"""
main_auto.py
Vòng lặp chính dùng CloakBrowser tự động thu thập bài từ Facebook.
Thay thế main.py (vốn dùng json_drop_collector).

Chạy:
  python main_auto.py
"""

import json
import time
from pathlib import Path
from browser.fb_collector import collect_from_facebook
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

    new_count      = 0
    matched_count  = 0

    for post in posts:
        result = classify(post["text"])
        is_new = insert_post(post, result)
        if not is_new:
            continue
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
        started = time.time()

        if _cycle % _HEARTBEAT_EVERY == 0:
            try:
                send_heartbeat()
            except Exception:
                pass

        try:
            run_once()
        except Exception:
            logger.exception("Cycle %d failed", _cycle)

        elapsed = time.time() - started
        sleep_time = max(1, INTERVAL - elapsed)
        logger.info("Sleeping %.0fs until next cycle...", sleep_time)
        time.sleep(sleep_time)


if __name__ == "__main__":
    main()
