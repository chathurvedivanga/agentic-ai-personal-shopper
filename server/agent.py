from __future__ import annotations

import asyncio
import json
import os
import re
import time
from threading import Lock
from typing import Any, Dict, Iterator, List

import google.generativeai as genai
import httpx
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
- For budget recommendation requests, recommend 3-5 specific product models with approximate India prices whenever possible. Do not answer with only broad brands or series names.
- Prefer evidence from supplied YouTube review transcripts whenever they exist.
- If videos were found but transcripts were inaccessible, say that transcript access failed or subtitles were unavailable. Do not say the videos were unavailable.
- If fresh transcript evidence is unavailable, still provide a best-effort shortlist using the available review metadata and stable product knowledge.
- If the category is ambiguous enough to produce generic advice, ask one short clarifying question before recommending. For example, clarify whether "watch" means smartwatch or analog watch.
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
TITLE_MAX_LENGTH = 56
MAX_HISTORY_MESSAGES = 10
TOOL_NAME = "fetch_youtube_reviews"
DIRECT_RESPONSE_CHUNK_SIZE = 220
RESEARCH_CACHE_TTL_SECONDS = 30 * 60
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
#
GROQ_TIMEOUT_SECONDS = 10.0
OPENROUTER_APP_TITLE = "AI Shopping Partner"

LAYER1_AGENTS = {
    "critic": {
        "model": "openai/gpt-oss-20b",
        "prompt": (
            "You are a critical product reviewer. Read the transcript and query. "
            "In one short paragraph, highlight only the major flaws, missing features, "
            "or concerns."
        ),
    },
    "summarizer": {
        "model": "qwen/qwen3-32b",
        "prompt": (
            "You are a product summarizer. Read the transcript and query. "
            "Output a concise bulleted list of the top 3 best features mentioned. "
            "Return ONLY the bulleted list."
        ),
    },
    "extractor": {
        "model": "llama-3.1-8b-instant",
        "prompt": (
            "You are a strict data extractor. Read the transcript, query, and video metadata. "
            "Extract EVERY technical specification, brand, model, and hard fact mentioned. "
            "Be exhaustive. If transcripts are missing or thin, use the video titles and channel "
            "metadata to extract as much information as possible.\n"
            "Return ONLY a valid JSON object. Do not include markdown formatting. "
            "Keep values concise. Do not guess; only include what is explicitly stated."
        ),
    },
}

FAST_PATH_RESEARCH_CUES = (
    "recommend",
    "best",
    "under",
    "buy",
    "budget",
    "vs",
    "versus",
    "compare",
    "comparison",
    "shortlist",
    "top",
    "which should i buy",
    "looking for",
    "need a",
)

FOLLOW_UP_RESEARCH_CUES = (
    "first one",
    "second one",
    "third one",
    "that one",
    "those",
    "these",
    "battery",
    "camera",
    "display",
    "performance",
    "software",
    "thermals",
    "charger",
    "charging",
    "durability",
    "which one",
    "what about",
    "how is",
    "how's",
)

WATCH_AMBIGUITY_PATTERN = re.compile(r"\bwatches?\b")
WATCH_TYPE_PATTERN = re.compile(
    r"\b(smart ?watch|analog watch|analogue watch|mechanical watch|digital watch|fitness watch)\b"
)

