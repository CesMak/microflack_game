"""initial migration

Revision ID: 1e80f4ae37b8
Revises: 
Create Date: 2020-10-30 20:30:32.002331

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1e80f4ae37b8'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.Integer(), nullable=True),
    sa.Column('updated_at', sa.Integer(), nullable=True),
    sa.Column('last_seen_at', sa.Integer(), nullable=True),
    sa.Column('nickname', sa.String(length=32), nullable=False),
    sa.Column('password_hash', sa.String(length=256), nullable=False),
    sa.Column('online', sa.Boolean(), nullable=True),
    sa.Column('roomid', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('nickname')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('users')
    # ### end Alembic commands ###
