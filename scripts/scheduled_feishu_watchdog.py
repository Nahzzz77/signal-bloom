#!/usr/bin/env python3
"""Alert locally when today's Feishu delivery has no confirmed receipt."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


INSTALL_DIR = Path(__file__).resolve().parent
CONFIG_PATH = INSTALL_DIR / "config.json"


def _notify_user() -> bool:
    """Best-effort notification without exposing any private delivery data."""
    try:
        result = subprocess.run(
            [
                "/usr/bin/osascript",
                "-e",
                'display notification "今日飞书日报尚未成功投递，请打开 Codex 查看原因。" with title "SignalBloom" subtitle "投递异常"',
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _healthy(project_dir: Path, edition_date: str) -> bool:
    receipt_path = project_dir / "outputs" / edition_date / "feishu_delivery.json"
    if not receipt_path.is_file():
        return False
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return receipt.get("status") == "succeeded" and receipt.get("edition_date") == edition_date


def main() -> int:
    if len(sys.argv) != 1:
        return 2
    edition_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        project_dir = Path(str(config["project_dir"]))
        if not project_dir.is_absolute():
            return 2
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return 2

    if _healthy(project_dir, edition_date):
        print(json.dumps({"status": "healthy", "edition_date": edition_date}))
        return 0

    if _notify_user():
        print(json.dumps({"status": "alerted", "edition_date": edition_date}))
        return 0
    print(json.dumps({"status": "alert_failed", "edition_date": edition_date}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
