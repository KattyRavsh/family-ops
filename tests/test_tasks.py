import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    main.tasks.clear()
    main.next_task_id = 1

    return TestClient(main.app)


def test_create_and_get_task(client):
    create_response = client.post(
        "/tasks",
        json={"title": "Полить цветы"},
    )

    assert create_response.status_code == 200
    assert create_response.json() == {
        "id": 1,
        "title": "Полить цветы",
        "completed": False,
    }

    list_response = client.get("/tasks")

    assert list_response.status_code == 200
    assert list_response.json() == [
        {
            "id": 1,
            "title": "Полить цветы",
            "completed": False,
        }
    ]


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