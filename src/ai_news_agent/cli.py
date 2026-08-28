from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .feishu import FeishuError, sync_output
from .pipeline import NewsPipeline
from .provider import CodexExecProvider, DemoProvider


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _doctor(root: Path) -> int:
    checks: list[dict] = []
    checks.append({"name": "python", "ok": sys.version_info >= (3, 9), "detail": sys.version.split()[0]})
    codex = shutil.which("codex")
    checks.append({"name": "codex_binary", "ok": bool(codex), "detail": codex or "not found"})
    for relative in (
        "configs/sources.json",
        "configs/platforms.json",
        "schemas/research_bundle.schema.json",
        "schemas/article.schema.json",
        "prompts/research.md",
        "prompts/wechat.md",
        "prompts/woshipm.md",
    ):
        path = root / relative
        checks.append({"name": relative, "ok": path.is_file(), "detail": str(path)})
    if codex:
        version = subprocess.run([codex, "--version"], capture_output=True, text=True, check=False)
        checks.append(
            {
                "name": "codex_version",
                "ok": version.returncode == 0,
                "detail": (version.stdout or version.stderr).strip(),
            }
        )
        login = subprocess.run([codex, "login", "status"], capture_output=True, text=True, check=False)
        checks.append(
            {
                "name": "codex_login",
                "ok": login.returncode == 0,
                "detail": (login.stdout or login.stderr).strip(),
            }
        )
    print(json.dumps({"passed": all(item["ok"] for item in checks), "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if all(item["ok"] for item in checks) else 1


def _load_local_env(path: Path) -> None:
    if not path.is_file():
        return
    allowed = {"FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_CHAT_NAME"}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in allowed:
            os.environ.setdefault(key, value.strip().strip("\"").strip("'"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="signal-bloom", description="Evidence-first content workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="check local runtime and project files")
    run = subparsers.add_parser("run", help="run the end-to-end content pipeline")
    run.add_argument("--seed", type=Path, required=True, help="curated candidate JSON")
    run.add_argument("--date", required=True, help="edition date in YYYY-MM-DD")
    run.add_argument("--output", type=Path, help="output directory")
    run.add_argument("--platform-rules", type=Path, help="verified current platform rules JSON")
    run.add_argument("--provider", choices=("codex", "demo"), default="codex")
    run.add_argument("--force", action="store_true", help="replace known output files in the target folder")
    run.add_argument("--timeout", type=int, default=900, help="seconds allowed for each Codex stage")
    sync = subparsers.add_parser("sync-feishu", help="send one verified daily digest to Feishu")
    sync.add_argument("--output", type=Path, required=True, help="existing daily output directory")
    sync.add_argument("--chat-name", help="exact Feishu group name")
    sync.add_argument("--dry-run", action="store_true", help="validate and render without calling Feishu")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = project_root()
    if args.command == "doctor":
        return _doctor(root)
    if args.command == "sync-feishu":
        _load_local_env(root / ".env")
        chat_name = args.chat_name or os.environ.get("FEISHU_CHAT_NAME", "SignalBloom 私人资讯")
        try:
            result = sync_output(
                args.output,
                app_id=os.environ.get("FEISHU_APP_ID", ""),
                app_secret=os.environ.get("FEISHU_APP_SECRET", ""),
                chat_name=chat_name,
                dry_run=args.dry_run,
            )
        except (FeishuError, OSError) as exc:
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    seed = args.seed.resolve()
    seed_value = json.loads(seed.read_text(encoding="utf-8"))
    if seed_value.get("edition_date") != args.date:
        raise SystemExit(
            f"date mismatch: --date is {args.date}, seed.edition_date is {seed_value.get('edition_date')}"
        )
    output = (args.output or (root / "outputs" / args.date)).resolve()
    provider = DemoProvider() if args.provider == "demo" else CodexExecProvider(root, args.timeout)
    try:
        manifest = NewsPipeline(root, provider).run(
            seed_path=seed,
            output_dir=output,
            platform_rules_path=args.platform_rules.resolve() if args.platform_rules else None,
            force=args.force,
            provider_name=args.provider,
        )
    except (FileExistsError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": str(exc),
                    "hint": "Use another output directory, or pass --force only when replacement is intentional.",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] == "completed" else 2
