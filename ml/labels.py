from datetime import date, datetime


def get_late_label(
    *,
    due_date: date | None,
    completed: bool,
    completed_at: datetime | None,
    as_of: date,
) -> int | None:

    if due_date is None:
        return None

    if completed_at is not None:
        return int(completed_at.date() > due_date)

    if completed:
        return None

    if as_of > due_date:
        return 1

    return None
