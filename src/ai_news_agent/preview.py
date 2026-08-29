from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path


def write_archive_index(outputs_dir: Path) -> dict:
    """Index complete private editions and point the stable local entry at the latest one."""

    outputs_dir.mkdir(parents=True, exist_ok=True)
    editions = []
    required = (
        "review.html",
        "edition.json",
        "manifest.json",
        "research_bundle.json",
        "articles/wechat.md",
        "articles/woshipm.md",
    )
    for candidate in outputs_dir.iterdir():
        if not candidate.is_dir():
            continue
        try:
            if date.fromisoformat(candidate.name).isoformat() != candidate.name:
                continue
        except ValueError:
            continue
        if not all((candidate / relative).is_file() for relative in required):
            continue
        try:
            edition = json.loads((candidate / "edition.json").read_text(encoding="utf-8"))
            manifest = json.loads((candidate / "manifest.json").read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if (
            edition.get("edition_date") == candidate.name
            and manifest.get("edition_date") == candidate.name
            and manifest.get("status") in {"completed", "needs_revision"}
        ):
            editions.append(candidate.name)

    editions.sort(reverse=True)
    payload = {"editions": editions}
    (outputs_dir / "archive.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if editions:
        target = f"./{editions[0]}/review.html"
        redirect = f'<meta http-equiv="refresh" content="0; url={target}">'
        body = f'<p>正在打开最新一期。<a href="{target}">点击继续</a></p>'
    else:
        redirect = ""
        body = "<p>尚未生成可查看的本地日报。</p>"
    landing = (
        "<!doctype html>\n"
        '<html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"{redirect}<title>SignalBloom 历史日报</title>"
        "<style>body{margin:0;min-height:100vh;display:grid;place-items:center;"
        "background:#000;color:#fff;font:16px/1.7 system-ui,sans-serif}"
        "a{color:inherit}</style></head><body>"
        f"{body}</body></html>\n"
    )
    for name in ("index.html", "review.html"):
        (outputs_dir / name).write_text(landing, encoding="utf-8")
    return payload


def write_edition_summary(
    output_dir: Path,
    edition_date: str,
    articles: dict[str, dict],
    qa: dict,
) -> None:
    article_summaries = {}
    for name, article in articles.items():
        metrics = qa.get("articles", {}).get(name, {}).get("metrics", {})
        article_summaries[name] = {
            "title": article.get("title", ""),
            "chinese_characters": int(metrics.get("chinese_characters", 0)),
            "source_count": int(metrics.get("source_count", 0)),
            "image_count": int(metrics.get("image_count", 0)),
        }
    payload = {
        "edition_date": edition_date,
        "articles": article_summaries,
    }
    (output_dir / "edition.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def install_prebuilt_preview(
    project_root: Path,
    output_dir: Path,
    article_paths: dict[str, Path],
) -> bool:
    """Install the built React shell and edition-specific article files."""

    dist_dir = project_root / "review-site" / "dist"
    index_path = dist_dir / "index.html"
    assets_dir = dist_dir / "assets"
    if not index_path.is_file() or not assets_dir.is_dir():
        return False

    shutil.copy2(index_path, output_dir / "review.html")
    hero_video = dist_dir / "hero-flower.mp4"
    if hero_video.is_file():
        shutil.copy2(hero_video, output_dir / hero_video.name)
    output_assets = output_dir / "assets"
    if output_assets.is_dir():
        shutil.rmtree(output_assets)
    shutil.copytree(assets_dir, output_assets)

    output_articles = output_dir / "articles"
    if output_articles.is_dir():
        shutil.rmtree(output_articles)
    output_articles.mkdir(parents=True)
    for platform, source_path in article_paths.items():
        shutil.copy2(source_path, output_articles / f"{platform}.md")
    return True
