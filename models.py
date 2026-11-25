from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from decimal import Decimal
from datetime import date, datetime


class TaskModel(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("family_members.id"),
        nullable=True,
    )
    created_by_member_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "family_members.id",
            name="fk_tasks_created_by_member_id_family_members",
        ),
        nullable=True,
    )

    category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    priority: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )


class FamilyMemberModel(Base):
    __tablename__ = "family_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class BudgetEntryModel(Base):
    __tablename__ = "budget_entries"
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('income', 'expense')",
            name="ck_budget_entries_entry_type",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_budget_entries_amount_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    entry_type: Mapped[str] = mapped_column(String(7), nullable=False)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)

    member_id: Mapped[int | None] = mapped_column(
        ForeignKey("family_members.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )


class TaskCommentModel(Base):
    __tablename__ = "task_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id"),
        nullable=False,
        index=True,
    )

    author_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("family_members.id"),
        nullable=True,
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )