"""
json_drop_collector.py
Đọc file JSON từ data/inbox/, trả về danh sách bài viết, rồi chuyển sang data/processed/.
Định dạng JSON đầu vào (1 bài hoặc mảng nhiều bài):
{
  "group": "Group 1",
  "post_id": "unique-id-123",
  "text": "원룸 양도합니다...",
  "url": "https://www.facebook.com/groups/.../posts/123",
  "created_at": "2026-11-02T15:00:00+09:00"
}
"""

import json
import shutil
from pathlib import Path
from system.logger import logger

INBOX_DIR = Path("data/inbox")
PROCESSED_DIR = Path("data/processed")

INBOX_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def collect_posts() -> list[dict]:
    posts = []
    json_files = sorted(INBOX_DIR.glob("*.json"))

    if not json_files:
        logger.debug("No JSON files in data/inbox/")
        return posts

    for file_path in json_files:
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
            # Chấp nhận cả dict đơn lẻ hoặc list
            items = raw if isinstance(raw, list) else [raw]
            for item in items:
                if _validate(item, file_path.name):
                    posts.append(item)
            # Di chuyển sang processed sau khi đọc xong
            dest = PROCESSED_DIR / file_path.name
            shutil.move(str(file_path), str(dest))
            logger.info("Processed file moved: %s → data/processed/", file_path.name)
        except Exception:
            logger.exception("Failed to read %s", file_path.name)

    return posts


def _validate(item: dict, filename: str) -> bool:
    required = ["post_id", "text", "group"]
    for field in required:
        if not item.get(field):
            logger.warning("Missing field '%s' in %s, skipping", field, filename)
            return False
    return True
