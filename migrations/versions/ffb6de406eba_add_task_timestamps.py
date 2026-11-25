"""add task timestamps

Revision ID: ffb6de406eba
Revises: f7eebd612be3
Create Date: 2026-11-24 17:13:19.671937

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ffb6de406eba'
down_revision: Union[str, Sequence[str], None] = 'f7eebd612be3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Сначала добавляем временные поля как допускающие NULL.
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(
            sa.Column("created_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("completed_at", sa.DateTime(), nullable=True)
        )

    # Для уже существующих задач ставим время применения миграции.
    # Это не настоящее время создания старых задач.
    op.execute(
        "UPDATE tasks "
        "SET created_at = CURRENT_TIMESTAMP "
        "WHERE created_at IS NULL"
    )

    # После заполнения делаем created_at обязательным
    # и задаём default для новых записей.
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("completed_at")
        batch_op.drop_column("created_at")
