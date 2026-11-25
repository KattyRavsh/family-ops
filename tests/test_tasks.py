import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pydantic import ValidationError

import main

from database import Base

from main import TaskDraft, TaskDraftRequest, TaskDraftResponse, weekday_due_date

from datetime import date, datetime
from types import SimpleNamespace
from decimal import Decimal
from ml.labels import get_late_label


def make_fake_ai_client(content: str):
    def fake_create(**kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content)
                )
            ]
        )

    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=fake_create)
        )
    )


@pytest.fixture
def client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    previous_overrides = main.app.dependency_overrides.copy()
    main.app.dependency_overrides[main.get_db] = override_get_db

    try:
        with TestClient(main.app) as test_client:
            yield test_client
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(previous_overrides)
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def test_create_and_get_task(client):
    create_response = client.post(
        "/tasks",
        json={"title": "Полить цветы"},
    )

    assert create_response.status_code == 200
    created_task = create_response.json()

    assert created_task["id"] == 1
    assert created_task["title"] == "Полить цветы"
    assert created_task["completed"] is False
    assert created_task["due_date"] is None
    assert created_task["assigned_member_id"] is None
    assert created_task["completed_at"] is None

    datetime.fromisoformat(created_task["created_at"])

    get_response = client.get("/tasks")

    assert get_response.status_code == 200
    assert get_response.json() == [created_task]


def test_complete_task(client):
    create_response = client.post(
        "/tasks",
        json={"title": "Убрать кухню"},
    )
    task_id = create_response.json()["id"]

    complete_response = client.patch(
        f"/tasks/{task_id}/complete"
    )

    assert complete_response.status_code == 200
    assert complete_response.json()["completed"] is True


def test_complete_missing_task_returns_404(client):
    response = client.patch("/tasks/999/complete")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_create_task_with_empty_title_returns_422(client):
    response = client.post(
        "/tasks",
        json={"title": ""},
    )

    assert response.status_code == 422


def test_create_task_with_max_length_title_returns_200(client):
    response = client.post(
        "/tasks",
        json={"title": "a" * 100},
    )

    assert response.status_code == 200
    assert len(response.json()["title"]) == 100


def test_create_task_with_too_long_title_returns_422(client):
    response = client.post(
        "/tasks",
        json={"title": "a" * 101},
    )

    assert response.status_code == 422


def test_create_task_with_whitespace_only_title_returns_422(client):
    response = client.post(
        "/tasks",
        json={"title": "  "},
    )

    assert response.status_code == 422


