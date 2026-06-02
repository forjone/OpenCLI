from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.interfaces import Uploader
from core.models import PostResult, VideoPost


@dataclass
class PublishTarget:
    """One destination: a platform uploader + an account name on that platform."""
    uploader: Uploader
    account: str


async def publish(
    master: VideoPost,
    targets: list[PublishTarget],
    adapter=None,
    dry_run: bool = False,
) -> list[PostResult]:
    """Fan out a single video to multiple platform accounts in parallel.

    If `adapter` is provided, each target gets a platform-specific rewrite of
    the master post via `adapter.adapt(master, target.uploader)`. Otherwise the
    master post is used as-is.
    """
    # 1. Pre-validate against each platform's hard constraints
    errors: dict[str, list[str]] = {}
    for t in targets:
        errs = t.uploader.validate(master)
        if errs:
            errors[f"{t.uploader.platform}:{t.account}"] = errs
    if errors and not adapter:
        # Without an adapter we can't auto-fix constraint violations
        return [
            PostResult(
                success=False,
                platform=t.uploader.platform,
                account=t.account,
                error="; ".join(errors.get(f"{t.uploader.platform}:{t.account}", [])),
            )
            for t in targets
            if f"{t.uploader.platform}:{t.account}" in errors
        ]

    async def _one(target: PublishTarget) -> PostResult:
        post = master
        if adapter is not None:
            post = await adapter.adapt(master, target.uploader)
        if dry_run:
            return PostResult(
                success=True,
                platform=target.uploader.platform,
                account=target.account,
                raw={"dry_run": True, "title": post.title, "tags": post.tags},
            )
        try:
            return await target.uploader.upload(target.account, post)
        except Exception as exc:  # uploader should not raise, but defend anyway
            return PostResult(
                success=False,
                platform=target.uploader.platform,
                account=target.account,
                error=f"unhandled: {exc!r}",
            )

    return await asyncio.gather(*[_one(t) for t in targets])
