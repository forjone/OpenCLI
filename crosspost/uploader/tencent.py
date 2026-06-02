"""Crosspost Uploader implementation for WeChat Channels (Tencent)."""
from __future__ import annotations

from pathlib import Path

from core.interfaces import Uploader
from core.models import PostResult, VideoPost
from uploader.tencent_uploader.main import (
    TencentVideo,
    cookie_auth,
    weixin_setup,
)


class TencentUploader(Uploader):
    platform = "tencent"
    max_title_len = 22
    max_desc_len = 600
    max_tags = 10

    def __init__(self, cookies_dir: Path):
        self.cookies_dir = cookies_dir
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def _cookie_path(self, account: str) -> Path:
        return self.cookies_dir / f"tencent_{account}.json"

    async def login(self, account: str, qrcode_callback=None) -> bool:
        return await weixin_setup(
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
            video = TencentVideo(
                title=post.title,
                file_path=str(post.video_path),
                tags=post.tags,
                publish_date=post.schedule_at or 0,
                account_file=str(self._cookie_path(account)),
                category=post.platform_extras.get("category"),
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
