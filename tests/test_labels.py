from datetime import date, datetime

from ml.labels import get_late_label


def test_completed_on_due_date_is_on_time():
    assert get_late_label(
        due_date=date(2026, 11, 28),
        completed=True,
        completed_at=datetime(2026, 11, 28, 23, 59),
        as_of=date(2026, 12, 1),
    ) == 0


def test_completed_after_due_date_is_late():
    assert get_late_label(
        due_date=date(2026, 11, 28),
        completed=True,
        completed_at=datetime(2026, 11, 29, 0, 1),
        as_of=date(2026, 12, 1),
    ) == 1


def test_completed_legacy_task_without_timestamp_is_unknown():
    assert get_late_label(
        due_date=date(2026, 11, 28),
        completed=True,
        completed_at=None,
        as_of=date(2026, 12, 1),
    ) is None


def test_open_overdue_task_is_late():
    assert get_late_label(
        due_date=date(2026, 11, 28),
        completed=False,
        completed_at=None,
        as_of=date(2026, 12, 1),
    ) == 1


def test_open_task_not_yet_due_is_unknown():
    assert get_late_label(
        due_date=date(2026, 12, 4),
        completed=False,
        completed_at=None,
        as_of=date(2026, 12, 1),
    ) is None


def test_no_due_date_is_unknown():
    assert get_late_label(
        due_date=None,
        completed=True,
        completed_at=datetime(2026, 11, 28),
        as_of=date(2026, 12, 1),
    ) is None
