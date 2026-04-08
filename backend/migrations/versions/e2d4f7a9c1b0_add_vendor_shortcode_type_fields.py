"""Add vendor shortcode type fields.

Revision ID: e2d4f7a9c1b0
Revises: c7b9d1f5a2e1
Create Date: 2026-04-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e2d4f7a9c1b0"
down_revision = "c7b9d1f5a2e1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("vendors", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "shortcode_type",
                sa.String(length=20),
                nullable=False,
                server_default="TILL",
            )
        )
        batch_op.add_column(sa.Column("paybill_account_number", sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table("vendors", schema=None) as batch_op:
        batch_op.drop_column("paybill_account_number")
        batch_op.drop_column("shortcode_type")
