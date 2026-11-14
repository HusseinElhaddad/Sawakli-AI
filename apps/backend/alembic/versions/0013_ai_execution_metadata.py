"""Preserve the exact AI outcome and claim context for safe replay and retry."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0013_ai_execution_metadata"
down_revision = "0012_entity_unique_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_runs", sa.Column("execution_metadata", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("model_runs", "execution_metadata")
