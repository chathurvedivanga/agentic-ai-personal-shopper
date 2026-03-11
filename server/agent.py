from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterator, List

import google.generativeai as genai
from google.api_core.exceptions import NotFound, ResourceExhausted
from google.generativeai import protos

from scraper import fetch_transcripts_parallel, search_youtube_videos

SYSTEM_PROMPT = """
You are Agentic AI Personal Shopper, an expert shopping assistant.

Tool use policy:
- You have access to a tool named `fetch_youtube_reviews` that fetches YouTube review transcripts.
- ONLY use this tool if the user asks about a new product, category, shortlist, or comparison that has not already been researched in this conversation.
- If the user asks a follow-up question about a product or shortlist already researched in this conversation, rely on chat history and DO NOT call the tool again.
- Prefer existing conversation context over repeated tool calls.

Response style:
- Default to the Indian market unless the user explicitly asks for another country.
- Use Indian rupees (INR / Rs / ₹) in recommendations and budgets by default.
- If the user gives a budget in another currency such as USD, mention an approximate INR equivalent once and then continue in INR only.
- Prefer evidence from supplied YouTube review transcripts whenever they exist.
- If videos were found but transcripts were inaccessible, say that transcript access failed or subtitles were unavailable. Do not say the videos were unavailable.
- If fresh transcript evidence is unavailable, still provide a best-effort shortlist using the available review metadata and stable product knowledge.
- Start recommendation answers with a section titled "Verdict".
- Include a section titled "What the YouTube reviews focused on" with 3-5 bullets when review evidence is available.
- If multiple products are discussed, include a section titled "Quick compare" and use this exact style for each option:
  `#### Model name`
  `- Best for: ...`
  `- Gaming: ...`
  `- Battery: ...`
  `- Watch-outs: ...`
- Keep the answer concise, practical, and buyer-friendly.
- Fold reviewer sentiment and recurring user-feedback themes naturally into the recommendation. Do not create a separate "reviews and feedback" section unless the user explicitly asks for it.
- Do not add a separate "YouTube Links" section in the text response because the UI already shows the linked sources separately.
""".strip()

DEFAULT_MODEL_CANDIDATES = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
]
TITLE_MAX_LENGTH = 48
MAX_HISTORY_MESSAGES = 10
TOOL_NAME = "fetch_youtube_reviews"
DIRECT_RESPONSE_CHUNK_SIZE = 220


def _build_model(
    model_name: str,
    *,
    tools: list[Any] | None = None,
    system_instruction: str = SYSTEM_PROMPT,
):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing GEMINI_API_KEY. Add it to server/.env or your shell environment."
        )

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name=model_name,
        tools=tools,
        system_instruction=system_instruction,
    )


def _candidate_models() -> List[str]:
    configured_model = (os.getenv("GEMINI_MODEL") or "").strip()
    env_fallbacks = [
        item.strip()
        for item in (os.getenv("GEMINI_FALLBACK_MODELS") or "").split(",")
        if item.strip()
    ]
    candidates = [configured_model, *env_fallbacks, *DEFAULT_MODEL_CANDIDATES]
    ordered_unique: List[str] = []

    for candidate in candidates:
        if candidate and candidate not in ordered_unique:
            ordered_unique.append(candidate)

    return ordered_unique


def _is_model_not_found(exc: Exception) -> bool:
    if isinstance(exc, NotFound):
        return True

    message = str(exc).lower()
    return (
        "is not found for api version" in message
        or "not supported for generatecontent" in message
    )


def _is_quota_exhausted(exc: Exception) -> bool:
    if isinstance(exc, ResourceExhausted):
        return True

    message = str(exc).lower()
    return (
        "quota exceeded" in message
        or "exceeded your current quota" in message
        or "rate limit" in message
        or "429" in message
    )


def _fallback_title(seed_text: str) -> str:
    cleaned = re.sub(r"\s+", " ", seed_text).strip()
    cleaned = re.sub(r"[^\w\s₹./,+-]", "", cleaned).strip()
    words = [
        word
        for word in cleaned.split()
        if word.lower()
        not in {
            "a",
            "an",
            "best",
            "buy",
            "can",
            "compare",
            "find",
            "for",
            "help",
            "i",
            "looking",
            "me",
            "need",
            "please",
            "recommend",
            "search",
            "show",
            "suggest",
            "the",
            "what",
            "which",
        }
    ]
    if not words:
        return "New chat"
    title = " ".join(words[:6]).title()
    return title[:TITLE_MAX_LENGTH].strip() or "New chat"


