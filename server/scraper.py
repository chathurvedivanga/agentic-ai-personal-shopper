from __future__ import annotations

import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtubesearchpython import VideosSearch

try:
    from youtube_transcript_api import (
        CouldNotRetrieveTranscript,
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
    )
except ImportError:  # pragma: no cover - compatibility fallback
    from youtube_transcript_api._errors import (  # type: ignore[attr-defined]
        CouldNotRetrieveTranscript,
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
    )

SKIPPABLE_ERRORS = (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)
MAX_TRANSCRIPT_CHARS = 2800
SEARCH_CANDIDATE_LIMIT = 12
TARGET_TRANSCRIPT_RESULTS = 4

SEARCH_STOPWORDS = {
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
    "is",
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

INDIA_MARKET_TERMS = ("india", "indian", "inr", "rs", "rupees", "flipkart", "amazon india")


def _normalize_query(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9$+\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _strip_foreign_budget_terms(text: str) -> str:
    stripped = re.sub(r"under\s+\$\s*\d[\d,]*", "", text)
    stripped = re.sub(r"\$\s*\d[\d,]*", "", stripped)
    stripped = re.sub(r"\b\d[\d,]*\s*usd\b", "", stripped)
    stripped = re.sub(r"\b\d[\d,]*\s*dollars?\b", "", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped


def _derive_search_queries(query: str) -> List[str]:
    normalized = _normalize_query(query)
    normalized_without_foreign_budget = _strip_foreign_budget_terms(normalized)
    tokens = [token for token in normalized.split() if token not in SEARCH_STOPWORDS]
    concise = " ".join(tokens).strip()
    concise = re.sub(r"\s+", " ", concise)
    if normalized_without_foreign_budget and normalized_without_foreign_budget != normalized:
        concise_without_foreign_budget = " ".join(
            token
            for token in normalized_without_foreign_budget.split()
            if token not in SEARCH_STOPWORDS
        ).strip()
    else:
        concise_without_foreign_budget = ""
    year = datetime.now().year
    has_india_context = any(term in normalized for term in INDIA_MARKET_TERMS)
    india_suffix = " india" if not has_india_context else ""

    variants = [
        f"{normalized}{india_suffix}",
        f"{normalized}{india_suffix} review",
        f"{normalized}{india_suffix} comparison",
        f"{normalized}{india_suffix} buyer guide",
        f"{normalized}{india_suffix} {year}",
    ]

    if concise and concise != normalized:
        variants.extend(
            [
                f"{concise}{india_suffix} review",
                f"{concise}{india_suffix} comparison",
                f"best {concise}{india_suffix} review",
                f"best {concise}{india_suffix} {year}",
            ]
        )

    if normalized_without_foreign_budget and normalized_without_foreign_budget != normalized:
        variants.extend(
            [
                f"{normalized_without_foreign_budget}{india_suffix} review",
                f"{normalized_without_foreign_budget}{india_suffix} comparison",
                f"{normalized_without_foreign_budget}{india_suffix} {year}",
            ]
        )

    if concise_without_foreign_budget:
        variants.extend(
            [
                f"{concise_without_foreign_budget}{india_suffix} review",
                f"best {concise_without_foreign_budget}{india_suffix} {year}",
            ]
        )

    deduped: List[str] = []
    for variant in variants:
        cleaned = re.sub(r"\s+", " ", variant).strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)

    return deduped[:4]


def _to_video_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    video_id = item.get("id")
    if not video_id:
        return None

    channel = item.get("channel") or {}
    return {
        "video_id": video_id,
        "title": item.get("title") or "Untitled video",
        "channel": channel.get("name") if isinstance(channel, dict) else "",
        "url": item.get("link") or f"https://www.youtube.com/watch?v={video_id}",
    }


def search_youtube_videos(query: str, limit: int = SEARCH_CANDIDATE_LIMIT) -> List[Dict[str, Any]]:
    search_queries = _derive_search_queries(query)
    videos: List[Dict[str, Any]] = []
    seen_ids = set()

    for search_query in search_queries:
        try:
            raw_results = VideosSearch(search_query, limit=max(limit, 6)).result().get(
                "result", []
            )
        except Exception:
            continue

        for item in raw_results:
            video = _to_video_item(item)
            if not video or video["video_id"] in seen_ids:
                continue
            seen_ids.add(video["video_id"])
            videos.append(video)
            if len(videos) >= limit:
                return videos

    return videos


def _truncate_transcript(entries: List[Dict[str, Any]]) -> str:
    transcript = " ".join(
        segment.get("text", "").replace("\n", " ").strip() for segment in entries
    )
    transcript = " ".join(transcript.split())
    if len(transcript) <= MAX_TRANSCRIPT_CHARS:
        return transcript

    head_budget = int(MAX_TRANSCRIPT_CHARS * 0.65)
    tail_budget = MAX_TRANSCRIPT_CHARS - head_budget - len(" ... ")
    head = transcript[:head_budget].rsplit(" ", 1)[0].strip()
    tail = transcript[-tail_budget:].split(" ", 1)[-1].strip()
    if not head or not tail:
        return transcript[:MAX_TRANSCRIPT_CHARS]
    return f"{head} ... {tail}"


def _normalize_transcript_entries(entries: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []

    for entry in entries:
        if isinstance(entry, dict):
            normalized.append(entry)
            continue

        text = getattr(entry, "text", "")
        start = getattr(entry, "start", 0.0)
        duration = getattr(entry, "duration", 0.0)
        normalized.append(
            {
                "text": text,
                "start": start,
                "duration": duration,
            }
        )

    return normalized


def _fetch_with_fallbacks(api: YouTubeTranscriptApi, video_id: str) -> Any:
    try:
        return api.fetch(video_id, languages=["en", "en-US"])
    except SKIPPABLE_ERRORS:
        pass

    transcript_list = api.list(video_id)

    for method_name in (
        "find_transcript",
        "find_manually_created_transcript",
        "find_generated_transcript",
    ):
        finder = getattr(transcript_list, method_name, None)
        if not finder:
            continue
        try:
            return finder(["en", "en-US"]).fetch()
        except SKIPPABLE_ERRORS:
            continue
        except Exception:
            continue

    transcripts = list(_iterate_transcripts(transcript_list))
    for transcript in transcripts:
        try:
            if getattr(transcript, "is_translatable", False):
                return transcript.translate("en").fetch()
        except Exception:
            continue

    for transcript in transcripts:
        try:
            return transcript.fetch()
        except Exception:
            continue

    raise RuntimeError(f"No usable transcript found for {video_id}")


def _iterate_transcripts(transcript_list: Any) -> Iterable[Any]:
    try:
        yield from transcript_list
    except TypeError:
        return


def _fetch_video_transcript(video: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    video_id = video["video_id"]
    api = YouTubeTranscriptApi()

    try:
        if hasattr(api, "fetch"):
            transcript_entries = _fetch_with_fallbacks(api, video_id)
        else:
            transcript_entries = api.get_transcript(
                video_id,
                languages=["en", "en-US"],
            )
    except SKIPPABLE_ERRORS:
        return None
    except Exception:
        return None

    transcript = _truncate_transcript(_normalize_transcript_entries(transcript_entries))
    if not transcript:
        return None

    return {**video, "transcript": transcript}


def fetch_transcripts_parallel(
    videos: List[Dict[str, Any]], max_workers: int = 5, target_count: int = TARGET_TRANSCRIPT_RESULTS
) -> List[Dict[str, Any]]:
    if not videos:
        return []

    workers = max(1, min(max_workers, len(videos)))
    ordered_results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(_fetch_video_transcript, video): index
            for index, video in enumerate(videos)
        }

        for future in as_completed(future_map):
            index = future_map[future]
            item = future.result()
            if item is None:
                continue
            item["_order"] = index
            ordered_results.append(item)
            if len(ordered_results) >= target_count:
                break

    ordered_results.sort(key=lambda item: item["_order"])
    for item in ordered_results:
        item.pop("_order", None)

    return ordered_results[:target_count]