_RESEARCH_CACHE: Dict[str, Dict[str, Any]] = {}
_RESEARCH_CACHE_LOCK = Lock()
TITLE_STOPWORDS = {
    "a",
    "an",
    "best",
    "buy",
    "can",
    "find",
    "for",
    "help",
    "i",
    "im",
    "i'm",
    "in",
    "india",
    "indian",
    "looking",
    "me",
    "need",
    "please",
    "recommend",
    "search",
    "show",
    "suggest",
    "the",
    "to",
    "want",
    "what",
    "which",
    "with",
}
VAGUE_TITLE_TERMS = {
    "chat",
    "help",
    "options",
    "partner",
    "personal",
    "product",
    "recommendations",
    "review",
    "reviews",
    "shopper",
    "shopping",
    "suggestions",
}
TITLE_BRAND_CASE_MAP = {
    "bgmi": "BGMI",
    "flipkart": "Flipkart",
    "g-shock": "G-Shock",
    "iphone": "iPhone",
    "iqoo": "iQOO",
    "macbook": "MacBook",
    "oneplus": "OnePlus",
    "poco": "POCO",
    "redmi": "Redmi",
    "realme": "realme",
}
LEADING_TITLE_FILLER = re.compile(
    r"^(?:can you|could you|help me|i need|i want to buy|i want|i am looking for|i'm looking for|looking for|please|recommend|suggest|show me|what is|which is|find me|best)\s+",
    re.IGNORECASE,
)
COMPARE_PATTERN = re.compile(r"\b(?:vs\.?|versus|compare(?: with| to)?)\b", re.IGNORECASE)
BUDGET_UNDER_PATTERN = re.compile(
    r"\b(?:under|below|less than)\s*(?:rs\.?|₹|rupees?)?\s*(\d[\d,]*)\b",
    re.IGNORECASE,
)
BUDGET_AROUND_PATTERN = re.compile(
    r"\b(?:around|about|near)\s*(?:rs\.?|₹|rupees?)?\s*(\d[\d,]*)\b",
    re.IGNORECASE,
)


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


def _format_indian_number_for_title(value: int) -> str:
    digits = str(abs(value))
    if len(digits) <= 3:
        grouped = digits
    else:
        grouped = digits[-3:]
        digits = digits[:-3]
        while digits:
            grouped = f"{digits[-2:]},{grouped}"
            digits = digits[:-2]
    return f"-{grouped}" if value < 0 else grouped


def _title_case_token_for_title(token: str) -> str:
    stripped = token.strip()
    if not stripped:
        return token

    lower = stripped.lower()
    if lower in TITLE_BRAND_CASE_MAP:
        return TITLE_BRAND_CASE_MAP[lower]
    if stripped.startswith("Rs "):
        return stripped
    if any(char.isdigit() for char in stripped):
        return stripped.upper() if len(stripped) <= 4 else stripped
    return stripped.title()


def _smart_title_case_for_title(text: str) -> str:
    tokens = re.split(r"(\s+)", text)
    return "".join(
        token if token.isspace() else _title_case_token_for_title(token)
        for token in tokens
    ).strip()


def _normalize_budget_phrase_for_title(raw_value: str) -> str:
    digits = re.sub(r"[^\d]", "", raw_value or "")
    if not digits:
        return ""
    return f"Rs {_format_indian_number_for_title(int(digits))}"


def _extract_budget_phrase_for_title(text: str) -> str:
    under_match = BUDGET_UNDER_PATTERN.search(text or "")
    if under_match:
        budget = _normalize_budget_phrase_for_title(under_match.group(1))
        if budget:
            return f"Under {budget}"

    around_match = BUDGET_AROUND_PATTERN.search(text or "")
    if around_match:
        budget = _normalize_budget_phrase_for_title(around_match.group(1))
        if budget:
            return f"Around {budget}"

    return ""


def _extract_compare_title_for_title(seed_text: str) -> str:
    parts = COMPARE_PATTERN.split(seed_text or "", maxsplit=1)
    if len(parts) != 2:
        return ""

    left = re.sub(r"[^\w\s.+-]", " ", parts[0]).strip()
    right = re.sub(r"[^\w\s.+-]", " ", parts[1]).strip()
    left = LEADING_TITLE_FILLER.sub("", left).strip()
    right = re.sub(r"\b(in india|india)\b", "", right, flags=re.IGNORECASE).strip()
    if not left or not right:
        return ""

    combined = (
        f"{_smart_title_case_for_title(left)} vs "
        f"{_smart_title_case_for_title(right)}"
    )
    return combined[:TITLE_MAX_LENGTH].strip()


