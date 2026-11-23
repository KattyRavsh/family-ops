"""add family members and task assignment

Revision ID: c8beaef6620a
Revises: 8f72526a5e73
Create Date: 2026-11-18 19:18:43.656686

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8beaef6620a'
down_revision: Union[str, Sequence[str], None] = '8f72526a5e73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "family_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(
            sa.Column("assigned_member_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_tasks_assigned_member_id_family_members",
            "family_members",
            ["assigned_member_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint(
            "fk_tasks_assigned_member_id_family_members",
            type_="foreignkey",
        )
        batch_op.drop_column("assigned_member_id")

    op.drop_table("family_members")
