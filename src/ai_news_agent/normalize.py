from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "source",
    "spm",
}

AI_KEYWORDS = {
    "agent",
    "agents",
    "agi",
    "ai",
    "aigc",
    "anthropic",
    "claude",
    "codex",
    "gemini",
    "glm",
    "gpt",
    "llm",
    "model",
    "openai",
    "qwen",
    "人工智能",
    "大模型",
    "多模态",
    "智能体",
    "模型",
}


def canonicalize_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    parts = urlsplit(value)
    scheme = (parts.scheme or "https").lower()
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    kept = []
    for key, val in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in TRACKING_QUERY_KEYS:
            continue
        kept.append((key, val))
    query = urlencode(sorted(kept))
    return urlunsplit((scheme, host, path, query, ""))


def normalize_title(value: str) -> str:
    value = (value or "").lower().strip()
    value = re.sub(r"[\s\u3000]+", "", value)
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value)


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    candidate = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        try:
            parsed = datetime.strptime(candidate[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _score(item: dict, edition_date: str) -> float:
    tier = int(item.get("source_tier", 3) or 3)
    authority = {1: 45.0, 2: 30.0, 3: 16.0}.get(tier, 8.0)
    editorial = {"P0": 30.0, "P1": 15.0, "P2": 0.0}.get(
        str(item.get("editorial_priority", "")).upper(), 0.0
    )
    text = " ".join(
        [
            str(item.get("title", "")),
            str(item.get("summary", "")),
            " ".join(item.get("tags", [])),
        ]
    ).lower()
    relevance = min(25.0, sum(4.0 for keyword in AI_KEYWORDS if keyword in text))
    evidence = min(16.0, 4.0 * len(set(item.get("evidence_urls", []))))
    original = 8.0 if item.get("is_primary_source") else 0.0
    published = _parse_time(str(item.get("published_at", "")))
    edition = _parse_time(edition_date)
    recency = 0.0
    if published and edition:
        age_hours = max(0.0, (edition - published).total_seconds() / 3600.0)
        recency = max(0.0, 18.0 - age_hours / 4.0)
    return round(authority + editorial + relevance + evidence + original + recency, 2)


def _is_duplicate(left: dict, right: dict) -> bool:
    if left["canonical_url"] and left["canonical_url"] == right["canonical_url"]:
        return True
    a = left["normalized_title"]
    b = right["normalized_title"]
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        return min(len(a), len(b)) >= 12
    return SequenceMatcher(None, a, b).ratio() >= 0.82


def _merge(target: dict, incoming: dict) -> dict:
    merged = copy.deepcopy(target)
    merged["evidence_urls"] = sorted(
        {
            canonicalize_url(url)
            for url in target.get("evidence_urls", []) + incoming.get("evidence_urls", [])
            if url
        }
    )
    merged["discovery_urls"] = sorted(
        {
            canonicalize_url(url)
            for url in target.get("discovery_urls", []) + incoming.get("discovery_urls", [])
            if url
        }
    )
    merged["source_names"] = sorted(
        set(target.get("source_names", [])) | set(incoming.get("source_names", []))
    )
    merged["tags"] = sorted(set(target.get("tags", [])) | set(incoming.get("tags", [])))
    if int(incoming.get("source_tier", 3)) < int(target.get("source_tier", 3)):
        for key in ("title", "summary", "published_at", "source_tier", "is_primary_source"):
            merged[key] = incoming.get(key, merged.get(key))
        merged["url"] = incoming.get("url", merged.get("url"))
        merged["canonical_url"] = incoming.get("canonical_url", merged.get("canonical_url"))
    return merged


def normalize_and_rank(seed: dict, max_selected: int = 30) -> list[dict]:
    edition_date = str(seed.get("edition_date", ""))
    prepared: list[dict] = []
    for index, raw in enumerate(seed.get("items", []), start=1):
        item = copy.deepcopy(raw)
        item.setdefault("id", f"candidate-{index:03d}")
        item.setdefault("summary", "")
        item.setdefault("published_at", "")
        item.setdefault("source_name", "unknown")
        item.setdefault("source_tier", 3)
        item.setdefault("tags", [])
        item.setdefault("is_primary_source", False)
        item["url"] = canonicalize_url(str(item.get("url", "")))
        item["canonical_url"] = item["url"]
        item["normalized_title"] = normalize_title(str(item.get("title", "")))
        item["source_names"] = [str(item.get("source_name", "unknown"))]
        item["discovery_urls"] = [
            canonicalize_url(url) for url in item.get("discovery_urls", []) if url
        ]
        evidence = item.get("evidence_urls") or ([item["url"]] if item["url"] else [])
        item["evidence_urls"] = sorted({canonicalize_url(url) for url in evidence if url})
        prepared.append(item)

    groups: list[dict] = []
    for item in prepared:
        for pos, existing in enumerate(groups):
            if _is_duplicate(item, existing):
                groups[pos] = _merge(existing, item)
                break
        else:
            groups.append(item)

    for item in groups:
        item["score"] = _score(item, edition_date)
    groups.sort(key=lambda value: (-value["score"], value["normalized_title"]))
    for rank, item in enumerate(groups[:max_selected], start=1):
        item["candidate_rank"] = rank
    return groups[:max_selected]