def test_create_task_with_surrounding_spaces_trims_title(client):
    response = client.post(
        "/tasks",
        json={"title": " Полить цветы "},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Полить цветы"


def test_create_task_with_due_date(client):
    response = client.post(
        "/tasks",
        json={
            "title": "Полить цветы",
            "due_date": "2026-12-01",
        },
    )

    assert response.status_code == 200
    assert response.json()["due_date"] == "2026-12-01"


def test_create_and_get_family_member(client):
    create_response = client.post(
        "/family-members",
        json={"name": "Катя"},
    )

    assert create_response.status_code == 200
    member = create_response.json()
    assert member == {"id": 1, "name": "Катя"}

    list_response = client.get("/family-members")

    assert list_response.status_code == 200
    assert list_response.json() == [{"id": 1, "name": "Катя"}]


def test_create_task_assigned_to_family_member(client):
    member_response = client.post(
        "/family-members",
        json={"name": "Катя"},
    )
    member_id = member_response.json()["id"]

    task_response = client.post(
        "/tasks",
        json={
            "title": "Полить цветы",
            "assigned_member_id": member_id,
        },
    )

    assert task_response.status_code == 200
    assert task_response.json()["assigned_member_id"] == member_id


def test_create_task_with_missing_member_returns_404(client):
    response = client.post(
        "/tasks",
        json={
            "title": "Полить цветы",
            "assigned_member_id": 999,
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Family member not found"}


def test_get_tasks_filtered_by_assigned_member(client):
    first_member = client.post(
        "/family-members",
        json={"name": "Катя"},
    ).json()

    second_member = client.post(
        "/family-members",
        json={"name": "Саша"},
    ).json()

    first_task = client.post(
        "/tasks",
        json={
            "title": "Полить цветы",
            "assigned_member_id": first_member["id"],
        },
    ).json()

    client.post(
        "/tasks",
        json={
            "title": "Убрать кухню",
            "assigned_member_id": second_member["id"],
        },
    )

    response = client.get(
        "/tasks",
        params={"assigned_member_id": first_member["id"]},
    )

    assert response.status_code == 200
    assert response.json() == [first_task]


def test_task_draft_request_accepts_text():
    request = TaskDraftRequest(text="Купить продукты")

    assert request.text == "Купить продукты"


def test_task_draft_request_rejects_blank_text():
    with pytest.raises(ValidationError):
        TaskDraftRequest(text="   ")


def test_task_draft_response_parses_date():
    response = TaskDraftResponse(
        tasks=[
            {
                "title": "Купить продукты",
                "due_date": "2026-11-28",
            }
        ]
    )

    assert response.tasks[0].title == "Купить продукты"
    assert response.tasks[0].due_date.isoformat() == "2026-11-28"


def test_create_task_drafts_returns_ai_response(client, monkeypatch):
    expected = {
        "tasks": [
            {"title": "Купить хлеб", "due_date": None},
            {"title": "Полить цветы", "due_date": None},
        ]
    }

    def fake_create(**kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"tasks": ['
                        '{"title": "Купить хлеб", "due_date": null},'
                        '{"title": "Полить цветы", "due_date": null}'
                        ']}'
                    )
                )
            ]
        )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=fake_create)
        )
    )

    monkeypatch.setattr(main, "client", fake_client)

    response = client.post(
        "/tasks/drafts",
        json={"text": "Купить хлеб\nПолить цветы"},
    )

    assert response.status_code == 200
    assert response.json() == expected


def test_weekday_due_date_calculates_upcoming_friday():
    result = weekday_due_date(
        "Полить цветы до пятницы",
        date(2026, 11, 24),  # вторник
    )

    assert result == date(2026, 11, 27)


def test_weekday_due_date_calculates_upcoming_monday():
    result = weekday_due_date(
        "Убраться до понедельника",
        date(2026, 11, 24),  # вторник
    )

    assert result == date(2026, 11, 30)


def test_weekday_due_date_returns_none_without_weekday():
    result = weekday_due_date(
        "Купить хлеб",
        date(2026, 11, 24),
    )

    assert result is None


def test_weekday_due_date_returns_none_for_ambiguous_weekdays():
    result = weekday_due_date(
        "Купить хлеб в среду, а цветы полить в пятницу",
        date(2026, 11, 24),
    )

    assert result is None


