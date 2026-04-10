"""Add vendor interoperability account fields.

Revision ID: 7a1b4f33c9d2
Revises: e2d4f7a9c1b0
Create Date: 2026-04-10 16:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7a1b4f33c9d2"
down_revision = "e2d4f7a9c1b0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("vendors", schema=None) as batch_op:
        batch_op.add_column(sa.Column("airtel_number", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("kcb_account", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("equity_account", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("coop_account", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("absa_account", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("ncba_account", sa.String(length=30), nullable=True))


def downgrade():
    with op.batch_alter_table("vendors", schema=None) as batch_op:
        batch_op.drop_column("ncba_account")
        batch_op.drop_column("absa_account")
        batch_op.drop_column("coop_account")
        batch_op.drop_column("equity_account")
        batch_op.drop_column("kcb_account")
        batch_op.drop_column("airtel_number")
