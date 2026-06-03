"""FastAPI backend for the crosspost web UI.

Endpoints:
  GET  /api/health           — liveness
  GET  /api/platforms        — list supported platforms + their constraints
  GET  /api/accounts         — list saved accounts (from SQLite)
  POST /api/login/start      — kick off a login task, returns {task_id}
  GET  /api/login/stream/{id}— SSE stream of QR payloads + final status
  POST /api/publish          — fan out a video to multiple targets
  GET  /api/posts            — recent post history
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from cli import _build_adapter, _build_uploader  # reuse factory functions

try:
    from conf import COOKIES_DIR, DATABASE_URL
except ImportError as exc:
    raise RuntimeError("Copy conf.example.py to conf.py first.") from exc

from core.models import Account, VideoPost
from core.orchestrator import PublishTarget, publish
from storage import init_db, list_accounts, list_posts, record_post, save_account

DB_PATH = Path(DATABASE_URL.replace("sqlite:///", ""))


app = FastAPI(title="crosspost", version="0.1.0")

# Allow the Vite dev server (5173) and same-origin prod access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db(DB_PATH)


# ---------- schemas ----------

class PlatformInfo(BaseModel):
    platform: str
    max_title_len: int
    max_desc_len: int
    max_tags: int
    required_extras: list[str]


class LoginStartRequest(BaseModel):
    platform: str
    account: str


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
    extras: dict[str, Any] = {}
    use_ai: bool = True
    dry_run: bool = False


# ---------- simple endpoints ----------

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


# ---------- login flow (SSE) ----------

_login_queues: dict[str, asyncio.Queue] = {}


@app.post("/api/login/start")
async def login_start(req: LoginStartRequest) -> dict:
    task_id = uuid.uuid4().hex
    queue: asyncio.Queue = asyncio.Queue()
    _login_queues[task_id] = queue

    async def qrcode_callback(payload: dict) -> None:
        await queue.put({"event": "qrcode", "payload": payload})

    async def runner() -> None:
        try:
            uploader = _build_uploader(req.platform)
            ok = await uploader.login(req.account, qrcode_callback=qrcode_callback)
            if ok:
                save_account(
                    DB_PATH,
                    Account(
                        platform=req.platform,
                        name=req.account,
                        cookie_path=uploader._cookie_path(req.account),  # type: ignore[attr-defined]
                    ),
                )
            await queue.put(
                {"event": "done", "success": ok, "platform": req.platform, "account": req.account}
            )
        except Exception as exc:  # noqa: BLE001
            await queue.put({"event": "error", "message": repr(exc)})

    asyncio.create_task(runner())
    return {"task_id": task_id}


@app.get("/api/login/stream/{task_id}")
async def login_stream(task_id: str) -> StreamingResponse:
    queue = _login_queues.get(task_id)
    if not queue:
        raise HTTPException(404, "unknown task_id")

    async def gen():
        try:
            while True:
                msg = await asyncio.wait_for(queue.get(), timeout=300)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                if msg.get("event") in ("done", "error"):
                    break
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'event': 'timeout'})}\n\n"
        finally:
            _login_queues.pop(task_id, None)

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------- publish ----------

# ---------- static frontend (production) ----------

_FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")


@app.post("/api/publish")
async def post_publish(req: PublishRequest) -> dict:
    if not req.targets:
        raise HTTPException(400, "at least one target required")

    flat_extras: dict = {}
    for _platform, kv in req.extras.items():
        if isinstance(kv, dict):
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
