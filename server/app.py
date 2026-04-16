from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from flask import Flask, Response, g, jsonify, request
from flask_cors import CORS

from agent import generate_chat_title, run_moa_shopper_reply
from storage import (
    add_moa_message,
    count_user_messages,
    create_session,
    delete_session,
    get_session_summary,
    get_session_with_messages,
    init_db,
    list_sessions,
    update_session_title,
)

load_dotenv()
init_db()

app = Flask(__name__)
TITLE_EXECUTOR = ThreadPoolExecutor(max_workers=2)
VIEWER_COOKIE_NAME = "shopper_viewer_id"
VIEWER_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def _resolve_cors_origins():
    explicit = (os.getenv("CORS_ORIGINS") or os.getenv("CORS_ORIGIN") or "").strip()
    if explicit:
        parsed = [
            origin.strip().rstrip("/")
            for origin in explicit.split(",")
            if origin.strip() and origin.strip() != "*"
        ]
        if not parsed:
            return ["http://localhost:5173", "http://127.0.0.1:5173"]
        return parsed if len(parsed) > 1 else parsed[0]

    return ["http://localhost:5173", "http://127.0.0.1:5173"]


CORS(
    app,
    resources={
        r"/api/*": {
            "origins": _resolve_cors_origins(),
            "supports_credentials": True,
        }
    },
)


def _normalize_viewer_id(raw_value: str) -> str:
    candidate = (raw_value or "").strip()
    if not candidate:
        return str(uuid.uuid4())

    try:
        return str(uuid.UUID(candidate))
    except ValueError:
        return str(uuid.uuid4())


def _cookie_settings() -> dict:
    secure = os.getenv("FORCE_SECURE_COOKIES", "").lower() in {"1", "true", "yes"} or request.is_secure
    return {
        "httponly": True,
        "max_age": VIEWER_COOKIE_MAX_AGE,
        "path": "/",
        "samesite": "None" if secure else "Lax",
        "secure": secure,
    }


def _schedule_title_generation(
    session_id: str,
    owner_id: str,
    seed_message: str,
    assistant_text: str = "",
    source_titles: list[str] | None = None,
) -> None:
    def task():
        title = generate_chat_title(
            seed_message,
            assistant_text=assistant_text,
            source_titles=source_titles or [],
        )
        update_session_title(session_id, owner_id, title)

    TITLE_EXECUTOR.submit(task)


@app.before_request
def ensure_viewer_cookie():
    current_value = request.cookies.get(VIEWER_COOKIE_NAME, "")
    normalized = _normalize_viewer_id(current_value)
    g.viewer_id = normalized
    g.viewer_cookie_needs_set = normalized != current_value


@app.after_request
def persist_viewer_cookie(response: Response):
    viewer_id = getattr(g, "viewer_id", "")
    if viewer_id:
        response.set_cookie(VIEWER_COOKIE_NAME, viewer_id, **_cookie_settings())
    return response


@app.get("/api/health")
def healthcheck():
    return jsonify({"status": "ok"})


@app.get("/api/sessions")
def sessions():
    return jsonify({"items": list_sessions(g.viewer_id)})


@app.get("/api/sessions/<session_id>")
def session_detail(session_id: str):
    session_payload = get_session_with_messages(session_id, g.viewer_id)
    if session_payload is None:
        return jsonify({"error": "Session not found."}), 404
    return jsonify(session_payload)


@app.patch("/api/sessions/<session_id>")
def session_update(session_id: str):
    session = get_session_summary(session_id, g.viewer_id)
    if session is None:
        return jsonify({"error": "Session not found."}), 404

    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"error": "A non-empty 'title' field is required."}), 400

    update_session_title(session_id, g.viewer_id, title)
    updated_session = get_session_summary(session_id, g.viewer_id)
    return jsonify({"session": updated_session})


@app.delete("/api/sessions/<session_id>")
def session_delete(session_id: str):
    deleted = delete_session(session_id, g.viewer_id)
    if not deleted:
        return jsonify({"error": "Session not found."}), 404
    return ("", 204)


@app.post("/api/chat")
async def chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    history = payload.get("history") or []
    session_id = (payload.get("session_id") or "").strip()

    if not message:
        return jsonify({"error": "A non-empty 'message' field is required."}), 400

    if not isinstance(history, list):
        return jsonify({"error": "'history' must be an array of chat messages."}), 400

    if session_id:
        session = get_session_summary(session_id, g.viewer_id)
        if session is None:
            return jsonify({"error": "Session not found."}), 404
    else:
        session = create_session(g.viewer_id)
        session_id = session["id"]

    try:
        result = await run_moa_shopper_reply(message=message, history=history)
    except Exception as exc:  # pragma: no cover - final guard rail
        return (
            jsonify(
                {
                    "error": str(exc)
                    or "The server hit an unexpected error while running the MoA pipeline."
                }
            ),
            500,
        )

    saved_turn = add_moa_message(
        session_id=session_id,
        user_query=message,
        layer1_critic=result["agent_breakdown"].get("critic", ""),
        layer1_summarizer=result["agent_breakdown"].get("summarizer", ""),
        layer1_extractor=result["agent_breakdown"].get("extractor", {}),
        final_synthesis=result["final_recommendation"],
        sources=result.get("sources", []),
    )
    is_first_user_message = count_user_messages(session_id) == 1

    if is_first_user_message:
        source_titles = [
            source.get("title", "")
            for source in result.get("sources", [])[:4]
            if source.get("title")
        ]
        _schedule_title_generation(
            session_id,
            g.viewer_id,
            message,
            assistant_text=result["final_recommendation"],
            source_titles=source_titles,
        )

    session = get_session_summary(session_id, g.viewer_id)
    return jsonify(
        {
            "session": session,
            "message": saved_turn,
            "final_recommendation": result["final_recommendation"],
            "agent_breakdown": result["agent_breakdown"],
            "sources": result.get("sources", []),
            "research": result.get("research", {}),
            "models": result.get("models", {}),
        }
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"},
        threaded=True,
    )
