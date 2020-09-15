import factory

import tests.factories.common as common
from tests.factories.base import BaseFactory
from tests.factories.event import EventFactoryBasic
from tests.factories.order import OrderFactory
from tests.factories.ticket import TicketFactory
from app.models.ticket_holder import TicketHolder


class AttendeeFactoryBase(BaseFactory):
    class Meta:
        model = TicketHolder

    firstname = common.string_
    lastname = common.string_
    email = common.email_
    address = common.string_
    city = common.string_
    state = common.string_
    country = "IN"
    is_checked_in = True
    pdf_url = common.url_
    event_id = 1
    ticket_id = None
    order_id = None
    modified_at = common.date_


class AttendeeSubFactory(AttendeeFactoryBase):
    event = factory.SubFactory(EventFactoryBasic)


class AttendeeFactory(AttendeeFactoryBase):
    event = factory.RelatedFactory(EventFactoryBasic)
    ticket = factory.RelatedFactory(TicketFactory)
    order = factory.RelatedFactory(OrderFactory)