def draft_chat_title(seed_text: str, assistant_text: str = "") -> str:
    compare_title = _extract_compare_title_for_title(seed_text)
    if compare_title:
        return compare_title

    base_text = seed_text or ""
    assistant_lower = assistant_text.lower()
    if assistant_lower and WATCH_AMBIGUITY_PATTERN.search(base_text) and WATCH_TYPE_PATTERN.search(
        assistant_lower
    ):
        watch_type_match = WATCH_TYPE_PATTERN.search(assistant_lower)
        if watch_type_match:
            base_text = re.sub(
                r"\bwatches?\b",
                watch_type_match.group(1),
                base_text,
                count=1,
                flags=re.IGNORECASE,
            )

    budget_phrase = _extract_budget_phrase_for_title(base_text)
    cleaned = re.sub(r"[^\w\s₹.+/-]", " ", base_text)
    cleaned = LEADING_TITLE_FILLER.sub("", cleaned).strip()
    cleaned = re.sub(
        r"\b(in india|india|indian market)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = BUDGET_UNDER_PATTERN.sub(" ", cleaned)
    cleaned = BUDGET_AROUND_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(
        r"(?:₹|rs\.?|rupees?)\s*\d[\d,]*",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    words = [
        word
        for word in cleaned.split()
        if word.lower() not in TITLE_STOPWORDS and len(word) > 1
    ]

    if re.search(r"\bcompar", cleaned, flags=re.IGNORECASE) and words:
        lead = _smart_title_case_for_title(" ".join(words[:2]))
        if "chip" in cleaned.lower() and not re.search(r"\bchip\b", lead, flags=re.IGNORECASE):
            lead = f"{lead} Chip"
        title = f"{lead} Comparison"
        return title[:TITLE_MAX_LENGTH].strip()

    if not words:
        return budget_phrase or "New chat"

    lead_words = words[:4]
    lead = _smart_title_case_for_title(" ".join(lead_words))
    title = f"{lead} {budget_phrase}".strip() if budget_phrase else lead
    title = re.sub(r"\s+", " ", title).strip()
    return title[:TITLE_MAX_LENGTH].strip() or "New chat"


def _is_vague_generated_title(title: str) -> bool:
    normalized_words = [word.lower() for word in re.findall(r"[a-zA-Z0-9+/-]+", title)]
    if not normalized_words:
        return True
    if len(normalized_words) == 1 and normalized_words[0] in VAGUE_TITLE_TERMS:
        return True
    if all(word in VAGUE_TITLE_TERMS for word in normalized_words):
        return True
    return False


def _clean_generated_chat_title(
    raw_text: str,
    seed_text: str,
    assistant_text: str = "",
) -> str:
    title = raw_text.strip().splitlines()[0].strip()
    title = title.strip("`\"'*-: ")
    title = re.sub(r"\s+", " ", title)
    title = title.replace("₹", "Rs ")
    title = _smart_title_case_for_title(title)
    fallback = draft_chat_title(seed_text, assistant_text)
    if not title or _is_vague_generated_title(title):
        return fallback
    return title[:TITLE_MAX_LENGTH].strip() or fallback


def generate_chat_title(
    seed_text: str,
    assistant_text: str = "",
    source_titles: List[str] | None = None,
) -> str:
    fallback = draft_chat_title(seed_text, assistant_text)
    source_titles = source_titles or []
    assistant_excerpt = re.sub(r"\s+", " ", assistant_text).strip()[:700]
    source_block = "\n".join(f"- {title}" for title in source_titles[:4]) or "- None"
    prompt = f"""
Create a short, specific title for this shopping conversation sidebar.

Requirements:
- 3 to 7 words
- title case
- no quotes
- no punctuation unless needed for a product name
- focus on the actual buyer intent, product category, and budget if present
- prefer specific category phrases over vague labels like Shopping, Help, Recommendations, or Chat
- if this is a comparison, use a title like "Product A vs Product B"
- if a budget exists, include it in the title
- avoid filler words like recommend, suggest, help, best, and buy

Examples:
- User: Recommend a gaming phone under Rs 40000 in India
  Title: Gaming Phones Under Rs 40,000
- User: Best smartwatches under 5000
  Title: Smartwatches Under Rs 5,000
- User: MacBook chip comparison for college
  Title: MacBook Chip Comparison
- User: Robot vacuum for pet hair in India
  Title: Robot Vacuums for Pet Hair

User message:
{seed_text}

Assistant answer excerpt:
{assistant_excerpt or "None"}

YouTube review titles:
{source_block}

Fallback candidate:
{fallback}

Return only the title.
""".strip()

    for model_name in _candidate_models():
        try:
            model = _build_model(
                model_name,
                system_instruction="You create concise and specific shopping chat titles.",
            )
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.0,
                    "max_output_tokens": 20,
                },
            )
            return _clean_generated_chat_title(
                getattr(response, "text", "") or "",
                seed_text,
                assistant_text,
            )
        except Exception as exc:
            if _is_model_not_found(exc) or _is_quota_exhausted(exc):
                continue
            break

    return fallback


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

    cached = _get_cached_research(query)
    if cached is not None:
        return cached

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
    payload = {
        "query": query,
        "video_count": len(videos),
        "transcript_count": len(research_items),
        "research_note": research_note,
        "research_context": _format_research_context(research_items, research_note),
        "video_search_results": _format_video_candidates(videos),
        "sources": source_items,
        "cache_hit": False,
    }
    _store_cached_research(query, payload)
    return payload


