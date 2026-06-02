"""Crosspost Uploader implementation for Bilibili.

Bilibili uses the `biliup` CLI under the hood (auto-downloaded by
`uploader/bilibili_uploader/runtime.py`). Unlike the Playwright-based
platforms it has no QR-code login flow exposed by SAU — the user logs in
via biliup directly the first time.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from core.interfaces import Uploader
from core.models import PostResult, VideoPost
from uploader.bilibili_uploader.runtime import (
    ensure_biliup_binary,
    run_biliup_command,
)


class BilibiliUploader(Uploader):
    platform = "bilibili"
    max_title_len = 80
    max_desc_len = 2000
    max_tags = 10
    required_extras = {"tid"}

    def __init__(self, cookies_dir: Path):
        self.cookies_dir = cookies_dir
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def _cookie_path(self, account: str) -> Path:
        return self.cookies_dir / f"bilibili_{account}.json"

    async def login(self, account: str, qrcode_callback=None) -> bool:
        ensure_biliup_binary(force_check=False)
        cookie_path = self._cookie_path(account)
        # biliup login writes a cookie file. Interactive — user scans in terminal.
        proc = await asyncio.to_thread(
            run_biliup_command,
            ["--user-cookie", str(cookie_path), "login"],
            True,
        )
        return proc.returncode == 0

    async def check_session(self, account: str) -> bool:
        cookie_path = self._cookie_path(account)
        if not cookie_path.exists():
            return False
        proc = await asyncio.to_thread(
            run_biliup_command,
            ["--user-cookie", str(cookie_path), "renew"],
            False,
        )
        return proc.returncode == 0

    async def upload(self, account: str, post: VideoPost) -> PostResult:
        cookie_path = self._cookie_path(account)
        tid = str(post.platform_extras["tid"])
        args = [
            "--user-cookie", str(cookie_path),
            "upload",
            "--title", post.title,
            "--desc", post.description or "",
            "--tid", tid,
            "--tag", ",".join(post.tags),
        ]
        if post.cover_path:
            args.extend(["--cover", str(post.cover_path)])
        args.append(str(post.video_path))
        try:
            proc = await asyncio.to_thread(run_biliup_command, args, False)
            ok = proc.returncode == 0
            return PostResult(
                success=ok,
                platform=self.platform,
                account=account,
                error=None if ok else proc.stderr[-500:],
                raw={"stdout_tail": (proc.stdout or "")[-500:]},
            )
        except Exception as exc:
            return PostResult(
                success=False,
                platform=self.platform,
                account=account,
                error=repr(exc),
            )