def _clean_title(raw_text: str, seed_text: str) -> str:
    title = raw_text.strip().splitlines()[0].strip()
    title = title.strip("`\"'*-: ")
    title = re.sub(r"\s+", " ", title)
    if not title:
        return _fallback_title(seed_text)
    return title[:TITLE_MAX_LENGTH].strip() or _fallback_title(seed_text)


def generate_chat_title(seed_text: str) -> str:
    prompt = f"""
Create a short chat title for this shopping conversation.

Requirements:
- 3 to 6 words
- title case
- no quotes
- no punctuation unless needed for a product name
- focus on the buyer intent, product category, and budget if present

User message:
{seed_text}

Return only the title.
""".strip()

    for model_name in _candidate_models():
        try:
            model = _build_model(model_name, system_instruction="You create concise chat titles.")
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.2,
                    "max_output_tokens": 18,
                },
            )
            return _clean_title(getattr(response, "text", "") or "", seed_text)
        except Exception as exc:
            if _is_model_not_found(exc) or _is_quota_exhausted(exc):
                continue
            break

    return _fallback_title(seed_text)


def _format_sources(research_items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    return [
        {
            "title": item["title"],
            "url": item["url"],
            "channel": item.get("channel") or "Unknown channel",
        }
        for item in research_items
    ]


def _format_research_context(
    research_items: List[Dict[str, Any]], fallback_note: str
) -> str:
    if not research_items:
        return fallback_note

    blocks = []
    for index, item in enumerate(research_items, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[Source {index}] {item['title']}",
                    f"Channel: {item.get('channel') or 'Unknown channel'}",
                    f"URL: {item['url']}",
                    "Transcript excerpt:",
                    item["transcript"],
                ]
            )
        )

    return "\n\n".join(blocks)


def _format_video_candidates(videos: List[Dict[str, Any]]) -> str:
    if not videos:
        return "No video search candidates were found."

    lines = []
    for index, item in enumerate(videos, start=1):
        lines.append(
            f"[Video {index}] {item['title']} | Channel: {item.get('channel') or 'Unknown channel'} | URL: {item['url']}"
        )
    return "\n".join(lines)


def fetch_youtube_reviews(product_name: str) -> Dict[str, Any]:
    """Fetch YouTube review evidence for a product or shopping query.

    Use this only when the user asks about a new product, category, or comparison
    that has not already been researched in the current conversation.

    Args:
        product_name: The product or comparison request to research on YouTube,
            for example "gaming phone under Rs 40000 in India" or
            "iQOO Neo 10 vs Poco F7".

    Returns:
        A JSON-serializable dictionary containing transcript-backed review context,
        a fallback note when transcripts are unavailable, and the video sources
        that were found.
    """

    query = re.sub(r"\s+", " ", product_name or "").strip()
    if not query:
        query = "product reviews"

    videos = search_youtube_videos(query)
    research_items: List[Dict[str, Any]] = []

    if videos:
        research_items = fetch_transcripts_parallel(videos, max_workers=5)

    if research_items:
        research_note = (
            f"Fresh YouTube review research was requested for '{query}'. "
            f"The search found {len(videos)} candidate videos and transcript text was "
            f"successfully extracted for {len(research_items)} of them."
        )
    elif videos:
        research_note = (
            f"Fresh YouTube review research was requested for '{query}'. "
            f"The search found {len(videos)} candidate videos, but transcript access failed "
            "or subtitles were unavailable for the usable results."
        )
    else:
        research_note = (
            f"Fresh YouTube review research was requested for '{query}', but the search "
            "returned no usable videos."
        )

    source_items = _format_sources(research_items if research_items else videos)
    return {
        "query": query,
        "video_count": len(videos),
        "transcript_count": len(research_items),
        "research_note": research_note,
        "research_context": _format_research_context(research_items, research_note),
        "video_search_results": _format_video_candidates(videos),
        "sources": source_items,
    }


