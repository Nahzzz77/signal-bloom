from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "recheck_output.py"
SPEC = importlib.util.spec_from_file_location("recheck_output", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecheckTests(unittest.TestCase):
    def test_missing_final_images_are_blocking(self) -> None:
        articles = {
            "wechat": {"body_markdown": "![图](images/missing.png)"},
            "woshipm": {"body_markdown": "没有图片"},
        }
        config = {
            "common": {"min_final_image_assets": 4, "max_final_image_assets": 5},
            "wechat": {"min_final_image_count": 2},
            "woshipm": {"min_final_image_count": 2},
        }
        qa = {
            "research": {"errors": [], "warnings": []},
            "articles": {
                "wechat": {"errors": [], "warnings": [], "metrics": {}},
                "woshipm": {"errors": [], "warnings": [], "metrics": {}},
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            MODULE.check_final_images(Path(temp), articles, config, qa)
        codes = {
            item["code"]
            for report in [qa["research"], *qa["articles"].values()]
            for item in report["errors"]
        }
        self.assertIn("article_image_missing_or_external", codes)
        self.assertIn("article_image_count_below_minimum", codes)
        self.assertIn("final_image_asset_count", codes)

    def test_rejects_prose_after_source_section(self) -> None:
        base = {
            "platform": "wechat",
            "title": "旧标题",
            "subtitle": "",
            "body_markdown": "旧正文",
            "summary": "用于测试的摘要文字",
            "source_urls": ["https://example.com/source"],
            "ai_disclosure_note": "发布前核对 AI 标识要求。",
            "editor_notes": ["真人终审。"],
        }
        markdown = (
            "# 新标题\n\n副标题\n\n正文内容。\n\n"
            "## 关键来源\n\n- [来源](https://example.com/source)\n\n"
            "这段事实不能躲在来源列表之后。\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "article.final.md"
            path.write_text(markdown, encoding="utf-8")
            with self.assertRaises(ValueError):
                MODULE.parse_final_markdown(path, base)


if __name__ == "__main__":
    unittest.main()
