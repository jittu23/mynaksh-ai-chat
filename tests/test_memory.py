
import pytest

from app import database
from app.memory import (
    extract_memories,
    remember,
    retrieve_relevant_memories,
)


@pytest.fixture
def memory_db(tmp_path, monkeypatch):
    monkeypatch.setattr(
        database,
        "DB_PATH",
        tmp_path / "memory_test.db",
    )
    database.init_db()


def test_extract_different_memory_categories():
    assert extract_memories(
        "I want to learn Python."
    )["learning_goal"] == "I want to learn Python"

    assert extract_memories(
        "I'm interested in astrology."
    )["interest"] == "I'm interested in astrology"

    assert extract_memories(
        "I live in Bangalore."
    )["location"] == "Bangalore"

    assert extract_memories(
        "I prefer short answers."
    )["response_preference"] == "Short answers"


def test_retrieve_relevant_memories(memory_db):
    user_id = "user-1"

    remember(user_id, "I want to learn Python.")
    remember(user_id, "I'm interested in astrology.")
    remember(user_id, "I prefer advice in Hindi.")

    memories = retrieve_relevant_memories(
        user_id,
        "What skills should I learn?",
    )

    categories = {
        item["memory_type"] for item in memories
    }

    assert "learning_goal" in categories
    assert "language_preference" in categories
    assert "interest" not in categories


def test_memory_isolation_between_users(memory_db):
    remember("user-1", "I live in Bangalore.")

    memories = retrieve_relevant_memories(
        "user-2",
        "Where do I live?",
    )

    assert memories == []


def test_memory_update(memory_db):
    remember("user-1", "I prefer advice in Hindi.")
    remember("user-1", "I prefer advice in English.")

    memories = database.get_memories("user-1")

    language_memories = [
        item for item in memories
        if item["memory_type"] == "language_preference"
    ]

    assert len(language_memories) == 1
    assert language_memories[0]["memory_value"] == "English"


def test_dont_save_every_message():
    assert extract_memories(
        "What is the weather today?"
    ) == {}


def test_retrieval_prioritizes_specific_learning_goal(memory_db):
    user_id = "user-ranking"

    remember(user_id, "I want to learn Python.")
    remember(user_id, "I want to learn Docker.")
    remember(user_id, "I want to learn Kubernetes.")

    memories = retrieve_relevant_memories(
        user_id,
        "How should I start learning Python?",
    )

    learning_goals = [
        memory["memory_value"]
        for memory in memories
        if memory["memory_type"] == "learning_goal"
    ]

    assert learning_goals == ["I want to learn Python"]


def test_multiple_learning_goals_should_be_preserved(memory_db):
    user_id = "user-multiple-goals"

    remember(user_id, "I want to learn Python.")
    remember(user_id, "I want to learn Docker.")

    memories = database.get_memories(user_id)

    goals = {
        memory["memory_value"]
        for memory in memories
        if memory["memory_type"] == "learning_goal"
    }

    assert goals == {
        "I want to learn Python",
        "I want to learn Docker",
    }


def test_generic_learning_question_retrieves_multiple_goals(
    memory_db,
):
    user_id = "user-generic"

    remember(user_id, "I want to learn Python.")
    remember(user_id, "I want to learn Docker.")

    memories = retrieve_relevant_memories(
        user_id,
        "What skills should I learn?",
    )

    goals = {
        memory["memory_value"]
        for memory in memories
        if memory["memory_type"] == "learning_goal"
    }

    assert goals == {
        "I want to learn Python",
        "I want to learn Docker",
    }
