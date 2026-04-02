"""Update database schema

Revision ID: fa0c6f002828
Revises: 409e7a93b342
Create Date: 2025-11-05 16:28:19.293763

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fa0c6f002828'
down_revision = '409e7a93b342'
branch_labels = None
depends_on = None


def upgrade():
    # Baseline migration already creates payment_sessions.transaction_id.
    # Keep this revision as a no-op to preserve revision history continuity.
    pass


def downgrade():
    # No-op downgrade to match upgrade.
    pass
