"""empty message

Revision ID: 40911d5c6c5b
Revises: 28c3d6eb08f9
Create Date: 2016-07-11 07:46:23.614512

"""

# revision identifiers, used by Alembic.
revision = '40911d5c6c5b'
down_revision = '28c3d6eb08f9'

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('events', sa.Column('searchable_location_name', sa.String(), nullable=True))
    op.add_column('events_version', sa.Column('searchable_location_name', sa.String(), autoincrement=False, nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('events_version', 'searchable_location_name')
    op.drop_column('events', 'searchable_location_name')
    ### end Alembic commands ###
