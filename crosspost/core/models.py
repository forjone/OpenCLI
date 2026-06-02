from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class VideoPost:
    """Master copy of a video to publish. Each platform may rewrite it via an adapter."""
    video_path: Path
    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    cover_path: Path | None = None
    schedule_at: datetime | None = None
    platform_extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class PostResult:
    success: bool
    platform: str
    account: str
    post_url: str | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Account:
    platform: str
    name: str
    cookie_path: Path