def _to_chat_history(
    history: List[Dict[str, Any]],
    current_message: str,
) -> List[protos.Content]:
    trimmed_history = history[-MAX_HISTORY_MESSAGES:]
    if trimmed_history:
        last_item = trimmed_history[-1]
        last_role = (last_item.get("role") or "").strip().lower()
        last_content = (last_item.get("content") or "").strip()
        if last_role == "user" and last_content == current_message.strip():
            trimmed_history = trimmed_history[:-1]

    contents: List[protos.Content] = []
    for item in trimmed_history:
        content = (item.get("content") or "").strip()
        if not content:
            continue

        role = (item.get("role") or "user").strip().lower()
        model_role = "model" if role == "assistant" else "user"
        contents.append(
            protos.Content(role=model_role, parts=[protos.Part(text=content)])
        )

    return contents


def _extract_function_calls(response: Any) -> List[protos.FunctionCall]:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return []

    parts = getattr(candidates[0].content, "parts", None) or []
    return [part.function_call for part in parts if part and "function_call" in part]


def _function_args(function_call: protos.FunctionCall) -> Dict[str, Any]:
    return {key: value for key, value in function_call.args.items()}


def _safe_chunk_text(chunk: Any) -> str:
    try:
        return getattr(chunk, "text", "") or ""
    except Exception:
        return ""


def _chunk_direct_text(text: str) -> List[str]:
    normalized = text.strip()
    if not normalized:
        return []

    chunks: List[str] = []
    remainder = normalized

    while len(remainder) > DIRECT_RESPONSE_CHUNK_SIZE:
        split_at = remainder.rfind(" ", 0, DIRECT_RESPONSE_CHUNK_SIZE)
        if split_at <= 0:
            split_at = DIRECT_RESPONSE_CHUNK_SIZE
        chunk = remainder[:split_at]
        if split_at < len(remainder) and remainder[split_at].isspace():
            chunk += " "
        chunks.append(chunk)
        remainder = remainder[split_at:].lstrip()

    if remainder:
        chunks.append(remainder)

    return chunks


