"""add patient blood_group column

Revision ID: 6f4ec4c5d0d1
Revises: 
Create Date: 2026-08-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6f4ec4c5d0d1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("patients")]

    if "blood_group" not in columns:
        with op.batch_alter_table("patients", schema=None) as batch_op:
            batch_op.add_column(sa.Column("blood_group", sa.String(length=10), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("patients")]

    if "blood_group" in columns:
        with op.batch_alter_table("patients", schema=None) as batch_op:
            batch_op.drop_column("blood_group")