def _format_history_for_moa(history: List[Dict[str, Any]]) -> str:
    if not history:
        return "No prior conversation."

    lines: List[str] = []
    for item in history[-MAX_HISTORY_MESSAGES:]:
        role = (item.get("role") or "user").strip().lower()
        content = re.sub(r"\s+", " ", (item.get("content") or "").strip())
        if not content:
            continue
        label = "Assistant" if role == "assistant" else "User"
        lines.append(f"{label}: {content[:900]}")

    return "\n".join(lines) if lines else "No prior conversation."


def _build_layer1_user_payload(
    query: str,
    research_payload: Dict[str, Any],
    history: List[Dict[str, Any]],
) -> str:
    research_context = (research_payload.get("research_context") or "").strip()
    if not research_context:
        research_context = research_payload.get("research_note") or "No transcript context was available."

    video_results = research_payload.get("video_search_results") or "No video metadata was available."
    return f"""
User query:
{query}

Recent conversation:
{_format_history_for_moa(history)}

YouTube transcript evidence and notes:
{research_context}

YouTube video metadata:
{video_results}
""".strip()


def _build_history_research_payload(
    query: str,
    history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    assistant_context = "\n\n".join(
        (item.get("content") or "").strip()
        for item in history[-MAX_HISTORY_MESSAGES:]
        if (item.get("role") or "").strip().lower() == "assistant"
        and (item.get("content") or "").strip()
    )
    if not assistant_context:
        assistant_context = "No prior assistant recommendation is available."

    return {
        "query": query,
        "video_count": 0,
        "transcript_count": 0,
        "research_note": (
            "No fresh YouTube search was run because this message appears to be a "
            "follow-up or does not yet contain a clear new shopping research target."
        ),
        "research_context": f"Existing conversation context:\n{assistant_context}",
        "video_search_results": "Fresh YouTube video search was skipped for this turn.",
        "sources": [],
        "cache_hit": False,
        "fresh_search": False,
    }


async def _call_groq_agent(
    client: httpx.AsyncClient,
    agent_name: str,
    agent_config: Dict[str, str],
    user_payload: str,
    max_retries: int = 3,
    response_format: Dict[str, Any] | None = None,
) -> str:
    api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        return (
            "Groq API key is not configured, so this Layer 1 agent could not run. "
            "Add GROQ_API_KEY in Render and server/.env to enable the full MoA debate."
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": agent_config["model"],
        "messages": [
            {"role": "system", "content": agent_config["prompt"]},
            {"role": "user", "content": user_payload},
        ],
        "temperature": 0.0,
        "max_tokens": 700,
    }
    if response_format:
        payload["response_format"] = response_format

    last_status = 0
    for attempt in range(max_retries):
        try:
            response = await client.post(GROQ_API_URL, headers=headers, json=payload)
            
            if response.status_code == 429:
                last_status = 429
                # Exponential backoff: 2s, 4s, 8s...
                wait_time = 2.0 * (2 ** attempt)
                await asyncio.sleep(wait_time)
                continue

            response.raise_for_status()
            data = response.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            
            # Robustly strip internal reasoning blocks (e.g. <think>...</think>)
            if content:
                stripped = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
                if not stripped and content.strip():
                     return f"{agent_name.title()} output was entirely removed by the reasoning filter. Raw response: {content[:200]}..."
                content = stripped

            return content or f"{agent_name.title()} returned an empty response."
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                continue
            return f"{agent_name.title()} timed out after {int(GROQ_TIMEOUT_SECONDS)} seconds."
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                continue
            return f"{agent_name.title()} failed with Groq HTTP {exc.response.status_code}."
        except Exception as exc:
            return f"{agent_name.title()} failed: {str(exc) or 'Unknown Groq error.'}"

    if last_status == 429:
        return f"{agent_name.title()} failed with Groq HTTP 429 after {max_retries} attempts. Rate limit exceeded."
    return f"{agent_name.title()} failed after {max_retries} attempts."


def _strip_json_markdown(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1]
    return text


def _parse_extractor_json(raw_text: str) -> Dict[str, Any]:
    cleaned = _strip_json_markdown(raw_text)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}
    except json.JSONDecodeError:
        return {
            "raw": (raw_text or "").strip(),
            "parse_error": "Extractor did not return valid JSON.",
        }


