
import re

from app.database import get_memories, save_memory


def extract_memories(message: str) -> dict[str, str]:
    """Extract useful long-term user information."""
    text = message.strip()
    extracted = {}

    # 1. Language preference
    language_match = re.search(
        r"\b(?:prefer|like|want)\b.{0,40}\b"
        r"(hindi|english|telugu|kannada)\b",
        text,
        re.IGNORECASE,
    )

    if language_match:
        extracted["language_preference"] = (
            language_match.group(1).capitalize()
        )

    # 2. Response preference
    if re.search(
        r"\b(?:prefer|like|want)\s+"
        r"(?:short|brief|concise)\s+"
        r"(?:answers|responses|replies)\b",
        text,
        re.IGNORECASE,
    ):
        extracted["response_preference"] = "Short answers"

    elif re.search(
        r"\b(?:prefer|like|want)\s+"
        r"(?:detailed|long)\s+"
        r"(?:answers|responses|explanations)\b",
        text,
        re.IGNORECASE,
    ):
        extracted["response_preference"] = "Detailed answers"

    # 3. Career goal
    career_patterns = [
        r"\b(?:i'm|i am)\s+planning to switch jobs[^.!?]*",
        r"\b(?:i'm|i am)\s+preparing for[^.!?]*interview[^.!?]*",
        r"\b(?:i want to|my goal is to)\s+become\s+[^.!?,]*",
    ]

    for pattern in career_patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            extracted["career_goal"] = match.group().strip()
            break

    # 4. Learning goal
    learning_match = re.search(
        r"\b(?:i want to|i plan to|my goal is to)\s+"
        r"(?:learn|study|master)\s+([^.!?,]+)",
        text,
        re.IGNORECASE,
    )

    if learning_match:
        extracted["learning_goal"] = (
            learning_match.group(0).strip()
        )

    # 5. Interests
    interest_match = re.search(
        r"\b(?:i'm interested in|i am interested in|"
        r"my hobby is)\s+[^.!?,]*",
        text,
        re.IGNORECASE,
    )

    if interest_match:
        extracted["interest"] = (
            interest_match.group().strip()
        )

    # 6. Location
    location_match = re.search(
        r"\b(?:i live in|i reside in|i'm based in|"
        r"i am based in)\s+"
        r"([a-zA-Z ]+?)(?=[.!?,]|$)",
        text,
        re.IGNORECASE,
    )

    if location_match:
        extracted["location"] = (
            location_match.group(1).strip()
        )

    return extracted


def remember(user_id: str, message: str) -> None:
    """Persist recognized user information in SQLite."""
    extracted = extract_memories(message)

    for memory_type, memory_value in extracted.items():
        save_memory(
            user_id,
            memory_type,
            memory_value,
        )


MEMORY_KEYWORDS = {
    "career_goal": {
        "career", "job", "jobs", "interview",
        "profession", "employment", "switch",
    },
    "learning_goal": {
        "learn", "learning", "study", "studying",
        "skill", "skills", "course", "education",
    },
    "interest": {
        "interest", "interests", "hobby", "hobbies",
        "enjoy", "favorite", "like",
    },
    "location": {
        "live", "living", "location",
        "city", "based", "reside",
    },
}

GLOBAL_PREFERENCES = {
    "language_preference",
    "response_preference",
}


def retrieve_relevant_memories(
    user_id: str,
    message: str,
) -> list[dict]:
    """
    Retrieve relevant memories using category filtering
    and lightweight keyword-overlap scoring.
    """

    memories = get_memories(user_id)

    query_words = set(
        re.findall(r"\b\w+\b", message.lower())
    )

    # Common words that should not influence relevance.
    stop_words = {
        "i", "im", "am", "my", "me", "you", "your",
        "a", "an", "the", "to", "for", "in", "on",
        "at", "of", "and", "or", "is", "are",
        "was", "were", "do", "does", "did",
        "what", "how", "why", "when", "where",
        "should", "can", "could", "would",
        "want", "plan", "planning", "start",
        "about", "with",
    }

    # Words describing memory categories rather than
    # specific subjects such as Python or Docker.
    generic_words = set().union(
        *MEMORY_KEYWORDS.values()
    )

    specific_query_words = (
        query_words - stop_words - generic_words
    )

    is_memory_question = bool(
        query_words & {"remember", "recall"}
    )

    preferences = []
    candidates = []

    for memory in memories:
        category = memory["memory_type"]

        # Always include global preferences.
        if category in GLOBAL_PREFERENCES:
            preferences.append(memory)
            continue

        # For explicit memory recall, include stored facts.
        if is_memory_question:
            candidates.append((memory, 1))
            continue

        category_keywords = MEMORY_KEYWORDS.get(
            category,
            set(),
        )

        # Exclude unrelated memory categories.
        if not (query_words & category_keywords):
            continue

        memory_words = set(
            re.findall(
                r"\b\w+\b",
                memory["memory_value"].lower(),
            )
        )

        specific_memory_words = (
            memory_words - stop_words - generic_words
        )

        # Count matching subject-specific words.
        score = len(
            specific_query_words & specific_memory_words
        )

        candidates.append((memory, score))

    if not candidates:
        return preferences

    max_score = max(
        score for _, score in candidates
    )

    if max_score > 0:
        # Select memories with the strongest topic match.
        selected = [
            memory
            for memory, score in candidates
            if score == max_score
        ]
    else:
        # For generic questions, keep category-matched facts.
        selected = [
            memory
            for memory, _ in candidates
        ]

    return preferences + selected
