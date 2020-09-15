import unittest
from datetime import datetime, timedelta, timezone

import tests.factories.common as common
from app.api.attendees import get_sold_and_reserved_tickets_count
from app.api.helpers.db import save_to_db
from app.api.helpers.order import delete_related_attendees_for_order, set_expiry_for_order
from tests.factories.attendee import AttendeeFactoryBase
from tests.factories.event import EventFactoryBasic
from tests.factories.order import OrderFactory
from tests.factories.ticket import TicketFactory
from app.models import db
from app.models.order import Order
from app.settings import get_settings
from tests.all.integration.utils import OpenEventTestCase


class TestOrderUtilities(OpenEventTestCase):
    def test_should_expire_outdated_order(self):
        """Method to test expiration of outdated orders"""

        with self.app.test_request_context():
            obj = OrderFactory()
            order_expiry_time = get_settings()['order_expiry_time']
            event = EventFactoryBasic()
            obj.event = event
            obj.created_at = datetime.now(timezone.utc) - timedelta(
                minutes=order_expiry_time
            )
            set_expiry_for_order(obj)
            self.assertEqual(obj.status, 'expired')

    def test_should_not_expire_valid_orders(self):
        """Method to test to not mark valid orders as expired"""

        with self.app.test_request_context():
            obj = OrderFactory()
            event = EventFactoryBasic()
            obj.event = event
            db.session.commit()
            set_expiry_for_order(obj)
            self.assertEqual(obj.status, 'initializing')

    def test_should_delete_related_attendees(self):
        """Method to test to delete related attendees of an event"""

        with self.app.test_request_context():
            attendee = AttendeeFactoryBase(event_id=EventFactoryBasic().id)

            obj = OrderFactory(event_id=attendee.event_id)
            obj.ticket_holders = [
                attendee,
            ]
            save_to_db(obj)

            delete_related_attendees_for_order(obj)
            order = db.session.query(Order).filter(Order.id == obj.id).first()
            self.assertEqual(len(order.ticket_holders), 0)

    def test_count_sold_and_reserved_tickets(self):
        """Method to test the count query of sold tickets"""

        with self.app.test_request_context():
            ticket = TicketFactory()
            other_ticket = TicketFactory()

            completed_order = OrderFactory(status='completed')
            placed_order = OrderFactory(status='placed')
            initializing_order = OrderFactory(
                status='initializing', created_at=datetime.utcnow() - timedelta(minutes=5)
            )
            pending_order = OrderFactory(
                status='pending', created_at=datetime.utcnow() - timedelta(minutes=35)
            )
            expired_time_order = OrderFactory(
                status='initializing', created_at=common.date_
            )
            expired_order = OrderFactory(status='expired')

            db.session.commit()

            # will not be counted as they have no order_id
            AttendeeFactoryBase.create_batch(2, ticket_id=ticket.id)
            # will be counted as attendee have valid orders
            AttendeeFactoryBase.create_batch(
                6, order_id=completed_order.id, ticket_id=ticket.id
            )
            # will be counted as attendee has valid placed order
            AttendeeFactoryBase(order_id=placed_order.id, ticket_id=ticket.id)
            # will not be counted as they are deleted
            AttendeeFactoryBase.create_batch(
                3,
                order_id=placed_order.id,
                ticket_id=ticket.id,
                deleted_at=datetime.utcnow(),
            )
            # will be counted as attendee has initializing order under order expiry time
            AttendeeFactoryBase.create_batch(
                4, order_id=initializing_order.id, ticket_id=ticket.id
            )
            # will be counted as attendee has pending order under 30+order expiry time
            AttendeeFactoryBase.create_batch(
                2, order_id=pending_order.id, ticket_id=ticket.id
            )
            # will not be counted as the order is not under order expiry time
            AttendeeFactoryBase.create_batch(
                3, order_id=expired_time_order.id, ticket_id=ticket.id
            )
            # will not be counted as the order has an expired state
            AttendeeFactoryBase.create_batch(
                5, order_id=expired_order.id, ticket_id=ticket.id
            )
            # will not be counted as the attendees have different ticket ID
            AttendeeFactoryBase.create_batch(
                2, order_id=completed_order.id, ticket_id=other_ticket.id
            )

            count = get_sold_and_reserved_tickets_count(ticket.id)

            self.assertEqual(count, 13)

            # Last 2 attendees belong to other ticket
            self.assertEqual(get_sold_and_reserved_tickets_count(other_ticket.id), 2)


if __name__ == '__main__':
    unittest.main()
