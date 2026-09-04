from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "scheduled_feishu_runner.py"


class ScheduledFeishuRunnerTests(unittest.TestCase):
    def _install(self, temp: Path, *, create_output: bool) -> Path:
        install_dir = temp / "installed"
        install_dir.mkdir()
        runner = install_dir / "runner.py"
        shutil.copyfile(RUNNER, runner)
        project_dir = temp / "project"
        project_dir.mkdir()
        (project_dir / ".env").write_text(
            "FEISHU_APP_ID=private-app\n"
            "FEISHU_APP_SECRET=private-secret\n"
            "FEISHU_CHAT_NAME=private-group\n",
            encoding="utf-8",
        )
        edition_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        if create_output:
            (project_dir / "outputs" / edition_date).mkdir(parents=True)
        module = install_dir / "feishu.py"
        module.write_text(
            "def sync_output(output_dir, *, app_id, app_secret, chat_name, dry_run=False):\n"
            "    assert app_id == 'private-app' and app_secret == 'private-secret'\n"
            "    assert chat_name == 'private-group'\n"
            "    if dry_run:\n"
            "        return {'status': 'dry_run', 'item_count': 10}\n"
            "    return {'status': 'succeeded', 'message_id': 'private-message'}\n",
            encoding="utf-8",
        )
        (install_dir / "config.json").write_text(
            json.dumps(
                {
                    "project_dir": str(project_dir),
                    "feishu_module_sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
                }
            ),
            encoding="utf-8",
        )
        return runner

    def test_runner_sends_without_printing_private_values(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            runner = self._install(Path(raw_temp), create_output=True)
            result = subprocess.run(
                [sys.executable, str(runner)], capture_output=True, text=True, check=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "succeeded")
            combined = result.stdout + result.stderr
            for private_value in ("private-app", "private-secret", "private-group", "private-message"):
                self.assertNotIn(private_value, combined)

    def test_runner_waits_when_today_output_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            runner = self._install(Path(raw_temp), create_output=False)
            result = subprocess.run(
                [sys.executable, str(runner)], capture_output=True, text=True, check=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "waiting")


if __name__ == "__main__":
    unittest.main()
