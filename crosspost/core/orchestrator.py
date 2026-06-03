from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from core.interfaces import Uploader
from core.models import PostResult, VideoPost

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


@dataclass
class PublishTarget:
    """One destination: a platform uploader + an account name on that platform."""
    uploader: Uploader
    account: str


async def _emit(cb: ProgressCallback | None, **fields: Any) -> None:
    if cb is None:
        return
    result = cb(fields)
    if inspect.isawaitable(result):
        await result


async def publish(
    master: VideoPost,
    targets: list[PublishTarget],
    adapter=None,
    dry_run: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> list[PostResult]:
    """Fan out a single video to multiple platform accounts in parallel.

    If `progress_callback` is given, it is called (sync or async) with dicts
    describing each stage transition:
        {"event": "started", "total": N}
        {"event": "adapt_start", "platform": ..., "account": ...}
        {"event": "adapt_done",  "platform": ..., "account": ..., "title": ..., "tags": [...]}
        {"event": "upload_start", "platform": ..., "account": ...}
        {"event": "upload_done",  "platform": ..., "account": ..., "success": bool, "error": str|None}
        {"event": "complete", "count": N}
    """
    # Pre-validate hard constraints. Without an adapter we can't auto-fix.
    if adapter is None:
        errors: dict[str, list[str]] = {}
        for t in targets:
            errs = t.uploader.validate(master)
            if errs:
                errors[f"{t.uploader.platform}:{t.account}"] = errs
        if errors:
            await _emit(progress_callback, event="validation_failed", errors=errors)
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

    await _emit(progress_callback, event="started", total=len(targets))

    async def _one(target: PublishTarget) -> PostResult:
        platform = target.uploader.platform
        post = master

        if adapter is not None:
            await _emit(progress_callback, event="adapt_start", platform=platform, account=target.account)
            post = await adapter.adapt(master, target.uploader)
            await _emit(
                progress_callback, event="adapt_done", platform=platform, account=target.account,
                title=post.title, tags=post.tags,
            )

        if dry_run:
            await _emit(
                progress_callback, event="upload_done", platform=platform, account=target.account,
                success=True, error=None, dry_run=True,
            )
            return PostResult(
                success=True, platform=platform, account=target.account,
                raw={"dry_run": True, "title": post.title, "tags": post.tags},
            )

        await _emit(progress_callback, event="upload_start", platform=platform, account=target.account)
        try:
            result = await target.uploader.upload(target.account, post)
        except Exception as exc:
            result = PostResult(
                success=False, platform=platform, account=target.account,
                error=f"unhandled: {exc!r}",
            )
        await _emit(
            progress_callback, event="upload_done", platform=platform, account=target.account,
            success=result.success, error=result.error,
        )
        return result

    results = await asyncio.gather(*[_one(t) for t in targets])
    await _emit(progress_callback, event="complete", count=len(results))
    return results