async def _run_layer1_agents(
    query: str,
    research_payload: Dict[str, Any],
    history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    user_payload = _build_layer1_user_payload(query, research_payload, history)
    timeout = httpx.Timeout(GROQ_TIMEOUT_SECONDS)

    async with httpx.AsyncClient(timeout=timeout) as client:
        critic = await _call_groq_agent(
            client,
            "critic",
            LAYER1_AGENTS["critic"],
            user_payload,
        )
        await asyncio.sleep(1.0)
        summarizer = await _call_groq_agent(
            client,
            "summarizer",
            LAYER1_AGENTS["summarizer"],
            user_payload,
        )
        await asyncio.sleep(1.0)
        extractor_raw = await _call_groq_agent(
            client,
            "extractor",
            LAYER1_AGENTS["extractor"],
            user_payload,
            response_format={"type": "json_object"},
        )

    return {
        "critic": critic,
        "summarizer": summarizer,
        "extractor": _parse_extractor_json(extractor_raw),
        "extractor_raw": extractor_raw,
    }


def _build_moa_synthesis_prompt(
    query: str,
    research_payload: Dict[str, Any],
    layer1: Dict[str, Any],
    history: List[Dict[str, Any]],
) -> str:
    extractor_json = json.dumps(layer1.get("extractor") or {}, indent=2, ensure_ascii=False)
    sources = research_payload.get("sources") or []
    source_lines = "\n".join(
        f"- {source.get('channel') or 'YouTube'}: {source.get('title')} ({source.get('url')})"
        for source in sources[:8]
    )

    return f"""
Act as the final shopping synthesizer.

Review the user query and the following agent analyses. Resolve contradictions, prefer transcript-backed evidence, and write a final, highly polished product recommendation formatted in Markdown.

Rules:
- Default to Indian buyers and Indian rupees.
- Recommend specific product models, not only broad brands.
- Keep the answer practical, concise, and buyer-friendly.
- Use Markdown headings and bullets. Avoid wide Markdown tables because the chat UI is narrow.
- Start with "## Verdict".
- Include recurring reviewer/user feedback naturally inside the recommendation.
- If transcripts were unavailable, be transparent that YouTube search happened but transcript access was limited.
- Do not create a separate "YouTube Links" section; the UI renders source links separately.
- For multiple products, use a "## Quick compare" section with one compact subsection per model.

User query:
{query}

Recent conversation:
{_format_history_for_moa(history)}

YouTube research note:
{research_payload.get("research_note") or "No research note available."}

YouTube sources:
{source_lines or "No source links available."}

Layer 1 critic:
{layer1.get("critic") or "No critic output."}

Layer 1 summarizer:
{layer1.get("summarizer") or "No summarizer output."}

Layer 1 extractor JSON:
{extractor_json}
""".strip()


async def _synthesize_moa_with_gemini(
    query: str,
    research_payload: Dict[str, Any],
    layer1: Dict[str, Any],
    history: List[Dict[str, Any]],
) -> tuple[str, str]:
    prompt = _build_moa_synthesis_prompt(query, research_payload, layer1, history)
    last_error: Exception | None = None

    for model_name in _candidate_models():
        try:
            model = _build_model(
                model_name,
                system_instruction=(
                    "You are an expert final shopping synthesizer. You combine multiple "
                    "agent analyses into one accurate, polished recommendation."
                ),
            )
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.35},
            )
            text = (getattr(response, "text", "") or "").strip()
            if text:
                return text, model_name
            last_error = RuntimeError(f"{model_name} returned an empty synthesis.")
        except Exception as exc:
            last_error = exc
            if _is_model_not_found(exc) or _is_quota_exhausted(exc):
                continue
            raise

    if _is_quota_exhausted(last_error or Exception()):
        return (
            "## Verdict\n\n"
            "The research agents completed their work, but Gemini is currently over quota, "
            "so the final synthesis could not be generated. Please retry after the quota "
            "window resets or switch to a Gemini model with available quota.\n\n"
            "## Agent outputs available\n\n"
            "Open **Behind the Scenes: AI Agent Debate** below to inspect the Critic, "
            "Summarizer, and Extractor results that were collected.",
            "",
        )

    raise RuntimeError(str(last_error) if last_error else "Gemini synthesis failed.")


