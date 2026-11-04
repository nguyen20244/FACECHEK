"""
main.py
Vòng lặp chính: thu thập → lọc → lưu DB → thông báo Telegram.
Chu kỳ mặc định: 90 giây (cấu hình trong config/groups.json).
"""

import json
import time
from pathlib import Path
from collector.json_drop_collector import collect_posts
from filters.strict_filter import classify
from database.db import insert_post, mark_notified
from telegram.notifier import send_post
from system.logger import logger

GROUP_CONFIG = json.loads(Path("config/groups.json").read_text(encoding="utf-8"))
INTERVAL = int(GROUP_CONFIG.get("poll_interval_seconds", 90))

# Đếm chu kỳ để gửi heartbeat mỗi 6 giờ
_HEARTBEAT_EVERY = max(1, int(6 * 3600 / INTERVAL))
_cycle_count = 0


def run_once():
    posts = collect_posts()
    logger.info("Collected %d post(s) from inbox", len(posts))
    for post in posts:
        result = classify(post["text"])
        is_new = insert_post(post, result)
        if not is_new:
            logger.debug("Duplicate skipped: %s", post["post_id"])
            continue

        if result["matched"]:
            try:
                send_post(post, result)
                mark_notified(post["post_id"])
                logger.info(
                    "✅ Notified | post=%s | confidence=%s | keywords=%s",
                    post["post_id"],
                    result["confidence"],
                    result["matched_transfer"],
                )
            except Exception:
                logger.exception("Telegram failed for %s", post["post_id"])
        else:
            logger.info(
                "❌ Filtered  | post=%s | reason=%s",
                post["post_id"],
                result["reason"],
            )


def main():
    global _cycle_count
    logger.info("=" * 60)
    logger.info("Facebook Housing Monitor started")
    logger.info("Interval: %s seconds | Filter: STRICT", INTERVAL)
    logger.info("=" * 60)

    while True:
        started = time.time()
        _cycle_count += 1

        # Heartbeat mỗi 6 giờ
        if _cycle_count % _HEARTBEAT_EVERY == 0:
            try:
                from telegram.notifier import send_heartbeat
                send_heartbeat()
            except Exception:
                pass

        try:
            run_once()
        except Exception:
            logger.exception("Cycle %d failed", _cycle_count)

        elapsed = time.time() - started
        sleep_time = max(1, INTERVAL - elapsed)
        logger.debug("Cycle %d done in %.1fs, sleeping %.1fs", _cycle_count, elapsed, sleep_time)
        time.sleep(sleep_time)


if __name__ == "__main__":
    main()
