from __future__ import annotations

import json
import shutil
from pathlib import Path


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