def _merge_sources(
    current: List[Dict[str, str]],
    new_items: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    seen_urls = {item.get("url") for item in current}
    merged = list(current)

    for item in new_items:
        url = item.get("url")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        merged.append(item)

    return merged


def _build_quota_fallback_answer(
    message: str,
    tool_cache: Dict[str, Dict[str, Any]],
) -> str:
    if not tool_cache:
        return (
            "I was able to receive your request, but Gemini is temporarily over quota right now. "
            "Please retry in a few seconds, or switch to a lower-tier model such as "
            "`gemini-2.0-flash` in `server/.env`."
        )

    first_payload = next(iter(tool_cache.values()))
    query = first_payload.get("query") or message
    video_count = int(first_payload.get("video_count") or 0)
    transcript_count = int(first_payload.get("transcript_count") or 0)
    sources = first_payload.get("sources") or []

    lines = [
        "## Verdict",
        (
            f"I fetched fresh YouTube review research for **{query}**, but Gemini is currently over quota, "
            "so I cannot synthesize the full recommendation right now."
        ),
        "",
        "## What I was able to gather",
        f"- YouTube videos found: {video_count}",
        f"- Review transcripts extracted: {transcript_count}",
    ]

    if transcript_count == 0 and video_count > 0:
        lines.append("- Transcript access was limited, so only video metadata could be collected.")

    if sources:
        lines.extend(
            [
                "",
                "## Sources ready below",
                "- The linked YouTube reviews are attached in the UI and can still be opened immediately.",
            ]
        )

    lines.extend(
        [
            "",
            "## Next step",
            "- Retry in a few seconds, or change `GEMINI_MODEL` in `server/.env` to `gemini-2.0-flash` to reduce free-tier quota pressure.",
        ]
    )

    return "\n".join(lines)


def stream_shopper_reply(
    message: str, history: List[Dict[str, Any]]
) -> Iterator[Dict[str, Any]]:
    prepared_history = _to_chat_history(history, message)
    attempted_models = _candidate_models()
    tool_cache: Dict[str, Dict[str, Any]] = {}
    emitted_text = False
    used_tool = False
    active_model = ""
    assistant_sources: List[Dict[str, str]] = []
    last_error: Exception | None = None

    for index, model_name in enumerate(attempted_models):
        active_model = model_name
        attempt_emitted_text = False

        yield {
            "event": "status",
            "data": {
                "message": f"Agent is deciding whether fresh review research is needed with {model_name}..."
            },
        }

        try:
            model = _build_model(model_name, tools=[fetch_youtube_reviews])
            chat = model.start_chat(history=prepared_history)
            decision_response = chat.send_message(
                message,
                generation_config={"temperature": 0.4},
                tool_config={
                    "function_calling_config": {
                        "mode": "auto",
                    }
                },
            )
            function_calls = _extract_function_calls(decision_response)

            if not function_calls:
                direct_text = (getattr(decision_response, "text", "") or "").strip()
                if not direct_text:
                    last_error = RuntimeError("Gemini returned an empty response.")
                    if index < len(attempted_models) - 1:
                        continue
                    break

                yield {
                    "event": "status",
                    "data": {
                        "message": "Agent is answering from the existing shopping conversation..."
                    },
                }
                for text_chunk in _chunk_direct_text(direct_text):
                    attempt_emitted_text = True
                    yield {"event": "chunk", "data": {"text": text_chunk}}

                emitted_text = attempt_emitted_text
                break

            used_tool = True
            function_response_parts: List[protos.Part] = []
            combined_sources: List[Dict[str, str]] = []

            for function_call in function_calls:
                if function_call.name != TOOL_NAME:
                    continue

                function_args = _function_args(function_call)
                research_query = (
                    str(function_args.get("product_name") or message).strip() or message
                )
                cache_key = research_query.lower()

                if cache_key not in tool_cache:
                    yield {
                        "event": "status",
                        "data": {"message": f"Agent is searching YouTube for: {research_query}"},
                    }
                    yield {
                        "event": "status",
                        "data": {
                            "message": "Agent is watching YouTube reviews and extracting transcripts in parallel..."
                        },
                    }
                    tool_cache[cache_key] = fetch_youtube_reviews(research_query)

                tool_payload = tool_cache[cache_key]
                combined_sources = _merge_sources(
                    combined_sources,
                    tool_payload.get("sources", []),
                )
                function_response_parts.append(
                    protos.Part(
                        function_response=protos.FunctionResponse(
                            name=function_call.name,
                            response=tool_payload,
                        )
                    )
                )

            assistant_sources = combined_sources
            if assistant_sources:
                yield {
                    "event": "sources",
                    "data": {"items": assistant_sources},
                }

            if not function_response_parts:
                last_error = RuntimeError("Gemini requested an unsupported tool call.")
                if index < len(attempted_models) - 1:
                    continue
                break

            yield {
                "event": "status",
                "data": {"message": f"Agent is drafting your shopping verdict with {model_name}..."},
            }
            final_stream = chat.send_message(
                protos.Content(role="user", parts=function_response_parts),
                generation_config={"temperature": 0.4},
                tool_config={"function_calling_config": "none"},
                stream=True,
            )

            for chunk in final_stream:
                text = _safe_chunk_text(chunk)
                if not text:
                    continue
                attempt_emitted_text = True
                yield {"event": "chunk", "data": {"text": text}}

            if attempt_emitted_text:
                emitted_text = True
                break

            last_error = RuntimeError("Gemini returned an empty response after tool execution.")
            if index < len(attempted_models) - 1:
                continue
        except Exception as exc:
            last_error = exc
            if _is_model_not_found(exc) and index < len(attempted_models) - 1:
                yield {
                    "event": "status",
                    "data": {
                        "message": (
                            f"Configured model {model_name} is unavailable. "
                            "Retrying with the next supported Gemini model..."
                        )
                    },
                }
                continue
            if _is_quota_exhausted(exc) and index < len(attempted_models) - 1:
                yield {
                    "event": "status",
                    "data": {
                        "message": (
                            f"Model quota for {model_name} is exhausted. "
                            "Retrying with the next configured Gemini model..."
                        )
                    },
                }
                continue
            raise

    if not emitted_text and _is_quota_exhausted(last_error or Exception()):
        fallback_answer = _build_quota_fallback_answer(message, tool_cache)
        for text_chunk in _chunk_direct_text(fallback_answer):
            yield {"event": "chunk", "data": {"text": text_chunk}}
        emitted_text = True

    if not emitted_text:
        error_message = (
            str(last_error) if last_error else "Gemini returned an empty response."
        )
        yield {
            "event": "error",
            "data": {"message": error_message},
        }

    yield {
        "event": "done",
        "data": {
            "ok": emitted_text,
            "used_tool": used_tool,
            "source_count": len(assistant_sources),
            "model": active_model,
        },
    }
