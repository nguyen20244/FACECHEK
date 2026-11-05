"""
browser/fb_collector_safe.py

Wrapper an toàn quanh fb_collector:
  FIX #5: Giới hạn số posts mỗi cycle (MAX_POSTS_PER_CYCLE)
  FIX #6: Guard khi post["text"] là None / rỗng
  FIX #7: Normalize text trước khi trả về (unescape HTML entities, NFC)

Import module này thay vì fb_collector trực tiếp.
"""

import html
import unicodedata
from typing import List, Dict, Any

from browser.fb_collector import collect_from_facebook as _collect_raw
from system.logger import logger

# Cap số bài xử lý mỗi cycle — tránh cycle kéo quá dài làm mất kiểm soát tốc độ
MAX_POSTS_PER_CYCLE = 50


def _normalize_text(text: str) -> str:
    """
    Chuẩn hóa text trước khi lọc:
    - Unescape HTML entities (&amp; → &, &#39; → ', v.v.)
    - NFC normalization (tiếng Hàn / Unicode đặc biệt)
    - Strip whitespace thừa
    """
    text = html.unescape(text)
    text = unicodedata.normalize("NFC", text)
    return text.strip()


def collect_posts_safe() -> List[Dict[str, Any]]:
    """
    Thu thập bài từ Facebook, lọc sạch, và giới hạn số lượng.

    Returns:
        Danh sách posts đã được validate và normalize.
    """
    raw_posts = _collect_raw()

    safe_posts = []
    skipped = 0

    for post in raw_posts:
        # FIX #6: Guard text None / rỗng
        text = post.get("text")
        if not text or not isinstance(text, str) or not text.strip():
            skipped += 1
            logger.debug("Skipped post with empty/null text: %s", post.get("post_id"))
            continue

        # FIX #7: Normalize text
        post["text"] = _normalize_text(text)
        safe_posts.append(post)

    if skipped:
        logger.info("Skipped %d post(s) with empty text", skipped)

    # FIX #5: Cap số bài mỗi cycle
    total = len(safe_posts)
    if total > MAX_POSTS_PER_CYCLE:
        logger.warning(
            "Collected %d posts, capping to %d per cycle to maintain schedule",
            total, MAX_POSTS_PER_CYCLE,
        )
        safe_posts = safe_posts[:MAX_POSTS_PER_CYCLE]

    return safe_posts
