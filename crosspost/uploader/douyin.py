"""Crosspost Uploader implementation for Douyin.

Delegates the actual browser automation to the vendored SAU code in
`uploader/douyin_uploader/main.py`. This file is the bridge between the
crosspost Uploader contract and SAU's existing functions.
"""
from __future__ import annotations

from pathlib import Path

from core.interfaces import Uploader
from core.models import PostResult, VideoPost
from uploader.douyin_uploader.main import (
    DouYinVideo,
    cookie_auth,
    douyin_setup,
)


class DouyinUploader(Uploader):
    platform = "douyin"
    max_title_len = 30
    max_desc_len = 1000
    max_tags = 5

    def __init__(self, cookies_dir: Path):
        self.cookies_dir = cookies_dir
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def _cookie_path(self, account: str) -> Path:
        return self.cookies_dir / f"douyin_{account}.json"

    async def login(self, account: str, qrcode_callback=None) -> bool:
        return await douyin_setup(
            str(self._cookie_path(account)),
            handle=True,
            qrcode_callback=qrcode_callback,
        )

    async def check_session(self, account: str) -> bool:
        path = self._cookie_path(account)
        if not path.exists():
            return False
        return await cookie_auth(str(path))

    async def upload(self, account: str, post: VideoPost) -> PostResult:
        try:
            video = DouYinVideo(
                title=post.title,
                file_path=str(post.video_path),
                tags=post.tags,
                publish_date=post.schedule_at or 0,
                account_file=str(self._cookie_path(account)),
                desc=post.description or None,
                thumbnail_landscape_path=str(post.cover_path) if post.cover_path else None,
                productLink=post.platform_extras.get("product_link", ""),
                productTitle=post.platform_extras.get("product_title", ""),
            )
            await video.start()
            return PostResult(
                success=True,
                platform=self.platform,
                account=account,
                raw={"title": post.title},
            )
        except Exception as exc:
            return PostResult(
                success=False,
                platform=self.platform,
                account=account,
                error=repr(exc),
            )
