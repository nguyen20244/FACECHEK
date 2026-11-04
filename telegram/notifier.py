"""
notifier.py
Gửi thông báo Telegram khi phát hiện bài nhượng phòng.
"""

import os
import requests
from dotenv import load_dotenv
from system.logger import logger

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

CONFIDENCE_EMOJI = {
    "high": "🔴",
    "medium": "🟡",
    "low": "⚪",
}


def send_post(post: dict, result: dict):
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("Telegram token or chat_id not configured in .env")
        return

    emoji = CONFIDENCE_EMOJI.get(result.get("confidence", "low"), "⚪")
    keywords = ", ".join(result.get("matched_transfer", []))
    text_preview = post.get("text", "")[:300]
    url = post.get("url", "")
    group = post.get("group", "")
    created_at = post.get("created_at", "")

    message = (
        f"{emoji} *[NHƯỢNG PHÒNG PHÁT HIỆN]*\n\n"
        f"📌 *Group:* {_esc(group)}\n"
        f"🕐 *Thời gian:* {_esc(created_at)}\n"
        f"🔑 *Từ khóa:* `{_esc(keywords)}`\n"
        f"📊 *Độ tin cậy:* {result.get('confidence', '').upper()}\n\n"
        f"📝 *Nội dung:*\n{_esc(text_preview)}{'...' if len(post.get('text','')) > 300 else ''}\n\n"
        f"🔗 [Xem bài đăng]({url})"
    )

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }

    resp = requests.post(API_URL, json=payload, timeout=10)
    resp.raise_for_status()
    logger.info("Telegram sent OK for post_id=%s", post.get("post_id"))


def send_heartbeat(message: str = "✅ Facebook Housing Monitor đang hoạt động bình thường."):
    """Gửi thông báo heartbeat định kỳ để biết bot còn sống."""
    if not BOT_TOKEN or not CHAT_ID:
        return
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        requests.post(API_URL, json=payload, timeout=10)
    except Exception:
        logger.warning("Heartbeat failed")


def _esc(text: str) -> str:
    """Escape ký tự đặc biệt Markdown cho Telegram."""
    for ch in ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]:
        text = text.replace(ch, f"\\{ch}")
    return text
