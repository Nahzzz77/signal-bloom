from __future__ import annotations

import json
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
WATCHDOG = ROOT / "scripts" / "scheduled_feishu_watchdog.py"


def load_watchdog_module():
    spec = importlib.util.spec_from_file_location("signalbloom_watchdog_test", WATCHDOG)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load watchdog module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScheduledFeishuWatchdogTests(unittest.TestCase):
    def _install(self, temp: Path, *, succeeded: bool) -> Path:
        install_dir = temp / "installed"
        install_dir.mkdir()
        watchdog = install_dir / "watchdog.py"
        shutil.copyfile(WATCHDOG, watchdog)
        project_dir = temp / "project"
        project_dir.mkdir()
        edition_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        receipt_dir = project_dir / "outputs" / edition_date
        receipt_dir.mkdir(parents=True)
        if succeeded:
            (receipt_dir / "feishu_delivery.json").write_text(
                json.dumps({"status": "succeeded", "edition_date": edition_date}),
                encoding="utf-8",
            )
        (install_dir / "config.json").write_text(
            json.dumps({"project_dir": str(project_dir)}), encoding="utf-8"
        )
        return watchdog

    def test_watchdog_reports_healthy_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            watchdog = self._install(Path(raw_temp), succeeded=True)
            result = subprocess.run(
                [sys.executable, str(watchdog)], capture_output=True, text=True, check=False
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "healthy")

    def test_watchdog_requires_successful_receipt_for_today(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            temp = Path(raw_temp)
            watchdog = self._install(temp, succeeded=False)
            project_dir = temp / "project"
            edition_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
            module = load_watchdog_module()

            self.assertFalse(module._healthy(project_dir, edition_date))
            receipt_dir = project_dir / "outputs" / edition_date
            (receipt_dir / "feishu_delivery.json").write_text(
                json.dumps({"status": "failed", "edition_date": edition_date}),
                encoding="utf-8",
            )
            self.assertFalse(module._healthy(project_dir, edition_date))
            (receipt_dir / "feishu_delivery.json").write_text(
                json.dumps({"status": "succeeded", "edition_date": "2000-01-01"}),
                encoding="utf-8",
            )
            self.assertFalse(module._healthy(project_dir, edition_date))

            # Notification failures must be observable by launchd rather than
            # being mislabeled as a successful alert.
            with patch.object(module.subprocess, "run", side_effect=subprocess.TimeoutExpired("osascript", 10)):
                self.assertFalse(module._notify_user())


if __name__ == "__main__":
    unittest.main()
