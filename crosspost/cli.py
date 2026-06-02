"""crosspost CLI — fan a video out to multiple platforms in one command."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Ensure conf.py exists (fall back to conf.example.py contents at runtime)
try:
    import conf  # noqa: F401
except ImportError:
    print("⚠️  conf.py not found — copy conf.example.py to conf.py first.", file=sys.stderr)
    sys.exit(2)

from conf import COOKIES_DIR, DATA_DIR, DATABASE_URL  # noqa: E402

from core.models import VideoPost  # noqa: E402
from core.orchestrator import PublishTarget, publish  # noqa: E402

PLATFORMS = ("douyin", "bilibili", "xiaohongshu", "tencent")


def _build_uploader(platform: str):
    cookies_dir = Path(COOKIES_DIR)
    if platform == "douyin":
        from uploader.douyin import DouyinUploader
        return DouyinUploader(cookies_dir)
    if platform == "bilibili":
        from uploader.bilibili import BilibiliUploader
        return BilibiliUploader(cookies_dir)
    if platform == "xiaohongshu":
        from uploader.xiaohongshu import XiaohongshuUploader
        return XiaohongshuUploader(cookies_dir)
    if platform == "tencent":
        from uploader.tencent import TencentUploader
        return TencentUploader(cookies_dir)
    raise ValueError(f"unknown platform: {platform}")


def _build_adapter(disable_ai: bool):
    if disable_ai:
        from adapters.base import NullAdapter
        return NullAdapter()
    from adapters.base import PlatformAdapter
    from adapters.llm import ClaudeClient
    return PlatformAdapter(ClaudeClient())


def _parse_schedule(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


async def cmd_login(args):
    up = _build_uploader(args.platform)
    ok = await up.login(args.account)
    print("✅ logged in" if ok else "❌ login failed")
    return 0 if ok else 1


async def cmd_check(args):
    up = _build_uploader(args.platform)
    ok = await up.check_session(args.account)
    print("valid" if ok else "invalid")
    return 0 if ok else 1


async def cmd_publish(args):
    targets_spec: list[tuple[str, str]] = []
    for spec in args.targets:
        if ":" not in spec:
            print(f"bad target {spec!r}, expected platform:account", file=sys.stderr)
            return 2
        platform, account = spec.split(":", 1)
        targets_spec.append((platform, account))

    extras: dict[str, dict] = {}
    if args.extras:
        for piece in args.extras:
            platform, kv = piece.split(":", 1)
            k, v = kv.split("=", 1)
            extras.setdefault(platform, {})[k] = v

    targets = []
    for platform, account in targets_spec:
        uploader = _build_uploader(platform)
        targets.append(PublishTarget(uploader=uploader, account=account))

    master = VideoPost(
        video_path=Path(args.file),
        title=args.title,
        description=args.desc or "",
        tags=[t.strip() for t in (args.tags or "").split(",") if t.strip()],
        cover_path=Path(args.cover) if args.cover else None,
        schedule_at=_parse_schedule(args.schedule),
        platform_extras={p: e for p, e in extras.items()},
    )

    # Wire per-platform extras into master.platform_extras as a flat dict the
    # uploader will pick up via .get on its own keys.
    flat_extras: dict = {}
    for p, e in extras.items():
        flat_extras.update(e)
    master.platform_extras = flat_extras

    adapter = _build_adapter(disable_ai=args.no_ai)
    results = await publish(master, targets, adapter=adapter, dry_run=args.dry_run)
    print(json.dumps([r.__dict__ for r in results], ensure_ascii=False, default=str, indent=2))
    return 0 if all(r.success for r in results) else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="crosspost", description="One video → many platforms.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_login = sub.add_parser("login", help="Log into one platform (QR code)")
    p_login.add_argument("--platform", required=True, choices=PLATFORMS)
    p_login.add_argument("--account", required=True)
    p_login.set_defaults(func=cmd_login)

    p_check = sub.add_parser("check", help="Verify a saved cookie is still valid")
    p_check.add_argument("--platform", required=True, choices=PLATFORMS)
    p_check.add_argument("--account", required=True)
    p_check.set_defaults(func=cmd_check)

    p_pub = sub.add_parser("publish", help="Publish one video to multiple platforms")
    p_pub.add_argument("--file", required=True, help="Video file path")
    p_pub.add_argument("--title", required=True)
    p_pub.add_argument("--desc", default="")
    p_pub.add_argument("--tags", default="", help="Comma-separated")
    p_pub.add_argument("--cover", default=None)
    p_pub.add_argument("--schedule", default=None, help="YYYY-MM-DD HH:MM")
    p_pub.add_argument(
        "--targets",
        nargs="+",
        required=True,
        help="One or more platform:account pairs, e.g. douyin:main bilibili:main",
    )
    p_pub.add_argument(
        "--extras",
        nargs="*",
        default=[],
        help="Per-platform required extras, e.g. bilibili:tid=21",
    )
    p_pub.add_argument("--no-ai", action="store_true", help="Skip AI rewriting")
    p_pub.add_argument("--dry-run", action="store_true", help="Don't actually upload")
    p_pub.set_defaults(func=cmd_publish)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
