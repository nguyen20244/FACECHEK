"""
main.py

Vòng lặp chính: thu thập từ Facebook (CloakBrowser) → lọc → lưu DB → thông báo Telegram.
Chu kỳ mặc định: 90 giây (cấu hình trong config/groups.json).

FIX #2: Đổi collector từ json_drop_collector → fb_collector (đúng nguồn tự động)
FIX #3: Import send_heartbeat ở top-level thay vì lồng trong loop
FIX #4 (log): Filtered posts dùng logger.debug() thay vì logger.info()
"""

import json
import time
from pathlib import Path

# FIX #2: dùng fb_collector_safe — nguồn tự động + guard text + cap posts
from browser.fb_collector_safe import collect_posts_safe as collect_from_facebook
from filters.strict_filter import classify
from database.db import insert_post, mark_notified
# FIX #3: import ở top-level, không lồng trong vòng lặp
from telegram.notifier import send_post, send_heartbeat
from system.logger import logger

GROUP_CONFIG = json.loads(Path("config/groups.json").read_text(encoding="utf-8"))
INTERVAL = int(GROUP_CONFIG.get("poll_interval_seconds", 90))

_HEARTBEAT_EVERY = max(1, int(6 * 3600 / INTERVAL))
_cycle_count = 0


def run_once():
    posts = collect_from_facebook()
    logger.info("Collected %d post(s) from Facebook", len(posts))

    new_count = 0
    matched_count = 0

    for post in posts:
        # FIX #8: Dedup TRƯỚC classify — tránh gọi classify() cho bài đã có trong DB
        from database.db import post_exists  # noqa: PLC0415 (lazy import tránh circular)
        if post_exists(post["post_id"]):
            logger.debug("Duplicate skipped: %s", post["post_id"])
            continue

        result = classify(post["text"])
        is_new = insert_post(post, result)

        if not is_new:
            # Race condition: vừa được insert bởi thread/process khác
            logger.debug("Race-condition duplicate: %s", post["post_id"])
            continue

        new_count += 1

        if result["matched"]:
            matched_count += 1
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
            # FIX log: dùng debug thay vì info để tránh log file phình
            logger.debug(
                "❌ Filtered | post=%s | reason=%s",
                post["post_id"],
                result["reason"],
            )

    logger.info("Cycle done: %d new, %d matched/notified", new_count, matched_count)


def main():
    global _cycle_count

    logger.info("=" * 60)
    logger.info("Facebook Housing Monitor started")
    logger.info("Interval: %ss | Mode: CloakBrowser | Filter: STRICT", INTERVAL)
    logger.info("=" * 60)

    while True:
        _cycle_count += 1
        started = time.time()

        # Heartbeat mỗi 6 giờ — FIX #3: send_heartbeat đã import ở top-level
        if _cycle_count % _HEARTBEAT_EVERY == 0:
            try:
                send_heartbeat()
            except Exception:
                logger.warning("Heartbeat failed (cycle %d)", _cycle_count)

        try:
            run_once()
        except Exception:
            logger.exception("Cycle %d failed", _cycle_count)

        elapsed = time.time() - started
        sleep_time = max(1, INTERVAL - elapsed)
        logger.debug(
            "Cycle %d done in %.1fs, sleeping %.1fs",
            _cycle_count, elapsed, sleep_time,
        )
        time.sleep(sleep_time)


if __name__ == "__main__":
    main()
