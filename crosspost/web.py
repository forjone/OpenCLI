"""FastAPI backend for the crosspost web UI.

Endpoints (MVP):
  GET  /api/health           — liveness
  GET  /api/platforms        — list supported platforms + their constraints
  GET  /api/accounts         — list saved accounts (from SQLite)
  POST /api/publish          — fan out a video to multiple targets
  GET  /api/posts            — recent post history

Login flows (QR code via SSE) and account management are TODO — left as the
next milestone, since the SAU vendor code already exposes async qrcode_callback
hooks we can wire to a Server-Sent Events stream.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from cli import _build_adapter, _build_uploader  # reuse factory functions

try:
    from conf import COOKIES_DIR, DATA_DIR, DATABASE_URL
except ImportError as exc:
    raise RuntimeError("Copy conf.example.py to conf.py first.") from exc

from core.models import VideoPost
from core.orchestrator import PublishTarget, publish
from storage import init_db, list_accounts, list_posts, record_post

DB_PATH = Path(DATABASE_URL.replace("sqlite:///", ""))


app = FastAPI(title="crosspost", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    init_db(DB_PATH)


class PlatformInfo(BaseModel):
    platform: str
    max_title_len: int
    max_desc_len: int
    max_tags: int
    required_extras: list[str]


class PublishTargetSpec(BaseModel):
    platform: str
    account: str


class PublishRequest(BaseModel):
    file: str
    title: str
    description: str = ""
    tags: list[str] = []
    cover: str | None = None
    schedule_at: str | None = None
    targets: list[PublishTargetSpec]
    extras: dict[str, dict] = {}
    use_ai: bool = True
    dry_run: bool = False


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/platforms", response_model=list[PlatformInfo])
def platforms() -> list[PlatformInfo]:
    out: list[PlatformInfo] = []
    for p in ("douyin", "bilibili", "xiaohongshu", "tencent"):
        u = _build_uploader(p)
        out.append(
            PlatformInfo(
                platform=u.platform,
                max_title_len=u.max_title_len,
                max_desc_len=u.max_desc_len,
                max_tags=u.max_tags,
                required_extras=sorted(u.required_extras),
            )
        )
    return out


@app.get("/api/accounts")
def accounts(platform: str | None = None) -> list[dict]:
    return [
        {"platform": a.platform, "name": a.name, "cookie_path": str(a.cookie_path)}
        for a in list_accounts(DB_PATH, platform=platform)
    ]


@app.get("/api/posts")
def posts(limit: int = 50) -> list[dict]:
    return list_posts(DB_PATH, limit=limit)


@app.post("/api/publish")
async def post_publish(req: PublishRequest) -> dict:
    if not req.targets:
        raise HTTPException(400, "at least one target required")

    flat_extras: dict = {}
    for _platform, kv in req.extras.items():
        flat_extras.update(kv)

    master = VideoPost(
        video_path=Path(req.file),
        title=req.title,
        description=req.description,
        tags=req.tags,
        cover_path=Path(req.cover) if req.cover else None,
        platform_extras=flat_extras,
    )

    targets = [
        PublishTarget(uploader=_build_uploader(t.platform), account=t.account)
        for t in req.targets
    ]
    adapter = _build_adapter(disable_ai=not req.use_ai)
    results = await publish(master, targets, adapter=adapter, dry_run=req.dry_run)
    for r in results:
        record_post(DB_PATH, master.video_path, master.title, r)
    return {"results": [r.__dict__ for r in results]}
