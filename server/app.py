from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, stream_with_context
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
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": os.getenv("CORS_ORIGIN", "*"),
        }
    },
)


def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _schedule_title_generation(session_id: str, seed_message: str) -> None:
    def task():
        title = generate_chat_title(seed_message)
        update_session_title(session_id, title)

    TITLE_EXECUTOR.submit(task)


@app.get("/api/health")
def healthcheck():
    return jsonify({"status": "ok"})


@app.get("/api/sessions")
def sessions():
    return jsonify({"items": list_sessions()})


@app.get("/api/sessions/<session_id>")
def session_detail(session_id: str):
    session_payload = get_session_with_messages(session_id)
    if session_payload is None:
        return jsonify({"error": "Session not found."}), 404
    return jsonify(session_payload)


@app.patch("/api/sessions/<session_id>")
def session_update(session_id: str):
    session = get_session_summary(session_id)
    if session is None:
        return jsonify({"error": "Session not found."}), 404

    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"error": "A non-empty 'title' field is required."}), 400

    update_session_title(session_id, title)
    updated_session = get_session_summary(session_id)
    return jsonify({"session": updated_session})


@app.delete("/api/sessions/<session_id>")
def session_delete(session_id: str):
    deleted = delete_session(session_id)
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
        session = get_session_summary(session_id)
        if session is None:
            return jsonify({"error": "Session not found."}), 404
    else:
        session = create_session()
        session_id = session["id"]

    add_message(session_id, "user", message)
    if count_user_messages(session_id) == 1:
        _schedule_title_generation(session_id, message)

    def generate():
        assistant_parts: list[str] = []
        assistant_sources: list[dict] = []
        assistant_saved = False

        yield _sse("session", {"session": get_session_summary(session_id)})

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
                    event["data"]["session"] = get_session_summary(session_id)
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
        debug=True,
        threaded=True,
    )
