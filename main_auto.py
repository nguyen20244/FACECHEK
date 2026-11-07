"""
main_auto.py — Batch Mode

Luồng mỗi cycle:
  1. Batch 1 (Group 1-3) → classify → gửi Telegram ngay
  2. Nghỉ 60s (cấu hình batch_pause_seconds trong groups.json)
  3. Batch 2 (Group 4-6) → classify → gửi Telegram ngay
  4. Nghỉ hết INTERVAL rồi lặp lại

Timeline ví dụ (INTERVAL=600s):
  13:00 - Bắt đầu cycle
  13:00 - Quét Batch 1 (~3 phút)
  13:03 - Gửi Telegram Batch 1 ✅
  13:03 - Nghỉ 60s
  13:04 - Quét Batch 2 (~3 phút)
  13:07 - Gửi Telegram Batch 2 ✅
  13:10 - Nghỉ hết 600s → cycle tiếp theo
"""

import json
import time
from pathlib import Path

from browser.fb_collector import collect_by_batch
from browser.fb_collector_safe import _normalize_text
from filters.strict_filter import classify
from database.db import insert_post, mark_notified, post_exists
from telegram.notifier import send_post, send_heartbeat
from system.logger import logger

GROUP_CONFIG     = json.loads(Path("config/groups.json").read_text(encoding="utf-8"))
INTERVAL         = int(GROUP_CONFIG.get("poll_interval_seconds", 600))
_HEARTBEAT_EVERY = max(1, int(6 * 3600 / INTERVAL))

_cycle         = 0
_total_new     = 0
_total_matched = 0


def _process_posts(posts: list[dict]) -> tuple[int, int]:
    """Classify + insert + gửi Telegram cho một batch posts."""
    new_count     = 0
    matched_count = 0

    for post in posts:
        # Guard text None / rỗng
        text = post.get("text") or ""
        if not text.strip():
            continue

        # Normalize
        post["text"] = _normalize_text(text)

        # Dedup trước classify
        if post_exists(post["post_id"]):
            logger.debug("skip exists | %s | %s", post["post_id"], (post.get("text") or "")[:50])
            continue

        result = classify(post["text"])
        is_new = insert_post(post, result)
        if not is_new:
            continue

        new_count += 1

        # Log rõ bài dài bị filter để dễ chỉnh keyword
        text_len = len(post.get("text") or "")
        if not result["matched"] and text_len >= 40:
            logger.info(
                "⚠️ Missed long post | len=%d | score=%s | reason=%s | preview=%s",
                text_len, result["score"], result["reason"],
                (post.get("text") or "")[:80],
            )

        if result["matched"]:
            matched_count += 1
            try:
                send_post(post, result)
                mark_notified(post["post_id"])
                logger.info(
                    "✅ Notified | post=%s | conf=%s | score=%s | kw=%s",
                    post["post_id"], result["confidence"],
                    result["score"], result["matched_transfer"],
                )
            except Exception:
                logger.exception("Telegram failed for %s", post["post_id"])
        else:
            logger.debug(
                "❌ Filtered | post=%s | reason=%s | score=%s",
                post["post_id"], result["reason"], result["score"],
            )

    return new_count, matched_count


def run_once() -> tuple[int, int]:
    """
    Chạy 1 cycle đầy đủ:
      - Scrape Batch 1 → xử lý + gửi ngay
      - Nghỉ batch_pause
      - Scrape Batch 2 → xử lý + gửi ngay
    """
    total_new     = 0
    total_matched = 0

    batched = collect_by_batch()  # {1: [...], 2: [...]}

    if not batched:
        logger.warning("collect_by_batch() trả về rỗng (chưa đăng nhập?)")
        return 0, 0

    for batch_num in sorted(batched.keys()):
        posts = batched[batch_num]
        logger.info("[Batch %d] %d bài thu được — bắt đầu xử lý...", batch_num, len(posts))

        new, matched = _process_posts(posts)
        total_new     += new
        total_matched += matched

        logger.info(
            "[Batch %d] Xong: %d bài mới, %d match/gửi Telegram",
            batch_num, new, matched,
        )

    return total_new, total_matched


def main():
    global _cycle, _total_new, _total_matched

    logger.info("=" * 60)
    logger.info("Facebook Housing Monitor AUTO — BATCH MODE")
    logger.info("Interval: %ss | Batch pause: %ss | Filter: STRICT v3",
                INTERVAL, GROUP_CONFIG.get("batch_pause_seconds", 60))
    logger.info("=" * 60)

    while True:
        _cycle += 1
        logger.info("\n[Cycle %d] Bắt đầu...", _cycle)

        started = time.time()
        try:
            new, matched = run_once()
            _total_new     += new
            _total_matched += matched
        except Exception:
            logger.exception("Cycle %d failed", _cycle)
            new, matched = 0, 0

        elapsed = time.time() - started

        # Heartbeat sau run_once, kèm stats
        if _cycle % _HEARTBEAT_EVERY == 0:
            try:
                send_heartbeat(stats={
                    "cycle":         _cycle,
                    "total_new":     _total_new,
                    "total_matched": _total_matched,
                })
            except Exception:
                logger.warning("Heartbeat failed (cycle %d)", _cycle)

        sleep_time = max(1, INTERVAL - elapsed)
        logger.info(
            "[Cycle %d] Hoàn thành %.0fs | %d bài mới | %d match | Nghỉ %.0fs",
            _cycle, elapsed, new, matched, sleep_time,
        )
        time.sleep(sleep_time)


if __name__ == "__main__":
    main()
