from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urlsplit

from .normalize import canonicalize_url


MODEL_PHRASES = {
    "不可否认": "删除空泛的让步套话",
    "从某种意义上": "改成具体事实或判断",
    "需要指出的是": "直接写需要指出的事实",
    "值得注意的是": "直接写需要注意的事实",
    "赋能": "改成具体动作或收益",
    "抓手": "改成具体机制",
    "范式": "确认是否真的需要这个抽象词",
}

CONTRARIAN_PATTERNS = {
    r"不是.{0,50}而是": "禁用‘不是……而是……’翻案句",
    r"不在于.{0,50}而在于": "禁用‘不在于……而在于……’翻案句",
    r"与其.{0,50}不如": "禁用‘与其……不如……’翻案句",
}


def _strip_urls(text: str) -> str:
    return re.sub(r"https?://[^\s)\]>]+", "", text)


def _valid_http_url(value: str) -> bool:
    parts = urlsplit(value)
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


def collect_evidence_urls(bundle: dict) -> set[str]:
    urls: set[str] = set()
    urls.update(
        canonicalize_url(item.get("url", ""))
        for item in bundle.get("reference_materials", [])
        if item.get("url")
    )
    for item in bundle.get("items", []):
        urls.update(canonicalize_url(url) for url in item.get("source_urls", []))
        for claim in item.get("claims", []):
            urls.update(canonicalize_url(url) for url in claim.get("evidence_urls", []))
    return {url for url in urls if url}


def validate_research_bundle(
    bundle: dict,
    candidate_urls: set[str],
    expected_date: str | None = None,
    max_selected: int | None = None,
) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []
    ranks: list[int] = []
    if not bundle.get("items"):
        errors.append({"code": "empty_research_bundle", "location": "research items"})
    if expected_date and bundle.get("edition_date") != expected_date:
        errors.append(
            {
                "code": "edition_date_mismatch",
                "location": str(bundle.get("edition_date")),
                "expected": expected_date,
            }
        )
    if max_selected is not None and len(bundle.get("items", [])) > max_selected:
        errors.append(
            {
                "code": "too_many_selected_items",
                "location": "research items",
                "count": len(bundle.get("items", [])),
                "maximum": max_selected,
            }
        )
    for index, material in enumerate(bundle.get("reference_materials", []), start=1):
        url = canonicalize_url(material.get("url", ""))
        if not url or url not in candidate_urls:
            errors.append(
                {"code": "reference_not_in_allowed_inputs", "location": f"reference {index}: {url}"}
            )
    for item_index, item in enumerate(bundle.get("items", []), start=1):
        ranks.append(item.get("rank"))
        if not item.get("source_urls"):
            errors.append({"code": "item_without_sources", "location": f"item {item_index}"})
        if not item.get("claims"):
            errors.append({"code": "claim_missing", "location": f"item {item_index}"})
        for url in item.get("source_urls", []):
            canonical = canonicalize_url(url)
            if not _valid_http_url(url):
                errors.append({"code": "invalid_source_url", "location": url})
            elif canonical not in candidate_urls:
                errors.append({"code": "source_not_in_candidates", "location": url})
        for claim_index, claim in enumerate(item.get("claims", []), start=1):
            evidence = claim.get("evidence_urls", [])
            if claim.get("status") == "supported" and not evidence:
                errors.append(
                    {
                        "code": "supported_claim_without_evidence",
                        "location": f"item {item_index} claim {claim_index}",
                    }
                )
            for url in evidence:
                canonical = canonicalize_url(url)
                if canonical not in candidate_urls:
                    errors.append({"code": "evidence_not_in_candidates", "location": url})
    if sorted(ranks) != list(range(1, len(ranks) + 1)):
        warnings.append({"code": "rank_sequence", "location": "research items"})
    platforms = Counter(topic.get("platform") for topic in bundle.get("topics", []))
    for platform in ("wechat", "woshipm"):
        if platforms[platform] != 1:
            errors.append({"code": "topic_count", "location": platform, "count": platforms[platform]})
    return {"errors": errors, "warnings": warnings}


