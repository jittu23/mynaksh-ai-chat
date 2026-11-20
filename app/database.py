
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "mynaksh.db"

# These categories hold one current value per user.
SINGLE_VALUE_MEMORIES = {
    "language_preference",
    "response_preference",
    "location",
}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize tables and migrate the old memory schema if needed."""

    with get_connection() as conn:

        # 1. Conversation history
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Memory table: allow distinct values in the same category
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                memory_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, memory_type, memory_value)
            )
        """)

        # 3. Detect the old UNIQUE(user_id, memory_type) schema
        old_schema = False

        indexes = conn.execute(
            "PRAGMA index_list('memories')"
        ).fetchall()

        for index in indexes:
            if not index["unique"]:
                continue

            index_name = index["name"]

            columns = [
                row["name"]
                for row in conn.execute(
                    f"PRAGMA index_info('{index_name}')"
                ).fetchall()
            ]

            if columns == ["user_id", "memory_type"]:
                old_schema = True
                break

        # 4. Migrate old memory table while retaining existing rows
        if old_schema:
            conn.execute("""
                CREATE TABLE memories_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, memory_type, memory_value)
                )
            """)

            conn.execute("""
                INSERT INTO memories_new (
                    id,
                    user_id,
                    memory_type,
                    memory_value,
                    created_at
                )
                SELECT
                    id,
                    user_id,
                    memory_type,
                    memory_value,
                    created_at
                FROM memories
            """)

            conn.execute("DROP TABLE memories")

            conn.execute("""
                ALTER TABLE memories_new
                RENAME TO memories
            """)

        # 5. Indexes for efficient lookup
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations
            ON conversations(user_id, session_id, id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories
            ON memories(user_id, memory_type)
        """)


def save_message(user_id, session_id, role, content):
    """Save a conversation message."""

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO conversations
            (user_id, session_id, role, content)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, session_id, role, content),
        )


def get_recent_history(user_id, session_id, limit=10):
    """Retrieve recent messages from the specified user and session."""

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM conversations
            WHERE user_id = ? AND session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, session_id, limit),
        ).fetchall()

    return [dict(row) for row in reversed(rows)]


def save_memory(user_id, memory_type, memory_value):
    """
    Save long-term user memory.

    Single-value categories replace the previous value.
    Multi-value categories preserve distinct memories.
    """

    with get_connection() as conn:

        if memory_type in SINGLE_VALUE_MEMORIES:

            # Replace existing preference or location
            conn.execute(
                """
                DELETE FROM memories
                WHERE user_id = ?
                  AND memory_type = ?
                """,
                (user_id, memory_type),
            )

        # Prevent duplicate entries while allowing multiple
        # distinct memories of the same category.
        conn.execute(
            """
            INSERT OR IGNORE INTO memories
            (user_id, memory_type, memory_value)
            VALUES (?, ?, ?)
            """,
            (user_id, memory_type, memory_value),
        )


def get_memories(user_id):
    """Retrieve all stored memories belonging to a user."""

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT memory_type, memory_value
            FROM memories
            WHERE user_id = ?
            ORDER BY id ASC
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]
