import unittest
from datetime import datetime

import tests.factories.common as common
from app.api.helpers.csv_jobs_util import *
from tests.factories.attendee import AttendeeFactory
from tests.factories.order import OrderFactory
from tests.factories.session import SessionFactory
from tests.factories.speaker import SpeakerFactory
from app.models import db
from tests.all.integration.auth_helper import create_user
from tests.all.integration.utils import OpenEventTestCase


class TestExportCSV(OpenEventTestCase):
    def test_export_orders_csv(self):
        """Method to check the orders data export"""

        with self.app.test_request_context():
            test_order = OrderFactory(created_at=datetime.now())
            test_order.amount = 2
            field_data = export_orders_csv([test_order])
            self.assertEqual(field_data[1][2], 'initializing')
            self.assertEqual(field_data[1][4], '2')

    def test_export_attendees_csv(self):
        """Method to check the attendees data export"""

        with self.app.test_request_context():
            test_attendee = AttendeeFactory()
            field_data = export_attendees_csv([test_attendee])
            self.assertEqual(field_data[1][3], common.string_)
            self.assertEqual(field_data[1][5], 'user0@example.com')

    def _test_export_session_csv(self, test_session=None):
        with self.app.test_request_context():
            if not test_session:
                test_session = SessionFactory()
            field_data = export_sessions_csv([test_session])
            session_row = field_data[1]

            self.assertEqual(session_row[0], 'example (accepted)')
            self.assertEqual(session_row[9], 'accepted')

    def test_export_sessions_csv(self):
        """Method to check sessions data export"""

        with self.app.test_request_context():
            self._test_export_session_csv()

    def test_export_sessions_none_csv(self):
        """Method to check sessions data export with no abstract"""

        with self.app.test_request_context():
            test_session = SessionFactory()
            test_session.long_abstract = None
            test_session.level = None
            self._test_export_session_csv(test_session)

    def test_export_sessions_with_details_csv(self):
        """Method to check that sessions details are correct"""

        with self.app.test_request_context():
            test_session = SessionFactory(
                short_abstract='short_abstract',
                long_abstract='long_abstract',
                comments='comment',
                level='level',
                created_at=common.date_,
            )
            db.session.commit()
            field_data = export_sessions_csv([test_session])
            session_row = field_data[1]

            self.assertEqual(session_row[0], 'example (accepted)')
            self.assertEqual(session_row[1], '')
            self.assertEqual(session_row[2], common.string_)
            self.assertEqual(session_row[3], 'short_abstract')
            self.assertEqual(session_row[4], 'long_abstract')
            self.assertEqual(session_row[5], 'comment')
            self.assertEqual(session_row[6], common.date_.astimezone())
            self.assertEqual(session_row[7], 'Yes')
            self.assertEqual(session_row[8], 'level')
            self.assertEqual(session_row[9], 'accepted')
            self.assertEqual(session_row[10], common.string_)
            self.assertEqual(session_row[11], '00:30')
            self.assertEqual(session_row[12], 'English')
            self.assertEqual(session_row[13], common.url_)
            self.assertEqual(session_row[14], common.url_)
            self.assertEqual(session_row[15], common.url_)

    def test_export_speakers_csv(self):
        """Method to check speakers data export"""

        with self.app.test_request_context():
            test_speaker = SpeakerFactory(
                name='Mario Behling',
                mobile='9004345009',
                short_biography='Speaker Bio',
                organisation='FOSSASIA',
                position='position',
                speaking_experience='1',
                sponsorship_required='No',
                city='Berlin',
                country='Germany',
            )
            user = create_user(email='export@example.com', password='password')
            user.id = 2
            field_data = export_speakers_csv([test_speaker])
            speaker_row = field_data[1]
            self.assertEqual(speaker_row[0], 'Mario Behling')
            self.assertEqual(speaker_row[1], 'user0@example.com')
            self.assertEqual(speaker_row[2], '')
            self.assertEqual(speaker_row[3], '9004345009')
            self.assertEqual(speaker_row[4], 'Speaker Bio')
            self.assertEqual(speaker_row[5], 'FOSSASIA')
            self.assertEqual(speaker_row[6], 'position')
            self.assertEqual(speaker_row[7], '1')
            self.assertEqual(speaker_row[8], 'No')
            self.assertEqual(speaker_row[9], 'Berlin')
            self.assertEqual(speaker_row[10], 'Germany')
            self.assertEqual(speaker_row[11], common.url_)
            self.assertEqual(speaker_row[12], common.url_)
            self.assertEqual(speaker_row[13], common.url_)
            self.assertEqual(speaker_row[14], common.url_)
            self.assertEqual(speaker_row[15], common.url_)


if __name__ == '__main__':
    unittest.main()