def validate_article(
    article: dict,
    evidence_urls: set[str],
    target: str,
    *,
    strict_editorial: bool = True,
    requirements: dict | None = None,
) -> dict:
    requirements = requirements or {}
    body = str(article.get("body_markdown", ""))
    reviewable_prose = "\n".join(
        str(article.get(field_name, ""))
        for field_name in ("title", "subtitle", "summary", "body_markdown")
    )
    errors: list[dict] = []
    warnings: list[dict] = []
    if article.get("platform") != target:
        errors.append({"code": "platform_mismatch", "location": str(article.get("platform"))})
    if not article.get("title") or not body.strip():
        errors.append({"code": "empty_article", "location": target})

    for char in ("—", "–"):
        if char in reviewable_prose:
            errors.append({"code": "forbidden_dash", "location": char})
    prose_without_urls = _strip_urls(reviewable_prose)
    if ":" in prose_without_urls or "：" in prose_without_urls:
        errors.append({"code": "colon_requires_review", "location": target})
    for pattern, message in CONTRARIAN_PATTERNS.items():
        if re.search(pattern, reviewable_prose, flags=re.S):
            errors.append({"code": "contrarian_template", "location": message})
    for phrase, suggestion in MODEL_PHRASES.items():
        if phrase in reviewable_prose:
            errors.append({"code": "model_phrase", "location": phrase, "suggestion": suggestion})

    source_urls = {canonicalize_url(url) for url in article.get("source_urls", []) if url}
    for url in article.get("source_urls", []):
        if not _valid_http_url(url):
            errors.append({"code": "invalid_article_source", "location": url})
    unknown = source_urls - evidence_urls
    if unknown:
        errors.append({"code": "article_source_outside_bundle", "location": sorted(unknown)})
    minimum_sources = int(requirements.get("min_source_count", 1))
    if not source_urls:
        errors.append({"code": "article_without_sources", "location": target})
    elif len(source_urls) < minimum_sources:
        errors.append(
            {
                "code": "article_source_count_below_minimum",
                "location": target,
                "count": len(source_urls),
                "minimum": minimum_sources,
            }
        )
    elif len(source_urls) < 2:
        warnings.append({"code": "thin_source_list", "location": target, "count": len(source_urls)})

    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", body))
    minimum = int(requirements.get("min_chinese_characters", 6000))
    target_maximum = int(requirements.get("target_max_chinese_characters", 8500))
    hard_maximum = int(requirements.get("hard_max_chinese_characters", 10000))
    if chinese_chars < 100:
        errors.append(
            {"code": "article_too_short_to_review", "location": target, "count": chinese_chars}
        )
    if chinese_chars < minimum:
        issue = {"code": "article_short", "location": target, "count": chinese_chars, "minimum": minimum}
        (errors if strict_editorial else warnings).append(issue)
    if chinese_chars > hard_maximum:
        errors.append(
            {
                "code": "article_exceeds_hard_maximum",
                "location": target,
                "count": chinese_chars,
                "maximum": hard_maximum,
            }
        )
    elif chinese_chars > target_maximum:
        warnings.append(
            {
                "code": "article_above_target_length",
                "location": target,
                "count": chinese_chars,
                "target_maximum": target_maximum,
            }
        )
    if re.search(r"(?m)^\s*\|.+\|\s*$", body):
        errors.append({"code": "markdown_table_not_publishable", "location": target})
    if not article.get("ai_disclosure_note"):
        errors.append({"code": "ai_disclosure_missing", "location": target})
    if not article.get("editor_notes"):
        errors.append({"code": "editor_notes_missing", "location": target})
    return {
        "errors": errors,
        "warnings": warnings,
        "metrics": {"chinese_characters": chinese_chars, "source_count": len(source_urls)},
    }


def build_qa_report(
    bundle: dict,
    articles: dict[str, dict],
    candidate_urls: set[str],
    expected_date: str | None = None,
    max_selected: int | None = None,
    strict_editorial: bool = True,
    platform_requirements: dict[str, dict] | None = None,
) -> dict:
    research = validate_research_bundle(bundle, candidate_urls, expected_date, max_selected)
    evidence_urls = collect_evidence_urls(bundle)
    article_reports = {
        platform: validate_article(
            article,
            evidence_urls,
            platform,
            strict_editorial=strict_editorial,
            requirements=(platform_requirements or {}).get(platform),
        )
        for platform, article in articles.items()
    }
    if "wechat" in articles and "woshipm" in articles:
        left = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", articles["wechat"].get("body_markdown", "").lower())
        right = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", articles["woshipm"].get("body_markdown", "").lower())
        similarity = round(SequenceMatcher(None, left, right).ratio(), 4) if left and right else 0.0
        if min(len(left), len(right)) >= 100 and similarity >= 0.72:
            issue = {
                "code": "cross_platform_drafts_too_similar",
                "location": "wechat,woshipm",
                "similarity": similarity,
            }
            article_reports["wechat"]["errors"].append(issue)
            article_reports["woshipm"]["errors"].append(issue)
    else:
        similarity = None
    error_count = len(research["errors"]) + sum(
        len(report["errors"]) for report in article_reports.values()
    )
    warning_count = len(research["warnings"]) + sum(
        len(report["warnings"]) for report in article_reports.values()
    )
    return {
        "passed": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "cross_platform_similarity": similarity,
        "research": research,
        "articles": article_reports,
        "manual_review_required": [
            "逐条打开关键来源，复核数字、日期、开放范围和公司自述边界",
            "核对微信公众号当日 AI 内容标识、原创声明与版权设置",
            "核对人人都是产品经理当日投稿规则、同题库存、授权与白名单要求",
            "确认标题、封面、摘要和正文没有夸大结论",
        ],
    }
