from __future__ import annotations

from abc import ABC, abstractmethod

from core.models import PostResult, VideoPost


class Uploader(ABC):
    """Common contract every platform uploader must implement.

    Subclasses set the metadata below so the orchestrator + adapter can
    pre-validate posts and tune AI rewrites without platform-specific code.
    """

    platform: str = ""
    max_title_len: int = 100
    max_desc_len: int = 5000
    max_tags: int = 10
    required_extras: set[str] = set()  # e.g. {"tid"} for Bilibili

    @abstractmethod
    async def login(self, account: str, qrcode_callback=None) -> bool:
        """Trigger interactive login (QR code). Returns True on success."""

    @abstractmethod
    async def check_session(self, account: str) -> bool:
        """Return True if the saved cookie is still valid."""

    @abstractmethod
    async def upload(self, account: str, post: VideoPost) -> PostResult:
        """Publish a single post. Must not raise — wrap errors in PostResult."""

    def validate(self, post: VideoPost) -> list[str]:
        """Return a list of human-readable validation errors (empty if OK)."""
        errors: list[str] = []
        if len(post.title) > self.max_title_len:
            errors.append(
                f"{self.platform}: 标题超长 ({len(post.title)} > {self.max_title_len})"
            )
        if len(post.tags) > self.max_tags:
            errors.append(
                f"{self.platform}: 标签过多 ({len(post.tags)} > {self.max_tags})"
            )
        missing = self.required_extras - set(post.platform_extras)
        if missing:
            errors.append(f"{self.platform}: 缺少必填字段 {sorted(missing)}")
        if not post.video_path.exists():
            errors.append(f"{self.platform}: 视频文件不存在 {post.video_path}")
        return errors
