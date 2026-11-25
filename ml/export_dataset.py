import csv
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select

from database import SessionLocal
from ml.labels import get_late_label
from models import TaskModel

LEGACY_CUTOFF = datetime(2026, 11, 24, 14, 15, 42)
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "task_lateness.csv"
FIELDNAMES = [
    "created_at",
    "days_until_due",
    "created_weekday",
    "due_weekday",
    "has_assignee",
    "label_late",
]


def main() -> None:
    db = SessionLocal()
    try:
        tasks = db.scalars(
            select(TaskModel)
            .where(TaskModel.created_at > LEGACY_CUTOFF)
            .order_by(TaskModel.created_at, TaskModel.id)
        ).all()
        today = date.today()
        rows: list[dict[str, str | int]] = []
        skipped: Counter[str] = Counter()

        for task in tasks:
            if task.due_date is None:
                skipped["no_due_date"] += 1
                continue

            if task.due_date < task.created_at.date():
                skipped["created_after_due_date"] += 1
                continue

            label = get_late_label(
                due_date=task.due_date,
                completed=task.completed,
                completed_at=task.completed_at,
                as_of=today,
            )
            if label is None:
                skipped["completed_without_timestamp" if task.completed else "outcome_not_known_yet"] += 1
                continue

            rows.append(
                {
                    "created_at": task.created_at.isoformat(),
                    "days_until_due": (task.due_date - task.created_at.date()).days,
                    "created_weekday": task.created_at.weekday(),
                    "due_weekday": task.due_date.weekday(),
                    "has_assignee": int(task.assigned_member_id is not None),
                    "label_late": label,
                }
            )

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

        distribution = Counter(row["label_late"] for row in rows)
        print(f"Найдено задач после границы миграции: {len(tasks)}")
        print(f"Примеров с известной меткой: {len(rows)}")
        print(f"Метка 0 (в срок): {distribution[0]}")
        print(f"Метка 1 (опоздала): {distribution[1]}")
        print("Пропущено:")
        for reason in ("no_due_date", "created_after_due_date", "completed_without_timestamp", "outcome_not_known_yet"):
            print(f"  {reason}: {skipped[reason]}")
        print(f"CSV сохранён: {OUTPUT_PATH}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
