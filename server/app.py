from __future__ import annotations

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from flask import Flask, Response, g, jsonify, request, stream_with_context
from flask_cors import CORS

from agent import generate_chat_title, stream_shopper_reply
from storage import (
    add_message,
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


def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _normalize_viewer_id(raw_value: str) -> str:
    candidate = (raw_value or "").strip()
    if not candidate:
        return str(uuid.uuid4())

    try:
        return str(uuid.UUID(candidate))
    except ValueError:
        return str(uuid.uuid4())


def _cookie_settings() -> dict:
    secure = os.getenv("RENDER", "").lower() == "true" or request.is_secure
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
def chat():
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

    add_message(session_id, "user", message)
    is_first_user_message = count_user_messages(session_id) == 1

    def generate():
        assistant_parts: list[str] = []
        assistant_sources: list[dict] = []
        assistant_saved = False
        title_generation_scheduled = False

        def maybe_schedule_title_generation(assistant_text: str) -> None:
            nonlocal title_generation_scheduled
            if not is_first_user_message or title_generation_scheduled or not assistant_text:
                return
            source_titles = [
                source.get("title", "")
                for source in assistant_sources[:4]
                if source.get("title")
            ]
            _schedule_title_generation(
                session_id,
                g.viewer_id,
                message,
                assistant_text=assistant_text,
                source_titles=source_titles,
            )
            title_generation_scheduled = True

        yield _sse("session", {"session": get_session_summary(session_id, g.viewer_id)})

        try:
            for event in stream_shopper_reply(message=message, history=history):
                if event["event"] == "chunk":
                    assistant_parts.append(event["data"].get("text", ""))
                elif event["event"] == "sources":
                    assistant_sources = event["data"].get("items", [])
                elif event["event"] == "done" and not assistant_saved:
                    assistant_text = "".join(assistant_parts).strip()
                    if assistant_text:
                        add_message(
                            session_id,
                            "assistant",
                            assistant_text,
                            sources=assistant_sources,
                        )
                        assistant_saved = True
                        maybe_schedule_title_generation(assistant_text)
                    event["data"]["session"] = get_session_summary(session_id, g.viewer_id)
                yield _sse(event["event"], event["data"])
        except Exception as exc:  # pragma: no cover - final guard rail
            yield _sse(
                "error",
                {
                    "message": str(exc)
                    or "The server hit an unexpected error while streaming the reply."
                },
            )
            yield _sse("done", {"ok": False})
        finally:
            assistant_text = "".join(assistant_parts).strip()
            if assistant_text and not assistant_saved:
                add_message(
                    session_id,
                    "assistant",
                    assistant_text,
                    sources=assistant_sources,
                )
                maybe_schedule_title_generation(assistant_text)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers=headers,
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"},
        threaded=True,
    )
