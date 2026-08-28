from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_news_agent.feishu import FeishuError, build_post, find_chat_id, sync_output


def bundle() -> dict:
    return {
        "edition_date": "2099-01-01",
        "digest_title": "AI 资讯样例",
        "executive_summary": "今日共收录两条可核验资讯，供产品团队评估边界与风险。",
        "reference_materials": [],
        "items": [
            {
                "rank": 1,
                "title": "模型甲发布",
                "event_time": "2099-01-01",
                "summary": "官方公布了模型甲的新能力与限制。",
                "why_it_matters": "需要重新评估当前产品的模型选型。",
                "risk_note": "暂时不能假定所有地区均已开放。",
                "source_urls": ["https://example.com/a", "https://example.com/a-doc"],
                "claims": [
                    {
                        "text": "已宣布模型甲",
                        "status": "supported",
                        "evidence_urls": ["https://example.com/a"],
                    },
                    {
                        "text": "开放范围待确认",
                        "status": "partial",
                        "evidence_urls": ["https://example.com/a-doc"],
                    },
                ],
            },
            {
                "rank": 2,
                "title": "工具乙更新",
                "event_time": "2099-01-01",
                "summary": "工具乙调整了自动化执行流程。",
                "why_it_matters": "产品团队要检查原有审批与回滚流程。",
                "risk_note": "效果与安全性尚缺少独立验证。",
                "source_urls": ["https://example.com/b"],
                "claims": [
                    {
                        "text": "结论存在冲突",
                        "status": "conflicting",
                        "evidence_urls": ["https://example.com/b"],
                    },
                    {
                        "text": "安全性待核实",
                        "status": "unverified",
                        "evidence_urls": [],
                    },
                ],
            },
        ],
        "topics": [
            {
                "platform": platform,
                "title": "样例选题",
                "angle": "从产品判断出发",
                "audience_decision": "是否调整方案",
                "new_value": "补充风险与证据",
                "required_claims": [],
                "avoid": [],
            }
            for platform in ("wechat", "woshipm")
        ],
    }


def write_output(output_dir: Path, *, errors: list[dict] | None = None) -> None:
    output_dir.mkdir()
    bundle_path = output_dir / "research_bundle.json"
    bundle_path.write_text(json.dumps(bundle(), ensure_ascii=False), encoding="utf-8")
    (output_dir / "qa_report.json").write_text(
        json.dumps({"research": {"errors": errors or []}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "path": "research_bundle.json",
                        "sha256": hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


class FeishuTests(unittest.TestCase):
    def test_build_post_preserves_editorial_evidence(self) -> None:
        value = bundle()
        post = build_post(value)
        serialized = json.dumps(post, ensure_ascii=False)

        for item in value["items"]:
            self.assertIn(item["title"], serialized)
            self.assertIn(item["why_it_matters"], serialized)
            self.assertIn(item["risk_note"], serialized)
            for url in item["source_urls"]:
                self.assertIn(url, serialized)
        for label in ("已核实", "部分支持", "存在冲突", "未核实"):
            self.assertIn(label, serialized)

    def test_find_chat_id_requires_one_exact_match(self) -> None:
        chats = [
            {"name": "SignalBloom 私人资讯备份", "chat_id": "oc_other"},
            {"name": "SignalBloom 私人资讯", "chat_id": "oc_exact"},
        ]
        self.assertEqual(find_chat_id(chats, "SignalBloom 私人资讯"), "oc_exact")
        with self.assertRaises(FeishuError):
            find_chat_id(chats, "不存在的群")
        with self.assertRaises(FeishuError):
            find_chat_id(chats + [chats[1]], "SignalBloom 私人资讯")

    def test_sync_output_rejects_research_errors_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp) / "output"
            write_output(output_dir, errors=[{"code": "bad_claim"}])
            with patch("ai_news_agent.feishu.get_tenant_access_token") as get_token:
                with self.assertRaisesRegex(FeishuError, "拒绝同步"):
                    sync_output(
                        output_dir,
                        app_id="app",
                        app_secret="secret",
                        chat_name="SignalBloom 私人资讯",
                    )
                get_token.assert_not_called()

    def test_sync_output_rejects_bundle_changed_after_qa(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp) / "output"
            write_output(output_dir)
            (output_dir / "research_bundle.json").write_text("{}", encoding="utf-8")
            with patch("ai_news_agent.feishu.get_tenant_access_token") as get_token:
                with self.assertRaisesRegex(FeishuError, "Manifest"):
                    sync_output(
                        output_dir,
                        app_id="app",
                        app_secret="secret",
                        chat_name="SignalBloom 私人资讯",
                    )
                get_token.assert_not_called()

    def test_sync_output_writes_receipt_and_skips_same_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp) / "output"
            write_output(output_dir)
            with (
                patch(
                    "ai_news_agent.feishu.get_tenant_access_token", return_value="token"
                ) as get_token,
                patch(
                    "ai_news_agent.feishu.list_chats",
                    return_value=[
                        {"name": "SignalBloom 私人资讯", "chat_id": "oc_chat"}
                    ],
                ) as list_chats,
                patch(
                    "ai_news_agent.feishu.send_post",
                    return_value={"message_id": "om_message"},
                ) as send_post,
            ):
                first = sync_output(
                    output_dir,
                    app_id="app",
                    app_secret="secret",
                    chat_name="SignalBloom 私人资讯",
                )
                second = sync_output(
                    output_dir,
                    app_id="app",
                    app_secret="secret",
                    chat_name="SignalBloom 私人资讯",
                )

            receipt = json.loads(
                (output_dir / "feishu_delivery.json").read_text(encoding="utf-8")
            )
            self.assertEqual(first["status"], "succeeded")
            self.assertEqual(receipt["message_id"], "om_message")
            self.assertTrue(second["skipped"])
            self.assertEqual(get_token.call_count, 2)
            self.assertEqual(list_chats.call_count, 2)
            send_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