def test_create_task_drafts_returns_502_for_invalid_json(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "client",
        make_fake_ai_client("это не JSON"),
    )

    response = client.post(
        "/tasks/drafts",
        json={"text": "Купить хлеб"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "AI returned an invalid task draft"
    }


def test_create_task_drafts_returns_502_for_invalid_date(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "client",
        make_fake_ai_client(
            '{"tasks":[{"title":"Купить хлеб","due_date":"не дата"}]}'
        ),
    )

    response = client.post(
        "/tasks/drafts",
        json={"text": "Купить хлеб"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "AI returned an invalid task draft"
    }


def test_accept_task_drafts_saves_tasks(client):
    payload = {
        "tasks": [
            {"title": "Купить хлеб", "due_date": None},
            {"title": "Полить цветы", "due_date": "2026-11-27"},
        ]
    }

    response = client.post("/tasks/drafts/accept", json=payload)

    assert response.status_code == 200

    saved_tasks = response.json()
    assert len(saved_tasks) == 2
    assert saved_tasks[0]["title"] == "Купить хлеб"
    assert saved_tasks[0]["due_date"] is None
    assert saved_tasks[1]["title"] == "Полить цветы"
    assert saved_tasks[1]["due_date"] == "2026-11-27"
    assert all(task["id"] is not None for task in saved_tasks)

    tasks_response = client.get("/tasks")
    assert tasks_response.status_code == 200
    assert [task["title"] for task in tasks_response.json()] == [
        "Купить хлеб",
        "Полить цветы",
    ]


def test_accept_empty_task_drafts_returns_422(client):
    response = client.post(
        "/tasks/drafts/accept",
        json={"tasks": []},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Draft must contain at least one task"
    }


def test_budget_entries_create_and_filter(client):
    expense_response = client.post(
        "/budget-entries",
        json={
            "entry_type": "expense",
            "amount": "1250.50",
            "category": "Продукты",
            "description": "Покупки на неделю",
            "transaction_date": "2026-11-24",
            "member_id": None,
        },
    )

    income_response = client.post(
        "/budget-entries",
        json={
            "entry_type": "income",
            "amount": "50000.00",
            "category": "Зарплата",
            "description": None,
            "transaction_date": "2026-11-24",
            "member_id": None,
        },
    )

    assert expense_response.status_code == 200
    assert income_response.status_code == 200
    assert Decimal(str(expense_response.json()["amount"])) == Decimal("1250.50")

    all_entries = client.get("/budget-entries")
    assert all_entries.status_code == 200
    assert len(all_entries.json()) == 2

    expenses = client.get(
        "/budget-entries",
        params={"entry_type": "expense"},
    )
    assert expenses.status_code == 200
    assert len(expenses.json()) == 1
    assert expenses.json()[0]["category"] == "Продукты"

    date_filtered = client.get(
        "/budget-entries",
        params={
            "date_from": "2026-11-24",
            "date_to": "2026-11-24",
        },
    )
    assert date_filtered.status_code == 200
    assert len(date_filtered.json()) == 2


def test_budget_entry_rejects_zero_amount(client):
    response = client.post(
        "/budget-entries",
        json={
            "entry_type": "expense",
            "amount": "0",
            "category": "Продукты",
            "transaction_date": "2026-11-24",
        },
    )

    assert response.status_code == 422


def test_budget_summary_calculates_totals(client):
    client.post(
        "/budget-entries",
        json={
            "entry_type": "income",
            "amount": "50000.00",
            "category": "Зарплата",
            "transaction_date": "2026-11-24",
        },
    )
    client.post(
        "/budget-entries",
        json={
            "entry_type": "expense",
            "amount": "1250.50",
            "category": "Продукты",
            "transaction_date": "2026-11-24",
        },
    )

    response = client.get(
        "/budget-summary",
        params={
            "date_from": "2026-11-01",
            "date_to": "2026-11-30",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "date_from": "2026-11-01",
        "date_to": "2026-11-30",
        "income_total": "50000.00",
        "expense_total": "1250.50",
        "balance": "48749.50",
    }


def test_budget_summary_excludes_entries_outside_period(client):
    client.post(
        "/budget-entries",
        json={
            "entry_type": "income",
            "amount": "1000.00",
            "category": "Доход",
            "transaction_date": "2026-10-31",
        },
    )

    response = client.get(
        "/budget-summary",
        params={
            "date_from": "2026-11-01",
            "date_to": "2026-11-30",
        },
    )

    assert response.status_code == 200
    assert response.json()["income_total"] == "0.00"
    assert response.json()["expense_total"] == "0.00"
    assert response.json()["balance"] == "0.00"


def test_budget_summary_rejects_reversed_date_range(client):
    response = client.get(
        "/budget-summary",
        params={
            "date_from": "2026-11-30",
            "date_to": "2026-11-01",
        },
    )

    assert response.status_code == 422


def test_complete_task_sets_timestamp_only_once(client):
    create_response = client.post(
        "/tasks",
        json={"title": "Проверить дату завершения"},
    )
    assert create_response.status_code == 200

    task_id = create_response.json()["id"]

    first_response = client.patch(f"/tasks/{task_id}/complete")
    assert first_response.status_code == 200

    first_task = first_response.json()
    assert first_task["completed"] is True
    assert first_task["completed_at"] is not None
    datetime.fromisoformat(first_task["completed_at"])

    second_response = client.patch(f"/tasks/{task_id}/complete")
    assert second_response.status_code == 200
    assert second_response.json()["completed_at"] == first_task["completed_at"]


def test_task_completed_on_due_date_is_not_late():
    label = get_late_label(
        due_date=date(2026, 11, 27),
        completed=True,
        completed_at=datetime(2026, 11, 27, 20, 30),
        as_of=date(2026, 11, 28),
    )

    assert label == 0


def test_task_completed_after_due_date_is_late():
    label = get_late_label(
        due_date=date(2026, 11, 27),
        completed=True,
        completed_at=datetime(2026, 11, 28, 9, 0),
        as_of=date(2026, 11, 29),
    )

    assert label == 1


def test_unfinished_task_is_late_after_due_date():
    label = get_late_label(
        due_date=date(2026, 11, 27),
        completed=False,
        completed_at=None,
        as_of=date(2026, 11, 28),
    )

    assert label == 1


def test_unfinished_task_before_due_date_has_no_label():
    label = get_late_label(
        due_date=date(2026, 11, 27),
        completed=False,
        completed_at=None,
        as_of=date(2026, 11, 26),
    )

    assert label is None


def test_task_without_due_date_has_no_label():
    label = get_late_label(
        due_date=None,
        completed=False,
        completed_at=None,
        as_of=date(2026, 11, 28),
    )

    assert label is None


def test_legacy_completed_task_without_timestamp_has_no_label():
    label = get_late_label(
        due_date=date(2026, 11, 27),
        completed=True,
        completed_at=None,
        as_of=date(2026, 11, 28),
    )

    assert label is None


def test_create_task_with_author_and_assignee(client):
    author = client.post(
        "/family-members",
        json={"name": "Катя"},
    ).json()

    assignee = client.post(
        "/family-members",
        json={"name": "Саша"},
    ).json()

    response = client.post(
        "/tasks",
        json={
            "title": "Купить продукты",
            "assigned_member_id": assignee["id"],
            "created_by_member_id": author["id"],
            "category": "Дом",
            "priority": "high",
        },
    )

    assert response.status_code == 200
    task = response.json()
    assert task["title"] == "Купить продукты"
    assert task["assigned_member_id"] == assignee["id"]
    assert task["created_by_member_id"] == author["id"]
    assert task["category"] == "Дом"
    assert task["priority"] == "high"


def test_update_task_reassigns_and_unassigns_member(client):
    first_member = client.post(
        "/family-members",
        json={"name": "Катя"},
    ).json()

    second_member = client.post(
        "/family-members",
        json={"name": "Саша"},
    ).json()

    task = client.post(
        "/tasks",
        json={
            "title": "Полить цветы",
            "assigned_member_id": first_member["id"],
        },
    ).json()

    reassigned = client.patch(
        f"/tasks/{task['id']}",
        json={"assigned_member_id": second_member["id"]},
    )

    assert reassigned.status_code == 200
    assert reassigned.json()["assigned_member_id"] == second_member["id"]

    unassigned = client.patch(
        f"/tasks/{task['id']}",
        json={"assigned_member_id": None},
    )

    assert unassigned.status_code == 200
    assert unassigned.json()["assigned_member_id"] is None


def test_task_comments_create_and_list(client):
    author = client.post(
        "/family-members",
        json={"name": "Катя"},
    ).json()

    task = client.post(
        "/tasks",
        json={"title": "Купить продукты"},
    ).json()

    created = client.post(
        f"/tasks/{task['id']}/comments",
        json={
            "body": "Не забудь купить молоко",
            "author_member_id": author["id"],
        },
    )

    assert created.status_code == 200
    comment = created.json()
    assert comment["task_id"] == task["id"]
    assert comment["author_member_id"] == author["id"]
    assert comment["body"] == "Не забудь купить молоко"
    assert comment["created_at"] is not None

    listed = client.get(f"/tasks/{task['id']}/comments")

    assert listed.status_code == 200
    assert listed.json() == [comment]