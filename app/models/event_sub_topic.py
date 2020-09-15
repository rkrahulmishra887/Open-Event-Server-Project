from app.api.helpers.db import get_new_slug
from app.models import db
from app.models.base import SoftDeletionModel


class EventSubTopic(SoftDeletionModel):
    """Event sub topic object table"""

    __tablename__ = 'event_sub_topics'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    slug = db.Column(db.String, unique=True, nullable=False)
    events = db.relationship('Event', backref='event-sub-topic')
    event_topic = db.relationship('EventTopic', backref='event-sub-topics')
    event_topic_id = db.Column(
        db.Integer, db.ForeignKey('event_topics.id', ondelete='CASCADE')
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.slug = get_new_slug(EventSubTopic, self.name)

    def __repr__(self):
        return '<EventSubTopic %r>' % self.name
