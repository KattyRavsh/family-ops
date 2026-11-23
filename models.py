from sqlalchemy import Boolean, Integer, String, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

from datetime import date


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


class FamilyMemberModel(Base):
    __tablename__ = "family_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)