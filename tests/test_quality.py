from __future__ import annotations

import unittest

from ai_news_agent.quality import build_qa_report, validate_article


def article(platform: str, body: str, sources: list[str] | None = None) -> dict:
    return {
        "platform": platform,
        "title": "一份可审核的样例文章",
        "subtitle": "",
        "body_markdown": body,
        "summary": "用于测试质量阻断规则。",
        "source_urls": sources or [],
        "ai_disclosure_note": "发布前核对标识。",
        "editor_notes": ["人工终审"],
    }


class QualityTests(unittest.TestCase):
    def test_short_article_and_markdown_table_are_blocking(self) -> None:
        source = "https://example.com/source"
        report = validate_article(
            article("wechat", "| 项目 | 结果 |\n|---|---|\n| 长度 | 不足 |", [source]),
            {source},
            "wechat",
        )
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("article_short", codes)
        self.assertIn("markdown_table_not_publishable", codes)

    def test_platform_source_minimum_is_blocking(self) -> None:
        source = "https://example.com/source"
        report = validate_article(
            article("wechat", "正文" * 3100, [source]),
            {source},
            "wechat",
            requirements={"min_source_count": 4},
        )
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("article_source_count_below_minimum", codes)

    def test_empty_bundle_and_source_free_articles_fail(self) -> None:
        bundle = {
            "edition_date": "2099-01-01",
            "reference_materials": [],
            "items": [],
            "topics": [],
        }
        report = build_qa_report(
            bundle,
            {
                "wechat": article("wechat", "很短"),
                "woshipm": article("woshipm", "也很短"),
            },
            set(),
            expected_date="2099-01-01",
            max_selected=10,
        )
        self.assertFalse(report["passed"])
        self.assertGreaterEqual(report["error_count"], 5)

    def test_identical_platform_drafts_fail_similarity_gate(self) -> None:
        source = "https://example.com/model"
        bundle = {
            "edition_date": "2099-01-01",
            "reference_materials": [],
            "items": [
                {
                    "rank": 1,
                    "title": "样例",
                    "event_time": "2099-01-01",
                    "summary": "样例摘要",
                    "why_it_matters": "产品团队需要核对边界",
                    "risk_note": "不能用于真实发布",
                    "source_urls": [source],
                    "claims": [
                        {"text": "样例发布", "status": "supported", "evidence_urls": [source]}
                    ],
                }
            ],
            "topics": [
                {"platform": "wechat"},
                {"platform": "woshipm"},
            ],
        }
        body = "产品团队需要先核对事实和开放范围。" * 25
        report = build_qa_report(
            bundle,
            {
                "wechat": article("wechat", body, [source]),
                "woshipm": article("woshipm", body, [source]),
            },
            {source},
            expected_date="2099-01-01",
            max_selected=10,
        )
        self.assertFalse(report["passed"])
        self.assertEqual(report["cross_platform_similarity"], 1.0)


if __name__ == "__main__":
    unittest.main()
