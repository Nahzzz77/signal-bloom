#!/usr/bin/env python3
"""Rebuild final article JSON, QA, review HTML, and the run manifest.

This script is intentionally deterministic. It does not call a model or the
network, so an editor can revise the two ``*.final.md`` files and then refresh
the acceptance package without rerunning research and drafting.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_news_agent.normalize import canonicalize_url
from ai_news_agent.preview import install_prebuilt_preview, write_archive_index, write_edition_summary
from ai_news_agent.quality import build_qa_report
from ai_news_agent.render import render_review_html, write_json


SOURCE_LINE_PATTERN = re.compile(r"^- \[[^\]]+\]\((https?://[^)]+)\)$")
IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def object_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_final_markdown(path: Path, base_article: dict) -> dict:
    text = path.read_text(encoding="utf-8").strip()
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError(f"final article must start with one H1 title: {path}")

    title = lines[0][2:].strip()
    cursor = 1
    while cursor < len(lines) and not lines[cursor].strip():
        cursor += 1
    subtitle = ""
    if cursor < len(lines) and not lines[cursor].lstrip().startswith("#"):
        subtitle = lines[cursor].strip()
        cursor += 1
    while cursor < len(lines) and not lines[cursor].strip():
        cursor += 1

    source_heading = next(
        (index for index, line in enumerate(lines[cursor:], start=cursor) if line.strip() == "## 关键来源"),
        len(lines),
    )
    if source_heading == len(lines):
        raise ValueError(f"final article needs a trailing '## 关键来源' section: {path}")
    body = "\n".join(lines[cursor:source_heading]).strip()
    source_lines = [line.strip() for line in lines[source_heading + 1 :] if line.strip()]
    invalid_source_lines = [
        line for line in source_lines if SOURCE_LINE_PATTERN.fullmatch(line) is None
    ]
    if invalid_source_lines:
        raise ValueError(
            "only Markdown source links are allowed after '## 关键来源': "
            + "; ".join(invalid_source_lines[:3])
        )
    sources = list(
        dict.fromkeys(
            match.group(1)
            for line in source_lines
            for match in [SOURCE_LINE_PATTERN.fullmatch(line)]
            if match is not None
        )
    )
    if not body or not sources:
        raise ValueError(f"final article needs body text and linked sources: {path}")

    article = copy.deepcopy(base_article)
    article.update(
        {
            "status": "ready",
            "title": title,
            "subtitle": subtitle,
            "body_markdown": body,
            "source_urls": sources,
            "blocking_reason": None,
            "missing_evidence": [],
        }
    )
    return article


def build_preview_site(project_root: Path, output_dir: Path) -> None:
    site_dir = project_root / "review-site"
    completed = subprocess.run(
        ["npm", "run", "build"],
        cwd=site_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "React preview build failed\n"
            + completed.stdout.strip()
            + "\n"
            + completed.stderr.strip()
        )

    installed = install_prebuilt_preview(
        project_root,
        output_dir,
        {
            "wechat": output_dir / "wechat_article.final.md",
            "woshipm": output_dir / "woshipm_article.final.md",
        },
    )
    if not installed:
        raise RuntimeError("React preview build completed without index.html or assets")


def check_final_images(
    output_dir: Path,
    articles: dict[str, dict],
    platforms_config: dict,
    qa: dict,
) -> None:
    referenced: set[str] = set()
    for platform_name, article in articles.items():
        image_refs = IMAGE_PATTERN.findall(article.get("body_markdown", ""))
        qa["articles"][platform_name]["metrics"]["image_count"] = len(image_refs)
        minimum = int(platforms_config.get(platform_name, {}).get("min_final_image_count", 0))
        if len(image_refs) < minimum:
            qa["articles"][platform_name]["errors"].append(
                {
                    "code": "article_image_count_below_minimum",
                    "location": platform_name,
                    "count": len(image_refs),
                    "minimum": minimum,
                }
            )
        for relative_path in image_refs:
            candidate = (output_dir / relative_path).resolve()
            try:
                candidate.relative_to(output_dir)
            except ValueError:
                candidate = Path()
            if not relative_path.startswith("images/") or not candidate.is_file():
                qa["articles"][platform_name]["errors"].append(
                    {
                        "code": "article_image_missing_or_external",
                        "location": relative_path,
                    }
                )
            else:
                referenced.add(relative_path)

    common = platforms_config.get("common", {})
    minimum_assets = int(common.get("min_final_image_assets", 0))
    maximum_assets = int(common.get("max_final_image_assets", 999))
    if not minimum_assets <= len(referenced) <= maximum_assets:
        qa["research"]["errors"].append(
            {
                "code": "final_image_asset_count",
                "location": "final articles",
                "count": len(referenced),
                "minimum": minimum_assets,
                "maximum": maximum_assets,
            }
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Recheck an edited AI news acceptance package")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--prose-checker",
        type=Path,
        help="optional path to the Human Writing check_prose.py script",
    )
    parser.add_argument(
        "--build-preview",
        action="store_true",
        help="build and install the React article preview as review.html",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    output_dir = args.output_dir.resolve()
    if output_dir in {Path("/").resolve(), Path.home().resolve(), project_root}:
        raise ValueError(f"unsafe output directory: {output_dir}")

    manifest = read_json(output_dir / "manifest.json")
    bundle = read_json(output_dir / "research_bundle.json")
    normalized = read_json(output_dir / "normalized_items.json")
    source_config = read_json(project_root / "configs" / "sources.json")
    platforms_config = read_json(project_root / "configs" / "platforms.json")
    metadata_path = output_dir / "editorial_metadata.json"
    editorial_metadata = read_json(metadata_path) if metadata_path.is_file() else {}

    rules_path_value = manifest.get("input", {}).get("platform_rules")
    rules = read_json(Path(rules_path_value)) if rules_path_value else {}
    candidate_urls = {
        canonicalize_url(url)
        for item in normalized
        for url in item.get("evidence_urls", [])
        if url
    }
    candidate_urls.update(
        canonicalize_url(url) for url in rules.get("allowed_evidence_urls", []) if url
    )

    articles = {}
    for platform_name in ("wechat", "woshipm"):
        base = read_json(output_dir / f"{platform_name}_article.json")
        metadata = editorial_metadata.get(platform_name, {})
        for field_name in ("summary", "ai_disclosure_note", "editor_notes"):
            if field_name in metadata:
                base[field_name] = metadata[field_name]
        final_path = output_dir / f"{platform_name}_article.final.md"
        final_article = parse_final_markdown(final_path, base)
        articles[platform_name] = final_article
        write_json(output_dir / f"{platform_name}_article.final.json", final_article)

    qa = build_qa_report(
        bundle,
        articles,
        candidate_urls,
        expected_date=manifest["edition_date"],
        max_selected=int(source_config.get("max_selected", 10)),
        platform_requirements=platforms_config,
    )
    check_final_images(output_dir, articles, platforms_config, qa)
    prose_checker = args.prose_checker
    if prose_checker is None:
        prose_checker = Path.home() / ".codex" / "skills" / "human-writing" / "scripts" / "check_prose.py"
    prose_report = {
        "checker": str(prose_checker),
        "checker_available": prose_checker.is_file(),
        "articles": {},
    }
    for platform_name in ("wechat", "woshipm"):
        if prose_checker.is_file():
            completed = subprocess.run(
                [sys.executable, str(prose_checker), str(output_dir / f"{platform_name}_article.final.md")],
                capture_output=True,
                text=True,
                check=False,
            )
            stdout = completed.stdout.strip()
            result = {
                "exit_code": completed.returncode,
                "passed": completed.returncode == 0,
                "manual_warning": "需要人工判断" in stdout,
                "stdout": stdout,
                "stderr": completed.stderr.strip(),
            }
            if completed.returncode != 0:
                qa["articles"][platform_name]["errors"].append(
                    {
                        "code": "human_writing_check_failed",
                        "location": f"{platform_name}_article.final.md",
                    }
                )
            elif result["manual_warning"]:
                qa["articles"][platform_name]["warnings"].append(
                    {
                        "code": "human_writing_manual_review",
                        "location": f"{platform_name}_article.final.md",
                    }
                )
        else:
            result = {
                "exit_code": None,
                "passed": False,
                "manual_warning": True,
                "stdout": "",
                "stderr": "Human Writing checker not found",
            }
            qa["articles"][platform_name]["errors"].append(
                {
                    "code": "human_writing_checker_unavailable",
                    "location": str(prose_checker),
                }
            )
        prose_report["articles"][platform_name] = result
    qa["error_count"] = len(qa["research"]["errors"]) + sum(
        len(report["errors"]) for report in qa["articles"].values()
    )
    qa["warning_count"] = len(qa["research"]["warnings"]) + sum(
        len(report["warnings"]) for report in qa["articles"].values()
    )
    qa["passed"] = qa["error_count"] == 0
    write_edition_summary(output_dir, manifest["edition_date"], articles, qa)
    write_json(output_dir / "prose_check_report.json", prose_report)
    write_json(output_dir / "qa_report.json", qa)
    rendered_review = render_review_html(bundle, articles, qa)
    if args.build_preview:
        (output_dir / "review-legacy.html").write_text(rendered_review, encoding="utf-8")
        build_preview_site(project_root, output_dir)
    else:
        (output_dir / "review.html").write_text(rendered_review, encoding="utf-8")

    now = datetime.now(ZoneInfo(manifest.get("timezone", "Asia/Shanghai"))).isoformat(
        timespec="seconds"
    )
    revision_input = {
        name: file_hash(output_dir / f"{name}_article.final.md")
        for name in ("wechat", "woshipm")
    }
    previous_revision = manifest["stages"].get("editorial_revision", {})
    manifest["stages"]["editorial_revision"] = {
        "status": "completed",
        "attempt": int(previous_revision.get("attempt", 0)) + 1,
        "input_sha256": object_hash(revision_input),
        "started_at": now,
        "finished_at": now,
    }
    for stage_name, stage_input in (
        ("quality", {"articles": articles, "prose_check": prose_report}),
        ("review", qa),
    ):
        previous_stage = manifest["stages"].get(stage_name, {})
        manifest["stages"][stage_name] = {
            "status": "completed",
            "attempt": int(previous_stage.get("attempt", 0)) + 1,
            "input_sha256": object_hash(stage_input),
            "started_at": now,
            "finished_at": now,
        }

    manifest["status"] = "completed" if qa["passed"] else "needs_revision"
    manifest["finished_at"] = now
    counts = manifest.setdefault("counts", {})
    counts.update(
        {
            "final_articles": len(articles),
            "image_assets": len(list((output_dir / "images").glob("*.png"))),
            "qa_errors": qa["error_count"],
            "qa_warnings": qa["warning_count"],
        }
    )
    artifacts = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        artifacts.append(
            {
                "path": str(path.relative_to(output_dir)),
                "sha256": file_hash(path),
                "bytes": path.stat().st_size,
            }
        )
    manifest["artifacts"] = artifacts
    write_json(output_dir / "manifest.json", manifest)
    if output_dir == (project_root / "outputs" / manifest["edition_date"]).resolve():
        write_archive_index(output_dir.parent)

    print(
        json.dumps(
            {
                "status": manifest["status"],
                "qa_errors": qa["error_count"],
                "qa_warnings": qa["warning_count"],
                "cross_platform_similarity": qa["cross_platform_similarity"],
                "prose_checker_available": prose_report["checker_available"],
                "artifacts": len(artifacts),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if qa["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
