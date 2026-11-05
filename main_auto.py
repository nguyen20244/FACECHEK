"""
main_auto.py

Vòng lặp chính dùng CloakBrowser tự động thu thập bài từ Facebook.

FIX #4: Heartbeat chạy SAU run_once (không trước) — tránh báo "bình thường" khi cycle đang fail
FIX #5: elapsed chỉ tính thời gian run_once(), không bao gồm heartbeat

Chạy:
    python main_auto.py
"""

import json
import time
from pathlib import Path

# FIX #5 + #6 + #7: dùng wrapper an toàn — cap posts, guard text None, normalize
from browser.fb_collector_safe import collect_posts_safe as collect_from_facebook
from filters.strict_filter import classify
from database.db import insert_post, mark_notified
from telegram.notifier import send_post, send_heartbeat
from system.logger import logger

GROUP_CONFIG = json.loads(Path("config/groups.json").read_text(encoding="utf-8"))
INTERVAL = int(GROUP_CONFIG.get("poll_interval_seconds", 90))

_HEARTBEAT_EVERY = max(1, int(6 * 3600 / INTERVAL))
_cycle = 0


def run_once():
    posts = collect_from_facebook()
    logger.info("Collected %d post(s) from Facebook", len(posts))

    new_count = 0
    matched_count = 0

    for post in posts:
        # FIX #8: Dedup TRƯỚC classify
        from database.db import post_exists  # noqa: PLC0415
        if post_exists(post["post_id"]):
            continue

        result = classify(post["text"])
        is_new = insert_post(post, result)

        if not is_new:
            continue  # race condition

        new_count += 1

        if result["matched"]:
            matched_count += 1
            try:
                send_post(post, result)
                mark_notified(post["post_id"])
                logger.info(
                    "✅ Notified | post=%s | confidence=%s | keywords=%s",
                    post["post_id"], result["confidence"], result["matched_transfer"],
                )
            except Exception:
                logger.exception("Telegram failed for %s", post["post_id"])
        else:
            logger.debug(
                "❌ Filtered | post=%s | reason=%s",
                post["post_id"], result["reason"],
            )

    logger.info("Cycle done: %d new, %d matched/notified", new_count, matched_count)


def main():
    global _cycle

    logger.info("=" * 60)
    logger.info("Facebook Housing Monitor AUTO started")
    logger.info("Interval: %ss | Mode: CloakBrowser | Filter: STRICT", INTERVAL)
    logger.info("=" * 60)

    while True:
        _cycle += 1

        # FIX #5: bắt đầu đếm elapsed CHỈ từ đây — không tính heartbeat
        started = time.time()

        try:
            run_once()
        except Exception:
            logger.exception("Cycle %d failed", _cycle)

        elapsed = time.time() - started

        # FIX #4: heartbeat SAU run_once — đảm bảo cycle thực sự đã chạy xong
        if _cycle % _HEARTBEAT_EVERY == 0:
            try:
                send_heartbeat()
            except Exception:
                logger.warning("Heartbeat failed (cycle %d)", _cycle)

        sleep_time = max(1, INTERVAL - elapsed)
        logger.info("Sleeping %.0fs until next cycle...", sleep_time)
        time.sleep(sleep_time)


if __name__ == "__main__":
    main()
