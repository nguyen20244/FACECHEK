"""
db.py
SQLite: lưu lịch sử bài viết, chống trùng theo post_id.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/housing_monitor.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                post_id     TEXT PRIMARY KEY,
                group_name  TEXT,
                url         TEXT,
                text        TEXT,
                created_at  TEXT,
                matched     INTEGER,
                confidence  TEXT,
                reason      TEXT,
                keywords    TEXT,
                notified    INTEGER DEFAULT 0,
                inserted_at TEXT
            )
        """)
        conn.commit()


def insert_post(post: dict, result: dict) -> bool:
    """Chèn bài mới. Trả về True nếu là bài mới, False nếu đã tồn tại."""
    init_db()
    post_id = post.get("post_id", "")
    with _get_conn() as conn:
        existing = conn.execute(
            "SELECT post_id FROM posts WHERE post_id = ?", (post_id,)
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """INSERT INTO posts
               (post_id, group_name, url, text, created_at, matched, confidence, reason, keywords, inserted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                post_id,
                post.get("group", ""),
                post.get("url", ""),
                post.get("text", ""),
                post.get("created_at", ""),
                int(result.get("matched", False)),
                result.get("confidence", ""),
                result.get("reason", ""),
                json.dumps(result.get("matched_transfer", []), ensure_ascii=False),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    return True


def post_exists(post_id: str) -> bool:
    """Kiểm tra nhanh post_id đã có trong DB chưa — dùng trước classify() để skip sớm."""
    init_db()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM posts WHERE post_id = ? LIMIT 1", (post_id,)
        ).fetchone()
    return row is not None


def mark_notified(post_id: str):
    init_db()
    with _get_conn() as conn:
        conn.execute(
            "UPDATE posts SET notified = 1 WHERE post_id = ?", (post_id,)
        )
        conn.commit()


def get_recent_posts(limit: int = 50) -> list[dict]:
    init_db()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM posts ORDER BY inserted_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