async def run_moa_shopper_reply(
    message: str,
    history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Run the two-layer Mixture-of-Agents shopping pipeline.

    Layer 0 gathers YouTube review evidence with parallel transcript extraction.
    Layer 1 concurrently asks three specialized Groq models to critique,
    summarize, and extract objective specs from that evidence.
    Layer 2 asks Gemini to resolve the agent outputs into one polished answer.
    """

    cleaned_message = re.sub(r"\s+", " ", (message or "").strip())
    if not cleaned_message:
        raise ValueError("A non-empty message is required.")

    should_fetch_fresh_research = _should_fast_path_research(cleaned_message, history)
    if should_fetch_fresh_research:
        research_payload = await asyncio.to_thread(fetch_youtube_reviews, cleaned_message)
        research_payload["fresh_search"] = True
    else:
        research_payload = _build_history_research_payload(cleaned_message, history)

    layer1 = await _run_layer1_agents(cleaned_message, research_payload, history)
    final_recommendation, synthesis_model = await _synthesize_moa_with_gemini(
        cleaned_message,
        research_payload,
        layer1,
        history,
    )

    return {
        "final_recommendation": final_recommendation,
        "agent_breakdown": {
            "critic": layer1.get("critic") or "",
            "summarizer": layer1.get("summarizer") or "",
            "extractor": layer1.get("extractor") or {},
        },
        "agent_breakdown_raw": {
            "extractor": layer1.get("extractor_raw") or "",
        },
        "sources": research_payload.get("sources") or [],
        "research": {
            "query": research_payload.get("query") or cleaned_message,
            "video_count": research_payload.get("video_count") or 0,
            "transcript_count": research_payload.get("transcript_count") or 0,
            "research_note": research_payload.get("research_note") or "",
            "cache_hit": bool(research_payload.get("cache_hit")),
            "fresh_search": bool(research_payload.get("fresh_search")),
        },
        "models": {
            "critic": LAYER1_AGENTS["critic"]["model"],
            "summarizer": LAYER1_AGENTS["summarizer"]["model"],
            "extractor": LAYER1_AGENTS["extractor"]["model"],
            "synthesizer": synthesis_model,
        },
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


def _get_tool_payload(
    research_query: str,
    tool_cache: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    cache_key = research_query.lower()
    if cache_key not in tool_cache:
        tool_cache[cache_key] = fetch_youtube_reviews(research_query)
    return tool_cache[cache_key]


def _function_response_part(function_name: str, payload: Dict[str, Any]) -> protos.Part:
    clean_payload = dict(payload)
    clean_payload.pop("cache_hit", None)
    return protos.Part(
        function_response=protos.FunctionResponse(
            name=function_name,
            response=clean_payload,
        )
    )


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


def _normalize_cache_key(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").strip().lower())


def _get_cached_research(query: str) -> Dict[str, Any] | None:
    cache_key = _normalize_cache_key(query)
    if not cache_key:
        return None

    now = time.time()
    with _RESEARCH_CACHE_LOCK:
        cached = _RESEARCH_CACHE.get(cache_key)
        if not cached:
            return None
        if cached["expires_at"] <= now:
            _RESEARCH_CACHE.pop(cache_key, None)
            return None

        payload = dict(cached["payload"])
        payload["cache_hit"] = True
        return payload


def _store_cached_research(query: str, payload: Dict[str, Any]) -> None:
    cache_key = _normalize_cache_key(query)
    if not cache_key:
        return

    cache_payload = dict(payload)
    cache_payload.pop("cache_hit", None)
    with _RESEARCH_CACHE_LOCK:
        _RESEARCH_CACHE[cache_key] = {
            "expires_at": time.time() + RESEARCH_CACHE_TTL_SECONDS,
            "payload": cache_payload,
        }


def _has_shopping_research_intent(message: str) -> bool:
    normalized = (message or "").strip().lower()
    if not normalized:
        return False

    if any(cue in normalized for cue in FAST_PATH_RESEARCH_CUES):
        return True

    return bool(
        re.search(r"\bunder\s*(?:rs|₹|\$|\d)", normalized)
        or re.search(r"\btop\s+\d", normalized)
        or " vs " in normalized
    )


def _is_ambiguous_category_request(message: str) -> bool:
    normalized = (message or "").strip().lower()
    if not normalized:
        return False

    return bool(
        WATCH_AMBIGUITY_PATTERN.search(normalized)
        and not WATCH_TYPE_PATTERN.search(normalized)
    )


def _looks_like_follow_up(message: str, history: List[Dict[str, Any]]) -> bool:
    if not any((item.get("role") or "").strip().lower() == "assistant" for item in history):
        return False

    normalized = (message or "").strip().lower()
    if not normalized:
        return False

    return any(cue in normalized for cue in FOLLOW_UP_RESEARCH_CUES)


def _should_fast_path_research(message: str, history: List[Dict[str, Any]]) -> bool:
    if not _has_shopping_research_intent(message):
        return False
    if _is_ambiguous_category_request(message):
        return False
    if _looks_like_follow_up(message, history):
        return False
    return True


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
    fast_path_tool_query = message if _should_fast_path_research(message, history) else ""

    for index, model_name in enumerate(attempted_models):
        active_model = model_name
        attempt_emitted_text = False

        if fast_path_tool_query:
            try:
                used_tool = True
                yield {
                    "event": "status",
                    "data": {
                        "message": f"Agent is searching YouTube for: {fast_path_tool_query}"
                    },
                }
                tool_payload = _get_tool_payload(fast_path_tool_query, tool_cache)
                yield {
                    "event": "status",
                    "data": {
                        "message": (
                            "Agent is reusing recent YouTube review research..."
                            if tool_payload.get("cache_hit")
                            else "Agent is watching YouTube reviews and extracting transcripts in parallel..."
                        )
                    },
                }
                assistant_sources = _merge_sources(
                    assistant_sources,
                    tool_payload.get("sources", []),
                )
                if assistant_sources:
                    yield {"event": "sources", "data": {"items": assistant_sources}}

                yield {
                    "event": "status",
                    "data": {
                        "message": f"Agent is drafting your shopping verdict with {model_name}..."
                    },
                }
                model = _build_model(model_name, tools=[fetch_youtube_reviews])
                history_with_message = [
                    *prepared_history,
                    protos.Content(role="user", parts=[protos.Part(text=message)]),
                ]
                chat = model.start_chat(history=history_with_message)
                final_stream = chat.send_message(
                    protos.Content(
                        role="user",
                        parts=[_function_response_part(TOOL_NAME, tool_payload)],
                    ),
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
                if research_query.lower() not in tool_cache:
                    yield {
                        "event": "status",
                        "data": {"message": f"Agent is searching YouTube for: {research_query}"},
                    }

                tool_payload = _get_tool_payload(research_query, tool_cache)
                yield {
                    "event": "status",
                    "data": {
                        "message": (
                            "Agent is reusing recent YouTube review research..."
                            if tool_payload.get("cache_hit")
                            else "Agent is watching YouTube reviews and extracting transcripts in parallel..."
                        )
                    },
                }
                combined_sources = _merge_sources(
                    combined_sources,
                    tool_payload.get("sources", []),
                )
                function_response_parts.append(
                    _function_response_part(function_call.name, tool_payload)
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
