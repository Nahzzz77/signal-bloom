from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_news_agent.pipeline import NewsPipeline
from ai_news_agent.provider import DemoProvider


class BlockedDemoProvider(DemoProvider):
    def generate(self, **kwargs):
        if kwargs["stage"] != "woshipm":
            return super().generate(**kwargs)
        value = {
            "status": "blocked",
            "platform": "woshipm",
            "title": None,
            "subtitle": None,
            "body_markdown": None,
            "summary": None,
            "source_urls": [],
            "ai_disclosure_note": None,
            "editor_notes": [],
            "blocking_reason": "当前证据不足以支撑六千字的可审核长文。",
            "missing_evidence": ["缺少可核验的产品流程和失败边界"],
        }
        kwargs["events_path"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["events_path"].write_text('{"stage":"woshipm","blocked":true}\n', encoding="utf-8")
        kwargs["output_path"].write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return value


class PipelineTests(unittest.TestCase):
    def test_blocked_article_is_recorded_and_stops_completion(self) -> None:
        root = Path(__file__).resolve().parents[1]
        seed = {
            "edition_date": "2099-01-01",
            "items": [
                {
                    "title": "样例模型发布",
                    "url": "https://example.com/model",
                    "published_at": "2099-01-01T00:00:00+08:00",
                    "source_name": "Example",
                    "source_tier": 1,
                    "is_primary_source": True,
                    "summary": "离线测试候选。",
                    "evidence_urls": ["https://example.com/model"],
                    "tags": ["模型"],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            seed_path = temp_path / "seed.json"
            seed_path.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")
            output = temp_path / "output"
            manifest = NewsPipeline(root, BlockedDemoProvider()).run(
                seed_path=seed_path,
                output_dir=output,
                provider_name="demo",
            )
            self.assertEqual(manifest["status"], "needs_revision")
            self.assertEqual(manifest["stages"]["woshipm"]["status"], "blocked")
            self.assertTrue((output / "woshipm_blocked.json").is_file())

    def test_demo_pipeline_produces_review_package(self) -> None:
        root = Path(__file__).resolve().parents[1]
        seed = {
            "edition_date": "2099-01-01",
            "items": [
                {
                    "title": "样例模型发布",
                    "url": "https://example.com/model",
                    "published_at": "2099-01-01T00:00:00+08:00",
                    "source_name": "Example",
                    "source_tier": 1,
                    "is_primary_source": True,
                    "summary": "离线测试候选。",
                    "evidence_urls": ["https://example.com/model"],
                    "tags": ["模型"],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            seed_path = temp_path / "seed.json"
            seed_path.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")
            output = temp_path / "output"
            manifest = NewsPipeline(root, DemoProvider()).run(
                seed_path=seed_path,
                output_dir=output,
                provider_name="demo",
            )
            self.assertEqual(manifest["status"], "completed")
            for name in (
                "manifest.json",
                "research_bundle.json",
                "daily_digest.md",
                "wechat_article.md",
                "woshipm_article.md",
                "qa_report.json",
                "edition.json",
                "review.html",
            ):
                self.assertTrue((output / name).is_file(), name)
            qa = json.loads((output / "qa_report.json").read_text(encoding="utf-8"))
            self.assertTrue(qa["passed"])
            self.assertIn(
                "<title>SignalBloom</title>",
                (output / "review.html").read_text(encoding="utf-8"),
            )
            self.assertTrue((output / "review-legacy.html").is_file())
            self.assertTrue((output / "articles" / "wechat.md").is_file())
            self.assertTrue(any((output / "assets").glob("*.js")))
            self.assertTrue((output / "hero-flower.mp4").is_file())
            edition = json.loads((output / "edition.json").read_text(encoding="utf-8"))
            self.assertEqual(edition["edition_date"], "2099-01-01")
            self.assertEqual(edition["articles"]["wechat"]["title"], "产品团队如何核对一次模型更新")
            self.assertIn(
                "hero-flower.mp4",
                {artifact["path"] for artifact in manifest["artifacts"]},
            )
            with self.assertRaises(FileExistsError):
                NewsPipeline(root, DemoProvider()).run(
                    seed_path=seed_path,
                    output_dir=output,
                    provider_name="demo",
                )


if __name__ == "__main__":
    unittest.main()
