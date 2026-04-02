"""Add last_login and last_logout audit fields.

Revision ID: c7b9d1f5a2e1
Revises: fa0c6f002828
Create Date: 2026-04-02 19:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c7b9d1f5a2e1"
down_revision = "fa0c6f002828"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("last_login", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_logout", sa.DateTime(), nullable=True))

    with op.batch_alter_table("vendors", schema=None) as batch_op:
        batch_op.add_column(sa.Column("last_login", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_logout", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("vendors", schema=None) as batch_op:
        batch_op.drop_column("last_logout")
        batch_op.drop_column("last_login")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("last_logout")
        batch_op.drop_column("last_login")
