import logging
from datetime import datetime, timedelta, timezone

from flask import render_template
from flask_rest_jsonapi.exceptions import ObjectNotFound

from app.api.helpers.db import (
    get_count,
    safe_query_without_soft_deleted_entries,
    save_to_db,
)
from app.api.helpers.errors import ConflictError, UnprocessableEntityError
from app.api.helpers.files import create_save_pdf
from app.api.helpers.storage import UPLOAD_PATHS
from app.models import db
from app.models.order import OrderTicket
from app.models.ticket import Ticket
from app.models.ticket_fee import TicketFees
from app.models.ticket_holder import TicketHolder
from app.settings import get_settings


def delete_related_attendees_for_order(order):
    """
    Delete the associated attendees of an order when it is cancelled/deleted/expired
    :param order: Order whose attendees have to be deleted.
    :return:
    """
    for ticket_holder in order.ticket_holders:
        db.session.delete(ticket_holder)
        try:
            db.session.commit()
        except Exception:
            logging.exception('DB Exception!')
            db.session.rollback()


def set_expiry_for_order(order, override=False):
    """
    Expire the order after the time slot(10 minutes) if the order is initializing.
    Also expires the order if we want to expire an order regardless of the state and time.
    :param order: Order to be expired.
    :param override: flag to force expiry.
    :return:
    """
    order_expiry_time = get_settings()['order_expiry_time']
    if (
        order
        and not order.paid_via
        and (
            override
            or (
                order.status == 'initializing'
                and (order.created_at + timedelta(minutes=order_expiry_time))
                < datetime.now(timezone.utc)
            )
        )
    ):
        order.status = 'expired'
        delete_related_attendees_for_order(order)
        save_to_db(order)
    return order


def create_pdf_tickets_for_holder(order):
    """
    Create tickets and invoices for the holders of an order.
    :param order: The order for which to create tickets for.
    """
    if order.status == 'completed' or order.status == 'placed':
        pdf = create_save_pdf(
            render_template('pdf/ticket_purchaser.html', order=order),
            UPLOAD_PATHS['pdf']['tickets_all'],
            dir_path='/static/uploads/pdf/tickets/',
            identifier=order.identifier,
            upload_dir='generated/tickets/',
        )

        order.tickets_pdf_url = pdf

        for holder in order.ticket_holders:
            if (not holder.user) or holder.user.id != order.user_id:
                # holder is not the order buyer.
                pdf = create_save_pdf(
                    render_template(
                        'pdf/ticket_attendee.html', order=order, holder=holder
                    ),
                    UPLOAD_PATHS['pdf']['tickets_all'],
                    dir_path='/static/uploads/pdf/tickets/',
                    identifier=order.identifier,
                    upload_dir='generated/tickets/',
                )
            else:
                # holder is the order buyer.
                pdf = order.tickets_pdf_url
            holder.pdf_url = pdf
            save_to_db(holder)

        # create order invoices pdf
        order_tickets = OrderTicket.query.filter_by(
            order_id=order.id, deleted_at=None
        ).all()

        create_save_pdf(
            render_template(
                'pdf/order_invoice.html',
                order=order,
                event=order.event,
                tax=order.event.tax,
                order_tickets=order_tickets,
            ),
            UPLOAD_PATHS['pdf']['order'],
            dir_path='/static/uploads/pdf/tickets/',
            identifier=order.identifier,
            upload_dir='generated/invoices/',
        )
        save_to_db(order)


