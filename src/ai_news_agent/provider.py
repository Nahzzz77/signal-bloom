from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Protocol


class GenerationProvider(Protocol):
    def generate(
        self,
        *,
        stage: str,
        prompt: str,
        schema_path: Path,
        output_path: Path,
        events_path: Path,
    ) -> dict: ...


class CodexExecError(RuntimeError):
    pass


class CodexExecProvider:
    """Use Codex CLI as the agent harness and preserve its event trail."""

    def __init__(self, project_root: Path, timeout_seconds: int = 900) -> None:
        self.project_root = project_root
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        *,
        stage: str,
        prompt: str,
        schema_path: Path,
        output_path: Path,
        events_path: Path,
    ) -> dict:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "codex",
            "exec",
            "--config",
            f'model_reasoning_effort="{"low" if stage == "research" else "medium"}"',
            "--skip-git-repo-check",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--json",
            "--output-schema",
            str(schema_path),
            "-o",
            str(output_path),
            "-",
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CodexExecError(f"{stage} timed out after {self.timeout_seconds}s") from exc

        events_path.write_text(completed.stdout, encoding="utf-8")
        events_path.with_suffix(".stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout)[-2000:]
            raise CodexExecError(f"{stage} failed with exit {completed.returncode}: {tail}")
        if not output_path.exists():
            raise CodexExecError(f"{stage} did not create {output_path}")
        try:
            return json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CodexExecError(f"{stage} returned invalid JSON: {exc}") from exc


class DemoProvider:
    """Deterministic provider used only by tests and product demos."""

    def generate(
        self,
        *,
        stage: str,
        prompt: str,
        schema_path: Path,
        output_path: Path,
        events_path: Path,
    ) -> dict:
        del prompt, schema_path
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text(json.dumps({"stage": stage, "provider": "demo"}) + "\n", encoding="utf-8")
        if stage == "research":
            value = {
                "edition_date": "2099-01-01",
                "digest_title": "SignalBloom 测试版",
                "executive_summary": "这是一份不连接外部服务的验收样例。",
                "reference_materials": [],
                "items": [
                    {
                        "rank": 1,
                        "title": "样例模型发布",
                        "event_time": "2099-01-01",
                        "summary": "样例团队发布一项模型更新。",
                        "why_it_matters": "产品团队需要重新核对能力边界。",
                        "risk_note": "样例数据不能用于正式发布。",
                        "source_urls": ["https://example.com/model"],
                        "claims": [
                            {
                                "text": "样例团队发布模型更新",
                                "status": "supported",
                                "evidence_urls": ["https://example.com/model"],
                            }
                        ],
                    }
                ],
                "topics": [
                    {
                        "platform": "wechat",
                        "title": "一次模型更新会改变什么",
                        "angle": "解释更新边界",
                        "audience_decision": "是否进入测试",
                        "new_value": "给出核对清单",
                        "required_claims": ["样例团队发布模型更新"],
                        "avoid": ["把样例写成真实新闻"],
                    },
                    {
                        "platform": "woshipm",
                        "title": "产品团队如何决定是否测试新模型",
                        "angle": "测试门槛",
                        "audience_decision": "是否投入评测资源",
                        "new_value": "给出决策框架",
                        "required_claims": ["样例团队发布模型更新"],
                        "avoid": ["功能百科"],
                    },
                ],
            }
        else:
            platform = "wechat" if stage == "wechat" else "woshipm"
            if platform == "wechat":
                demo_body = (
                    "样例团队发布了一项模型更新。公开资料目前只能证明发布动作，无法证明它已经改善任何真实业务。编辑先要核对开放范围、价格和已知限制，再决定是否值得投入测试资源。\n\n"
                    "一轮可靠验证应从固定任务开始。团队需要保留原始输入、模型输出、人工评分和失败原因，并把质量、延迟与成本分开记录。公开榜单只能提供线索，不能替代自己的业务样本。达到预设门槛后，再进入小流量验证。\n\n"
                    "这份文字只用于离线工程验收。真人编辑仍需打开来源、补充判断并重写表达，不能把样例当作真实新闻发布。\n\n"
                    "## 关键来源\n\n- https://example.com/model\n"
                )
            else:
                demo_body = (
                    "产品团队面对一次模型更新，先要回答是否值得启动评测。这个决定会占用样本整理、人工标注、接口接入和回归测试资源，不能只看发布页上的能力描述。\n\n"
                    "可以先设一道进入门槛。候选模型需要覆盖核心任务，费用和延迟处在可接受区间，并且能说清数据处理与失败恢复。满足门槛后，团队再用同一任务集比较当前方案和候选方案，记录成功率、人工接管率以及单次有效任务成本。\n\n"
                    "样例没有真实评测数据，不能得出采用结论。它只验证决策结构、文件生成和审核阻断是否工作。\n\n"
                    "## 关键来源\n\n- https://example.com/model\n"
                )
            value = {
                "status": "ready",
                "platform": platform,
                "title": "产品团队如何核对一次模型更新",
                "subtitle": "一份离线验收样例",
                "body_markdown": demo_body,
                "summary": "用固定任务集核对新模型。",
                "source_urls": ["https://example.com/model"],
                "ai_disclosure_note": "发布前由人工确认 AI 内容标识要求。",
                "editor_notes": ["这是离线样例，不能直接发布。"],
                "blocking_reason": None,
                "missing_evidence": [],
            }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return value
