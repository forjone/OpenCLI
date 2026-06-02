from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from core.models import Account, PostResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    platform TEXT NOT NULL,
    name     TEXT NOT NULL,
    cookie_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (platform, name)
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    account  TEXT NOT NULL,
    title    TEXT NOT NULL,
    video_path TEXT NOT NULL,
    success  INTEGER NOT NULL,
    post_url TEXT,
    error    TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posts_platform_account ON posts(platform, account);
"""


@contextmanager
def _conn(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    with _conn(db_path) as c:
        c.executescript(_SCHEMA)


def save_account(db_path: Path, account: Account) -> None:
    with _conn(db_path) as c:
        c.execute(
            "INSERT OR REPLACE INTO accounts (platform, name, cookie_path, created_at) "
            "VALUES (?, ?, ?, ?)",
            (account.platform, account.name, str(account.cookie_path), _now()),
        )


def list_accounts(db_path: Path, platform: str | None = None) -> list[Account]:
    with _conn(db_path) as c:
        if platform:
            rows = c.execute(
                "SELECT platform, name, cookie_path FROM accounts WHERE platform = ?",
                (platform,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT platform, name, cookie_path FROM accounts"
            ).fetchall()
    return [
        Account(platform=r["platform"], name=r["name"], cookie_path=Path(r["cookie_path"]))
        for r in rows
    ]


def record_post(db_path: Path, video_path: Path, title: str, result: PostResult) -> int:
    with _conn(db_path) as c:
        cur = c.execute(
            "INSERT INTO posts (platform, account, title, video_path, success, "
            "post_url, error, raw_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                result.platform,
                result.account,
                title,
                str(video_path),
                1 if result.success else 0,
                result.post_url,
                result.error,
                json.dumps(result.raw, ensure_ascii=False),
                _now(),
            ),
        )
        return cur.lastrowid


def list_posts(db_path: Path, limit: int = 50) -> list[dict]:
    with _conn(db_path) as c:
        rows = c.execute(
            "SELECT * FROM posts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
