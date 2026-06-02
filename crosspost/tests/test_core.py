"""Architectural smoke tests — no platform network calls."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from adapters.base import NullAdapter
from core.interfaces import Uploader
from core.models import PostResult, VideoPost
from core.orchestrator import PublishTarget, publish


class _FakeUploader(Uploader):
    platform = "fake"
    max_title_len = 10
    max_tags = 3

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[VideoPost] = []

    async def login(self, account, qrcode_callback=None):
        return True

    async def check_session(self, account):
        return True

    async def upload(self, account, post: VideoPost) -> PostResult:
        self.calls.append(post)
        if self.fail:
            return PostResult(success=False, platform=self.platform, account=account, error="boom")
        return PostResult(success=True, platform=self.platform, account=account, post_url="x")


def _master(tmp_path: Path) -> VideoPost:
    f = tmp_path / "demo.mp4"
    f.write_bytes(b"\x00")
    return VideoPost(video_path=f, title="hi", tags=["a"])


async def test_publish_dry_run_returns_one_result_per_target(tmp_path):
    up = _FakeUploader()
    targets = [PublishTarget(uploader=up, account="a"), PublishTarget(uploader=up, account="b")]
    results = await publish(_master(tmp_path), targets, adapter=NullAdapter(), dry_run=True)
    assert len(results) == 2
    assert all(r.success for r in results)
    assert up.calls == []  # dry_run skipped real upload


async def test_publish_propagates_uploader_errors(tmp_path):
    up = _FakeUploader(fail=True)
    targets = [PublishTarget(uploader=up, account="a")]
    [result] = await publish(_master(tmp_path), targets, adapter=NullAdapter())
    assert not result.success
    assert result.error == "boom"


async def test_validate_rejects_overlong_title(tmp_path):
    up = _FakeUploader()
    post = VideoPost(video_path=tmp_path / "x.mp4", title="x" * 11, tags=[])
    (tmp_path / "x.mp4").write_bytes(b"\x00")
    errs = up.validate(post)
    assert any("标题超长" in e for e in errs)


async def test_validate_rejects_missing_required_extras(tmp_path):
    class _Need(_FakeUploader):
        required_extras = {"tid"}

    up = _Need()
    post = VideoPost(video_path=tmp_path / "x.mp4", title="x", tags=[])
    (tmp_path / "x.mp4").write_bytes(b"\x00")
    errs = up.validate(post)
    assert any("tid" in e for e in errs)
