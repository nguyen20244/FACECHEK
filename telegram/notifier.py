"""
notifier.py — Nâng cấp v2

Thay đổi so với v1:
  - Dùng MarkdownV2 thay Markdown cũ → không bị lỗi escape ký tự
  - Chỉ gửi confidence HIGH và MEDIUM — LOW không gửi (tránh spam)
  - Format tin nhắn rõ ràng hơn: điểm số, loại phòng, địa chỉ nếu detect được
  - Retry tự động 3 lần nếu Telegram timeout
  - send_heartbeat có thống kê cycle
"""

import os
import re
import time
import requests
from dotenv import load_dotenv
from system.logger import logger

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
API_URL   = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# Chỉ gửi từ mức này trở lên — đổi thành "low" nếu muốn nhận tất cả
MIN_CONFIDENCE = "medium"
_CONF_RANK = {"low": 0, "medium": 1, "high": 2}

CONFIDENCE_EMOJI = {
    "high":   "🔴",
    "medium": "🟡",
    "low":    "⚪",
}

MAX_RETRIES = 3
RETRY_DELAY = 3  # giây


def _should_send(confidence: str) -> bool:
    return _CONF_RANK.get(confidence, 0) >= _CONF_RANK.get(MIN_CONFIDENCE, 1)


def _esc(text: str) -> str:
    """Escape đúng chuẩn MarkdownV2 của Telegram."""
    # Các ký tự cần escape trong MarkdownV2
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, f'\\{ch}')
    return text


def _detect_location(text: str) -> str:
    """Thử tách địa chỉ / ga tàu từ text để hiển thị nhanh."""
    # Tìm ga tàu điện ngầm Seoul (숫자호선 or 역)
    ga = re.findall(r'[가-힣]+역', text)
    if ga:
        return "🚇 " + ", ".join(dict.fromkeys(ga[:3]))

    # Tìm địa danh tiếng Việt phổ biến
    patterns = [
        r'ga\s+[A-Za-z가-힣\s]+',
        r'gần\s+[A-Za-zÀ-ỹ가-힣\s]+',
        r'khu\s+[A-Za-zÀ-ỹ\s]+',
        r'quận\s+[A-Za-zÀ-ỹ\s]+',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return "📍 " + m.group(0).strip()[:40]

    return ""


def _format_message(post: dict, result: dict) -> str:
    emoji      = CONFIDENCE_EMOJI.get(result.get("confidence", "low"), "⚪")
    conf       = result.get("confidence", "low").upper()
    score      = result.get("score", 0)
    keywords   = result.get("matched_transfer", [])
    text_full  = post.get("text", "")
    preview    = text_full[:350]
    more       = "\\.\\.\\." if len(text_full) > 350 else ""
    url        = post.get("url", "")
    group      = post.get("group", "")
    location   = _detect_location(text_full)

    kw_display = " \\| ".join([f"`{_esc(k)}`" for k in keywords[:5]])
    if not kw_display:
        kw_display = "\\(không rõ\\)"

    lines = [
        f"{emoji} *NHƯỢNG NHÀ / PHÒNG*",
        f"",
        f"📌 *Group:* {_esc(group)}",
    ]
    if location:
        lines.append(f"{location}")
    lines += [
        f"🔑 *Từ khóa:* {kw_display}",
        f"📊 *Độ tin cậy:* {_esc(conf)} \\(điểm: {score}\\)",
        f"",
        f"📝 *Nội dung:*",
        f"{_esc(preview)}{more}",
        f"",
        f"[🔗 Xem bài đăng]({url})",
    ]
    return "\n".join(lines)


def _send_raw(text: str):
    """Gửi tin nhắn với retry."""
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("Telegram token / chat_id chưa cấu hình trong .env")
        return

    payload = {
        "chat_id":                  CHAT_ID,
        "text":                     text,
        "parse_mode":               "MarkdownV2",
        "disable_web_page_preview": False,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(API_URL, json=payload, timeout=10)
            resp.raise_for_status()
            return
        except requests.exceptions.Timeout:
            logger.warning("Telegram timeout (lần %d/%d)", attempt, MAX_RETRIES)
        except requests.exceptions.HTTPError as e:
            logger.error("Telegram HTTP error: %s | body: %s", e, resp.text[:200])
            return  # HTTP error không retry
        except Exception as e:
            logger.warning("Telegram error lần %d: %s", attempt, e)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    logger.error("Telegram: gửi thất bại sau %d lần thử", MAX_RETRIES)


def send_post(post: dict, result: dict):
    """Gửi thông báo bài nhượng nhà. Bỏ qua nếu confidence quá thấp."""
    confidence = result.get("confidence", "low")

    if not _should_send(confidence):
        logger.info(
            "Bỏ qua gửi Telegram (confidence=%s < MIN=%s) | post=%s",
            confidence, MIN_CONFIDENCE, post.get("post_id"),
        )
        return

    msg = _format_message(post, result)
    _send_raw(msg)
    logger.info(
        "Telegram sent | post=%s | confidence=%s | score=%s | keywords=%s",
        post.get("post_id"),
        confidence,
        result.get("score"),
        result.get("matched_transfer"),
    )


def send_heartbeat(stats: dict | None = None):
    """
    Gửi heartbeat định kỳ. stats = {"cycle": N, "total_new": N, "total_matched": N}
    """
    if not BOT_TOKEN or not CHAT_ID:
        return

    if stats:
        msg = (
            f"✅ *Housing Monitor hoạt động bình thường*\n\n"
            f"🔄 Cycle: {stats.get('cycle', '?')}\n"
            f"📥 Bài mới: {stats.get('total_new', 0)}\n"
            f"🎯 Đã match: {stats.get('total_matched', 0)}\n"
            f"📡 Min confidence: `{MIN_CONFIDENCE.upper()}`"
        )
    else:
        msg = "✅ *Housing Monitor hoạt động bình thường*"

    payload = {
        "chat_id":    CHAT_ID,
        "text":       msg,
        "parse_mode": "MarkdownV2",
    }
    try:
        requests.post(API_URL, json=payload, timeout=10)
    except Exception as e:
        logger.warning("Heartbeat failed: %s", e)
