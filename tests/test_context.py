
import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        database,
        "DB_PATH",
        tmp_path / "context_test.db",
    )
    database.init_db()

    with TestClient(app) as test_client:
        yield test_client


def test_only_relevant_memories_reach_llm(
    client, monkeypatch
):
    captured = {}

    def mock_llm(message, history, memories):
        captured["memories"] = memories
        return "Mock response"

    monkeypatch.setattr(
        "app.main.generate_response",
        mock_llm,
    )

    database.save_memory(
        "user-1", "career_goal", "Switch jobs next year"
    )
    database.save_memory(
        "user-1", "interest", "Cricket"
    )
    database.save_memory(
        "user-1", "language_preference", "Hindi"
    )

    response = client.post(
        "/chat",
        json={
            "user_id": "user-1",
            "session_id": "session-1",
            "message": "What should I focus on for my career?",
        },
    )

    assert response.status_code == 200

    categories = {
        memory["memory_type"]
        for memory in captured["memories"]
    }

    assert categories == {
        "career_goal",
        "language_preference",
    }

    assert set(response.json()["context_used"]) == categories


def test_session_history_isolation(
    client, monkeypatch
):
    captured = {}

    def mock_llm(message, history, memories):
        captured[message] = history
        return "Mock response"

    monkeypatch.setattr(
        "app.main.generate_response",
        mock_llm,
    )

    def send(session_id, message):
        return client.post(
            "/chat",
            json={
                "user_id": "user-1",
                "session_id": session_id,
                "message": message,
            },
        )

    assert send(
        "session-A",
        "My interview is on Monday.",
    ).status_code == 200

    assert send(
        "session-B",
        "I like cricket.",
    ).status_code == 200

    assert send(
        "session-A",
        "When is my interview?",
    ).status_code == 200

    history = captured["When is my interview?"]

    assert len(history) == 2
    assert history[0]["content"] == (
        "My interview is on Monday."
    )
    assert history[1]["content"] == "Mock response"

    assert all(
        "cricket" not in item["content"].lower()
        for item in history
    )
