#!/usr/bin/env python3
"""Network-enabled, argument-free runner for scheduled Feishu delivery.

This file is copied with a pinned ``feishu.py`` and ``config.json`` into a
read-only user directory before it is allow-listed in Codex.  It is not meant
to be run in-place from the writable repository.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from zoneinfo import ZoneInfo


INSTALL_DIR = Path(__file__).resolve().parent
CONFIG_PATH = INSTALL_DIR / "config.json"
MODULE_PATH = INSTALL_DIR / "feishu.py"
ALLOWED_ENV_KEYS = {"FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_CHAT_NAME"}


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _load_local_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in ALLOWED_ENV_KEYS:
            values[key] = value.strip().strip('"').strip("'")
    return values


def _load_pinned_module(path: Path, expected_sha256: str) -> ModuleType:
    actual_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError("installed Feishu sender failed its integrity check")
    spec = importlib.util.spec_from_file_location("signalbloom_pinned_feishu", path)
    if spec is None or spec.loader is None:
        raise ValueError("installed Feishu sender cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reason(exc: Exception) -> str:
    message = str(exc)
    if "无法连接飞书 API" in message:
        return "network_unreachable"
    if "缺少 FEISHU_APP_ID" in message:
        return "credentials_missing"
    if "机器人所在群" in message:
        return "target_group_mismatch"
    if "Manifest" in message or "研究" in message or "缺少本地文件" in message:
        return "content_validation_failed"
    return "delivery_failed"


def main() -> int:
    if len(sys.argv) != 1:
        print(json.dumps({"status": "failed", "reason": "arguments_not_allowed"}))
        return 2

    edition_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    try:
        config = _load_json(CONFIG_PATH)
        project_dir = Path(str(config["project_dir"]))
        if not project_dir.is_absolute():
            raise ValueError("project_dir must be absolute")
        output_dir = project_dir / "outputs" / edition_date
        if not output_dir.is_dir():
            print(
                json.dumps(
                    {"status": "waiting", "edition_date": edition_date, "reason": "output_missing"}
                )
            )
            return 0

        local_env = _load_local_env(project_dir / ".env")
        module = _load_pinned_module(MODULE_PATH, str(config["feishu_module_sha256"]))
        kwargs = {
            "app_id": local_env.get("FEISHU_APP_ID", ""),
            "app_secret": local_env.get("FEISHU_APP_SECRET", ""),
            "chat_name": local_env.get("FEISHU_CHAT_NAME", "SignalBloom 私人资讯"),
        }
        dry_run = module.sync_output(output_dir, dry_run=True, **kwargs)
        result = module.sync_output(output_dir, **kwargs)
        print(
            json.dumps(
                {
                    "status": "skipped" if result.get("skipped") else "succeeded",
                    "edition_date": edition_date,
                    "item_count": dry_run.get("item_count", 0),
                },
                ensure_ascii=False,
            )
        )
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        reason = _reason(exc)
    except Exception as exc:  # The pinned module owns the API-specific error type.
        reason = _reason(exc)

    print(
        json.dumps({"status": "failed", "edition_date": edition_date, "reason": reason}),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
