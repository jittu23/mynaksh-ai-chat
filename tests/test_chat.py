
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import database


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Use a separate SQLite database for each test.
    monkeypatch.setattr(
        database,
        "DB_PATH",
        tmp_path / "test.db",
    )
    database.init_db()

    # Mock LLM: no API credentials or charges required.
    def fake_generate_response(message, history, memories):
        history_text = " ".join(
            item["content"] for item in history
        )

        if "Which company" in message:
            return (
                "Microsoft on Monday"
                if "Microsoft" in history_text
                else "I don't know"
            )

        return "Mock response"

    monkeypatch.setattr(
        "app.main.generate_response",
        fake_generate_response,
    )

    with TestClient(app) as test_client:
        yield test_client


def test_chat_endpoint(client):
    response = client.post(
        "/chat",
        json={
            "user_id": "user-1",
            "session_id": "session-1",
            "message": "Hello",
        },
    )

    assert response.status_code == 200
    assert response.json()["response"] == "Mock response"
    assert response.json()["context_used"] == []


def test_long_term_memory_across_sessions(client):
    client.post(
        "/chat",
        json={
            "user_id": "user-1",
            "session_id": "session-1",
            "message": (
                "I'm planning to switch jobs next year, "
                "and I prefer advice in Hindi."
            ),
        },
    )

    response = client.post(
        "/chat",
        json={
            "user_id": "user-1",
            "session_id": "session-2",
            "message": "What do you remember about my career?",
        },
    )

    assert response.status_code == 200
    assert "career_goal" in response.json()["context_used"]
    assert "language_preference" in response.json()["context_used"]


def test_short_term_conversation_history(client):
    client.post(
        "/chat",
        json={
            "user_id": "user-1",
            "session_id": "session-1",
            "message": "I have an interview with Microsoft on Monday.",
        },
    )

    response = client.post(
        "/chat",
        json={
            "user_id": "user-1",
            "session_id": "session-1",
            "message": "Which company did I mention?",
        },
    )

    assert response.status_code == 200
    assert "Microsoft on Monday" in response.json()["response"]


def test_irrelevant_memory_filtering(client):
    database.save_memory(
        "user-1",
        "career_goal",
        "Switch jobs next year",
    )

    response = client.post(
        "/chat",
        json={
            "user_id": "user-1",
            "session_id": "session-1",
            "message": "Tell me a joke about cats.",
        },
    )

    assert response.status_code == 200
    assert "career_goal" not in response.json()["context_used"]