def create_onsite_attendees_for_order(data):
    """
    Creates on site ticket holders for an order and adds it into the request data.
    :param data: data initially passed in the POST request for order.
    :return:
    """
    on_site_tickets = data.get('on_site_tickets')

    if not on_site_tickets:
        raise UnprocessableEntityError(
            {'pointer': 'data/attributes/on_site_tickets'}, 'on_site_tickets info missing'
        )

    data['ticket_holders'] = []

    for on_site_ticket in on_site_tickets:
        ticket_id = on_site_ticket['id']
        quantity = int(on_site_ticket['quantity'])

        ticket = safe_query_without_soft_deleted_entries(
            Ticket, 'id', ticket_id, 'ticket_id'
        )

        ticket_sold_count = get_count(
            db.session.query(TicketHolder.id).filter_by(
                ticket_id=int(ticket.id), deleted_at=None
            )
        )

        # Check if the ticket is already sold out or not.
        if ticket_sold_count + quantity > ticket.quantity:
            # delete the already created attendees.
            for holder in data['ticket_holders']:
                ticket_holder = (
                    db.session.query(TicketHolder).filter(id == int(holder)).one()
                )
                db.session.delete(ticket_holder)
                try:
                    db.session.commit()
                except Exception:
                    logging.exception('DB Exception!')
                    db.session.rollback()

            raise ConflictError(
                {'pointer': '/data/attributes/on_site_tickets'},
                "Ticket with id: {} already sold out. You can buy at most {} tickets".format(
                    ticket_id, ticket.quantity - ticket_sold_count
                ),
            )

        for _ in range(1, quantity):
            ticket_holder = TicketHolder(
                firstname='onsite',
                lastname='attendee',
                email='example@example.com',
                ticket_id=ticket.id,
                event_id=data.get('event'),
            )
            save_to_db(ticket_holder)
            data['ticket_holders'].append(ticket_holder.id)

    # delete from the data.
    del data['on_site_tickets']


def calculate_order_amount(tickets, discount_code=None):
    from app.models.discount_code import DiscountCode
    from app.api.helpers.ticketing import validate_tickets, validate_discount_code

    ticket_ids = [ticket['id'] for ticket in tickets]
    fetched_tickets = validate_tickets(ticket_ids)

    if discount_code:
        discount_code = validate_discount_code(discount_code, tickets=tickets)

    event = tax = tax_included = fees = None
    total_amount = total_tax = total_discount = 0.0
    ticket_list = []
    for ticket_info, ticket in zip(tickets, fetched_tickets):
        discount_amount = 0.0
        discount_data = None
        ticket_fee = 0.0

        quantity = ticket_info.get('quantity', 1)  # Default to single ticket
        if not event:
            event = ticket.event

            if event.deleted_at:
                raise ObjectNotFound(
                    {'pointer': 'tickets/event'}, f'Event: {event.id} not found'
                )

            fees = TicketFees.query.filter_by(currency=event.payment_currency).first()

        if not tax and event.tax:
            tax = event.tax
            tax_included = tax.is_tax_included_in_price

        if ticket.type == 'donation':
            price = ticket_info.get('price')
            if not price or price > ticket.max_price or price < ticket.min_price:
                raise UnprocessableEntityError(
                    {'pointer': 'tickets/price'},
                    f"Price for donation ticket should be present and within range "
                    f"{ticket.min_price} to {ticket.max_price}",
                )
        else:
            price = ticket.price if ticket.type != 'free' else 0.0

        if discount_code and ticket.type != 'free':
            code = (
                DiscountCode.query.with_parent(ticket)
                .filter_by(id=discount_code.id)
                .first()
            )
            if code:
                if discount_code.id == code.id:
                    if code.type == 'amount':
                        discount_amount = min(code.value, price)
                        discount_percent = (discount_amount / price) * 100
                    else:
                        discount_amount = (price * code.value) / 100
                        discount_percent = code.value
                    discount_data = {
                        'code': discount_code.code,
                        'percent': round(discount_percent, 2),
                        'amount': round(discount_amount, 2),
                        'total': round(discount_amount * quantity, 2),
                    }

        total_discount += round(discount_amount * quantity, 2)
        if fees and not ticket.is_fee_absorbed:
            ticket_fee = fees.service_fee * (price * quantity) / 100
            if ticket_fee > fees.maximum_fee:
                ticket_fee = fees.maximum_fee
        sub_total = ticket_fee + (price - discount_amount) * quantity
        total_amount = total_amount + sub_total
        ticket_list.append(
            {
                'id': ticket.id,
                'name': ticket.name,
                'price': price,
                'quantity': quantity,
                'discount': discount_data,
                'ticket_fee': round(ticket_fee, 2),
                'sub_total': round(sub_total, 2),
            }
        )

    sub_total = total_amount
    if tax:
        total_tax = total_amount * tax.rate / 100
        if not tax_included:
            total_amount += total_tax

    return dict(
        tax_included=tax_included,
        sub_total=round(sub_total, 2),
        total=round(total_amount, 2),
        tax=round(total_tax, 2),
        tax_percent=tax.rate if tax else 0.0,
        discount=round(total_discount, 2),
        tickets=ticket_list,
    )
