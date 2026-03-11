from __future__ import annotations

import json
import os
import sqlite3
import uuid
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "agentic_shopper.db")
DEFAULT_TITLE = "New chat"


def _db_path() -> str:
    configured = os.getenv("DB_PATH", "").strip()
    if not configured:
        return DEFAULT_DB_PATH
    if os.path.isabs(configured):
        return configured
    return os.path.join(os.path.dirname(__file__), configured)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(_db_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    connection = _connect()
    with connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                title_status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_session_created_at
            ON messages(session_id, created_at)
            """
        )
    connection.close()


def create_session(title: str = DEFAULT_TITLE) -> Dict[str, Any]:
    session_id = str(uuid.uuid4())
    connection = _connect()

    with connection:
        connection.execute(
            """
            INSERT INTO sessions (id, title, title_status)
            VALUES (?, ?, ?)
            """,
            (session_id, title, "pending"),
        )

    session = get_session_summary(session_id)
    connection.close()
    if session is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Failed to create session.")
    return session


def get_session_summary(session_id: str) -> Optional[Dict[str, Any]]:
    connection = _connect()
    row = connection.execute(
        """
        SELECT
            s.id,
            s.title,
            s.title_status,
            s.created_at,
            s.updated_at,
            (
                SELECT COUNT(*)
                FROM messages m
                WHERE m.session_id = s.id
            ) AS message_count,
            (
                SELECT m.content
                FROM messages m
                WHERE m.session_id = s.id
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT 1
            ) AS last_message_preview
        FROM sessions s
        WHERE s.id = ?
        """,
        (session_id,),
    ).fetchone()
    connection.close()
    return _row_to_session(row) if row else None


def list_sessions() -> List[Dict[str, Any]]:
    connection = _connect()
    rows = connection.execute(
        """
        SELECT
            s.id,
            s.title,
            s.title_status,
            s.created_at,
            s.updated_at,
            (
                SELECT COUNT(*)
                FROM messages m
                WHERE m.session_id = s.id
            ) AS message_count,
            (
                SELECT m.content
                FROM messages m
                WHERE m.session_id = s.id
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT 1
            ) AS last_message_preview
        FROM sessions s
        ORDER BY s.updated_at DESC, s.created_at DESC
        """
    ).fetchall()
    connection.close()
    return [_row_to_session(row) for row in rows]


def get_session_with_messages(session_id: str) -> Optional[Dict[str, Any]]:
    session = get_session_summary(session_id)
    if session is None:
        return None

    connection = _connect()
    rows = connection.execute(
        """
        SELECT id, role, content, sources_json, created_at
        FROM messages
        WHERE session_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (session_id,),
    ).fetchall()
    connection.close()

    return {
        "session": session,
        "messages": [_row_to_message(row) for row in rows],
    }


def add_message(
    session_id: str, role: str, content: str, sources: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    message_id = str(uuid.uuid4())
    safe_sources = sources or []
    connection = _connect()

    with connection:
        connection.execute(
            """
            INSERT INTO messages (id, session_id, role, content, sources_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                message_id,
                session_id,
                role,
                content,
                json.dumps(safe_sources, ensure_ascii=False),
            ),
        )
        connection.execute(
            """
            UPDATE sessions
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (session_id,),
        )

    row = connection.execute(
        """
        SELECT id, role, content, sources_json, created_at
        FROM messages
        WHERE id = ?
        """,
        (message_id,),
    ).fetchone()
    connection.close()

    if row is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Failed to persist message.")
    return _row_to_message(row)


def count_user_messages(session_id: str) -> int:
    connection = _connect()
    row = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM messages
        WHERE session_id = ? AND role = 'user'
        """,
        (session_id,),
    ).fetchone()
    connection.close()
    return int(row["total"]) if row else 0


def update_session_title(session_id: str, title: str) -> None:
    cleaned_title = " ".join(title.strip().split())[:80] or DEFAULT_TITLE
    connection = _connect()

    with connection:
        connection.execute(
            """
            UPDATE sessions
            SET title = ?, title_status = 'ready', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (cleaned_title, session_id),
        )

    connection.close()


def delete_session(session_id: str) -> bool:
    connection = _connect()
    with connection:
        cursor = connection.execute(
            """
            DELETE FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        )
    deleted = cursor.rowcount > 0
    connection.close()
    return deleted


def mark_title_ready(session_id: str) -> None:
    connection = _connect()
    with connection:
        connection.execute(
            """
            UPDATE sessions
            SET title_status = 'ready'
            WHERE id = ?
            """,
            (session_id,),
        )
    connection.close()


def _row_to_session(row: sqlite3.Row) -> Dict[str, Any]:
    preview = (row["last_message_preview"] or "").strip()
    return {
        "id": row["id"],
        "title": row["title"],
        "title_status": row["title_status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "message_count": int(row["message_count"] or 0),
        "last_message_preview": preview[:120],
    }


def _row_to_message(row: sqlite3.Row) -> Dict[str, Any]:
    try:
        sources = json.loads(row["sources_json"] or "[]")
    except json.JSONDecodeError:
        sources = []

    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "sources": sources,
        "created_at": row["created_at"],
    }
