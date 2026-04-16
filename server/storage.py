from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    func,
    inspect as sa_inspect,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "agentic_shopper.db")
DEFAULT_TITLE = "New chat"
INIT_DB_MAX_ATTEMPTS = 10
INIT_DB_RETRY_DELAY_SECONDS = 2

metadata = MetaData()

sessions = Table(
    "sessions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("owner_id", String(64), nullable=True),
    Column("title", String(255), nullable=False),
    Column("title_status", String(32), nullable=False, server_default=text("'pending'")),
    Column("created_at", Text, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

messages = Table(
    "messages",
    metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "session_id",
        String(64),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("role", String(32), nullable=False),
    Column("content", Text, nullable=False),
    Column("sources_json", Text, nullable=False, server_default=text("'[]'")),
    Column("created_at", Text, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

Index("idx_messages_session_created_at", messages.c.session_id, messages.c.created_at)

moa_messages = Table(
    "moa_messages",
    metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "session_id",
        String(64),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("user_query", Text, nullable=False),
    Column("layer1_critic", Text, nullable=False, server_default=text("''")),
    Column("layer1_summarizer", Text, nullable=False, server_default=text("''")),
    Column("layer1_extractor", Text, nullable=False, server_default=text("'{}'")),
    Column("final_synthesis", Text, nullable=False),
    Column("sources_json", Text, nullable=False, server_default=text("'[]'")),
    Column("created_at", Text, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

Index("idx_moa_messages_session_created_at", moa_messages.c.session_id, moa_messages.c.created_at)


def _sqlite_url() -> str:
    configured = os.getenv("DB_PATH", "").strip()
    if not configured:
        db_path = DEFAULT_DB_PATH
    elif os.path.isabs(configured):
        db_path = configured
    else:
        db_path = os.path.join(os.path.dirname(__file__), configured)
    return f"sqlite:///{db_path}"


def _database_url() -> str:
    configured = (os.getenv("DATABASE_URL") or "").strip()
    if not configured:
        return _sqlite_url()

    if "neon.tech" in configured and "sslmode=" not in configured.lower():
        separator = "&" if "?" in configured else "?"
        configured = f"{configured}{separator}sslmode=require"

    if configured.startswith("postgres://"):
        configured = configured.replace("postgres://", "postgresql+psycopg://", 1)
    elif configured.startswith("postgresql://"):
        configured = configured.replace("postgresql://", "postgresql+psycopg://", 1)

    return configured


@lru_cache(maxsize=1)
def _engine() -> Engine:
    database_url = _database_url()
    connect_args: Dict[str, Any] = {}
    engine_options: Dict[str, Any] = {
        "future": True,
        "pool_pre_ping": True,
    }

    if database_url.startswith("sqlite:///"):
        connect_args["check_same_thread"] = False
    else:
        # Neon serverless connections can be recycled after idle periods.
        # Pre-ping plus recycle keeps Render workers from holding stale sockets.
        engine_options.update(
            {
                "pool_recycle": 300,
                "pool_timeout": 30,
            }
        )

    return create_engine(
        database_url,
        connect_args=connect_args,
        **engine_options,
    )


def _serialize_timestamp(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _message_count_subquery():
    legacy_count = (
        select(func.count())
        .select_from(messages)
        .where(messages.c.session_id == sessions.c.id)
        .correlate(sessions)
        .scalar_subquery()
    )
    moa_count = (
        select(func.count())
        .select_from(moa_messages)
        .where(moa_messages.c.session_id == sessions.c.id)
        .correlate(sessions)
        .scalar_subquery()
    )
    return legacy_count + (moa_count * 2)


def _last_message_preview_subquery():
    moa_preview = (
        select(moa_messages.c.final_synthesis)
        .where(moa_messages.c.session_id == sessions.c.id)
        .order_by(moa_messages.c.created_at.desc(), moa_messages.c.id.desc())
        .limit(1)
        .correlate(sessions)
        .scalar_subquery()
    )
    legacy_preview = (
        select(messages.c.content)
        .where(messages.c.session_id == sessions.c.id)
        .order_by(messages.c.created_at.desc(), messages.c.id.desc())
        .limit(1)
        .correlate(sessions)
        .scalar_subquery()
    )
    return func.coalesce(moa_preview, legacy_preview)


def init_db() -> None:
    engine = _engine()
    last_error: Exception | None = None

    for attempt in range(1, INIT_DB_MAX_ATTEMPTS + 1):
        try:
            metadata.create_all(engine)
            _ensure_schema_updates(engine)
            return
        except SQLAlchemyError as exc:
            last_error = exc
            if attempt == INIT_DB_MAX_ATTEMPTS:
                break
            time.sleep(INIT_DB_RETRY_DELAY_SECONDS)

    raise RuntimeError("Failed to initialize the database.") from last_error


def create_session(owner_id: str, title: str = DEFAULT_TITLE) -> Dict[str, Any]:
    session_id = str(uuid.uuid4())
    with _engine().begin() as connection:
        connection.execute(
            insert(sessions).values(
                id=session_id,
                owner_id=owner_id,
                title=title,
                title_status="pending",
            )
        )

    session = get_session_summary(session_id, owner_id)
    if session is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Failed to create session.")
    return session


def get_session_summary(session_id: str, owner_id: str) -> Optional[Dict[str, Any]]:
    with _engine().connect() as connection:
        row = (
            connection.execute(
                select(
                    sessions.c.id,
                    sessions.c.owner_id,
                    sessions.c.title,
                    sessions.c.title_status,
                    sessions.c.created_at,
                    sessions.c.updated_at,
                    _message_count_subquery().label("message_count"),
                    _last_message_preview_subquery().label("last_message_preview"),
                ).where(
                    sessions.c.id == session_id,
                    sessions.c.owner_id == owner_id,
                )
            )
            .mappings()
            .first()
        )

    return _row_to_session(row) if row else None


def list_sessions(owner_id: str) -> List[Dict[str, Any]]:
    with _engine().connect() as connection:
        rows = (
            connection.execute(
                select(
                    sessions.c.id,
                    sessions.c.owner_id,
                    sessions.c.title,
                    sessions.c.title_status,
                    sessions.c.created_at,
                    sessions.c.updated_at,
                    _message_count_subquery().label("message_count"),
                    _last_message_preview_subquery().label("last_message_preview"),
                )
                .where(sessions.c.owner_id == owner_id)
                .order_by(sessions.c.updated_at.desc(), sessions.c.created_at.desc())
            )
            .mappings()
            .all()
        )

    return [_row_to_session(row) for row in rows]


def get_session_with_messages(session_id: str, owner_id: str) -> Optional[Dict[str, Any]]:
    session = get_session_summary(session_id, owner_id)
    if session is None:
        return None

    with _engine().connect() as connection:
        moa_rows = (
            connection.execute(
                select(
                    moa_messages.c.id,
                    moa_messages.c.user_query,
                    moa_messages.c.layer1_critic,
                    moa_messages.c.layer1_summarizer,
                    moa_messages.c.layer1_extractor,
                    moa_messages.c.final_synthesis,
                    moa_messages.c.sources_json,
                    moa_messages.c.created_at,
                )
                .where(moa_messages.c.session_id == session_id)
                .order_by(moa_messages.c.created_at.asc(), moa_messages.c.id.asc())
            )
            .mappings()
            .all()
        )
        legacy_rows = (
            connection.execute(
                select(
                    messages.c.id,
                    messages.c.role,
                    messages.c.content,
                    messages.c.sources_json,
                    messages.c.created_at,
                )
                .where(messages.c.session_id == session_id)
                .order_by(messages.c.created_at.asc(), messages.c.id.asc())
            )
            .mappings()
            .all()
        )

    hydrated_messages: List[Dict[str, Any]] = []
    for row in moa_rows:
        hydrated_messages.extend(_row_to_moa_messages(row))
    hydrated_messages.extend(_row_to_message(row) for row in legacy_rows)

    return {
        "session": session,
        "messages": hydrated_messages,
    }


def add_message(
    session_id: str, role: str, content: str, sources: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    message_id = str(uuid.uuid4())
    safe_sources = sources or []

    with _engine().begin() as connection:
        connection.execute(
            insert(messages).values(
                id=message_id,
                session_id=session_id,
                role=role,
                content=content,
                sources_json=json.dumps(safe_sources, ensure_ascii=False),
            )
        )
        connection.execute(
            update(sessions)
            .where(sessions.c.id == session_id)
            .values(updated_at=func.current_timestamp())
        )
        row = (
            connection.execute(
                select(
                    messages.c.id,
                    messages.c.role,
                    messages.c.content,
                    messages.c.sources_json,
                    messages.c.created_at,
                ).where(messages.c.id == message_id)
            )
            .mappings()
            .first()
        )

    if row is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Failed to persist message.")
    return _row_to_message(row)


def add_moa_message(
    session_id: str,
    user_query: str,
    layer1_critic: str,
    layer1_summarizer: str,
    layer1_extractor: Any,
    final_synthesis: str,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    message_id = str(uuid.uuid4())
    safe_sources = sources or []

    with _engine().begin() as connection:
        connection.execute(
            insert(moa_messages).values(
                id=message_id,
                session_id=session_id,
                user_query=user_query,
                layer1_critic=layer1_critic or "",
                layer1_summarizer=layer1_summarizer or "",
                layer1_extractor=json.dumps(layer1_extractor or {}, ensure_ascii=False),
                final_synthesis=final_synthesis,
                sources_json=json.dumps(safe_sources, ensure_ascii=False),
            )
        )
        connection.execute(
            update(sessions)
            .where(sessions.c.id == session_id)
            .values(updated_at=func.current_timestamp())
        )
        row = (
            connection.execute(
                select(
                    moa_messages.c.id,
                    moa_messages.c.user_query,
                    moa_messages.c.layer1_critic,
                    moa_messages.c.layer1_summarizer,
                    moa_messages.c.layer1_extractor,
                    moa_messages.c.final_synthesis,
                    moa_messages.c.sources_json,
                    moa_messages.c.created_at,
                ).where(moa_messages.c.id == message_id)
            )
            .mappings()
            .first()
        )

    if row is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Failed to persist MoA message.")

    return {
        "id": message_id,
        "user_query": user_query,
        "final_synthesis": final_synthesis,
        "agent_breakdown": {
            "critic": layer1_critic or "",
            "summarizer": layer1_summarizer or "",
            "extractor": layer1_extractor or {},
        },
        "sources": safe_sources,
        "messages": _row_to_moa_messages(row),
        "created_at": _serialize_timestamp(row["created_at"]),
    }


def count_user_messages(session_id: str) -> int:
    with _engine().connect() as connection:
        legacy_total = connection.execute(
            select(func.count())
            .select_from(messages)
            .where(messages.c.session_id == session_id, messages.c.role == "user")
        ).scalar_one()
        moa_total = connection.execute(
            select(func.count())
            .select_from(moa_messages)
            .where(moa_messages.c.session_id == session_id)
        ).scalar_one()

    return int(legacy_total or 0) + int(moa_total or 0)


def update_session_title(session_id: str, owner_id: str, title: str) -> None:
    cleaned_title = " ".join(title.strip().split())[:80] or DEFAULT_TITLE
    with _engine().begin() as connection:
        connection.execute(
            update(sessions)
            .where(
                sessions.c.id == session_id,
                sessions.c.owner_id == owner_id,
            )
            .values(
                title=cleaned_title,
                title_status="ready",
                updated_at=func.current_timestamp(),
            )
        )


def delete_session(session_id: str, owner_id: str) -> bool:
    with _engine().begin() as connection:
        result = connection.execute(
            delete(sessions).where(
                sessions.c.id == session_id,
                sessions.c.owner_id == owner_id,
            )
        )
    return result.rowcount > 0


def mark_title_ready(session_id: str, owner_id: str) -> None:
    with _engine().begin() as connection:
        connection.execute(
            update(sessions)
            .where(
                sessions.c.id == session_id,
                sessions.c.owner_id == owner_id,
            )
            .values(title_status="ready")
        )


def _ensure_schema_updates(engine: Engine) -> None:
    inspector = sa_inspect(engine)
    session_columns = {column["name"] for column in inspector.get_columns("sessions")}

    with engine.begin() as connection:
        if "owner_id" not in session_columns:
            connection.execute(text("ALTER TABLE sessions ADD COLUMN owner_id VARCHAR(64)"))

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_sessions_owner_updated_at "
                "ON sessions(owner_id, updated_at)"
            )
        )

        if "moa_messages" in inspector.get_table_names():
            moa_columns = {
                column["name"] for column in inspector.get_columns("moa_messages")
            }
            moa_column_sql = {
                "layer1_critic": "ALTER TABLE moa_messages ADD COLUMN layer1_critic TEXT DEFAULT '' NOT NULL",
                "layer1_summarizer": "ALTER TABLE moa_messages ADD COLUMN layer1_summarizer TEXT DEFAULT '' NOT NULL",
                "layer1_extractor": "ALTER TABLE moa_messages ADD COLUMN layer1_extractor TEXT DEFAULT '{}' NOT NULL",
                "sources_json": "ALTER TABLE moa_messages ADD COLUMN sources_json TEXT DEFAULT '[]' NOT NULL",
            }
            for column_name, sql in moa_column_sql.items():
                if column_name not in moa_columns:
                    connection.execute(text(sql))


def _row_to_session(row: Mapping[str, Any]) -> Dict[str, Any]:
    preview = (row.get("last_message_preview") or "").strip()
    return {
        "id": row["id"],
        "title": row["title"],
        "title_status": row["title_status"],
        "created_at": _serialize_timestamp(row["created_at"]),
        "updated_at": _serialize_timestamp(row["updated_at"]),
        "message_count": int(row.get("message_count") or 0),
        "last_message_preview": preview[:120],
    }


def _row_to_message(row: Mapping[str, Any]) -> Dict[str, Any]:
    try:
        sources = json.loads(row.get("sources_json") or "[]")
    except json.JSONDecodeError:
        sources = []

    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "sources": sources,
        "created_at": _serialize_timestamp(row["created_at"]),
    }


def _safe_json_loads(raw_value: Any, fallback: Any) -> Any:
    if raw_value is None:
        return fallback
    if isinstance(raw_value, (dict, list)):
        return raw_value
    try:
        return json.loads(str(raw_value))
    except json.JSONDecodeError:
        return fallback


def _row_to_moa_messages(row: Mapping[str, Any]) -> List[Dict[str, Any]]:
    created_at = _serialize_timestamp(row["created_at"])
    sources = _safe_json_loads(row.get("sources_json"), [])
    extractor = _safe_json_loads(row.get("layer1_extractor"), {})
    agent_breakdown = {
        "critic": row.get("layer1_critic") or "",
        "summarizer": row.get("layer1_summarizer") or "",
        "extractor": extractor,
    }

    return [
        {
            "id": f"{row['id']}:user",
            "role": "user",
            "content": row.get("user_query") or "",
            "sources": [],
            "created_at": created_at,
        },
        {
            "id": f"{row['id']}:assistant",
            "role": "assistant",
            "content": row.get("final_synthesis") or "",
            "final_recommendation": row.get("final_synthesis") or "",
            "agent_breakdown": agent_breakdown,
            "sources": sources if isinstance(sources, list) else [],
            "created_at": created_at,
        },
    ]
