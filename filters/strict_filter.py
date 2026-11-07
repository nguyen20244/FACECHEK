"""
strict_filter.py — v3 (ưu tiên bắt bài nhượng nhà)

Thay đổi so với v2:
  - Mở rộng mạnh STRONG_TRANSFER / WEAK_TRANSFER theo pattern thực tế từ group
  - Bài > 40 ký tự được ưu tiên: chỉ cần 1 tín hiệu nhượng + (giá hoặc loại phòng) là match
  - Giảm false-negative: không loại sớm bài dài có "cọc", "ga", "룸", "nhượng", "pass"...
  - Seek chỉ trừ điểm mạnh khi bài ngắn hoặc seek chiếm ưu thế rõ
  - Confidence rõ ràng hơn
"""

import re
import json
from pathlib import Path
from filters.normalizer import normalize

_kw = json.loads(Path("config/keywords.json").read_text(encoding="utf-8"))

TRANSFER_KW = [k.lower() for k in (
    _kw.get("transfer_keywords_ko", []) +
    _kw.get("transfer_keywords_vi", [])
)]
SEEK_KW = [k.lower() for k in (
    _kw.get("seek_keywords_ko", []) +
    _kw.get("seek_keywords_vi", [])
)]

# ── Từ khóa nhượng MẠNH (+3 điểm) ──────────────────────────────────────────
STRONG_TRANSFER = [
    # Việt
    "nhượng", "nhượng nhà", "nhượng phòng", "nhượng lại", "nhượng oneroom",
    "sang nhượng", "chuyển nhượng", "sang lại", "sang lại phòng",
    "pass nhà", "pass phòng", "pass oneroom", "pass room", "pass 1룸",
    "cần pass", "muốn pass", "e nhượng", "em nhượng", "mình nhượng",
    "cần nhượng", "muốn nhượng", "mình muốn nhượng",
    "trả phòng", "dọn ra", "hết hợp đồng sớm",
    "không ở được nữa", "cần người thay", "ai thay tôi",
    "chuyển đi nên", "về nước nên", "về vn nên", "hết visa nên",
    "bàn giao", "nhận nhà luôn", "dọn vào liền", "sang tên",
    # Hàn
    "양도", "양도해요", "양도 가능", "계약 승계", "계약승계",
    "방 빼", "퇴실", "방양도", "계약 넘기", "입주 가능", "즉시 입주",
    "보증금 승계", "전세 양도", "월세 양도",
]

# ── Từ khóa nhượng YẾU / tín hiệu phụ (+1 điểm) ───────────────────────────
WEAK_TRANSFER = [
    "cọc", "tiền cọc", "보증금", "deposit", "tiền nhà",
    "còn hợp đồng", "hợp đồng còn", "hết hợp đồng",
    "tháng sau chuyển", "cuối tháng chuyển", "chuyển nhà",
    "dọn đi", "không ở nữa", "không tiếp tục ở",
    "계약 남은", "계약기간 남", "잔여 계약",
    "đi bộ", "cạnh ga", "gần ga", "cách ga", "ở ga",
    "gần trường", "cách trường", "ngay gần",
    "điện ga riêng", "điện nước", "ga riêng",
    "mình có nhà", "có nhà", "còn phòng",
    "oneroom", "one room", "1룸", "2룸", "3룸", "투룸", "쓰리룸",
    "고시원", "gosiwon", "옥탑방", "반지하", "복층",
]

# ── Từ khóa tìm phòng MẠNH (trừ điểm) ─────────────────────────────────────
SEEK_STRONG = [
    "tìm phòng", "tìm nhà", "tìm người ở ghép", "tìm chỗ ở",
    "cần thuê", "muốn thuê", "thuê phòng", "thuê nhà",
    "방 구해요", "방 찾아요", "구합니다", "구하고 있어요",
    "방 있나요", "방 있어요", "방 구함",
    "ai có phòng không", "ai có nhà không",
    "có phòng cho thuê không", "giới thiệu phòng cho mình",
    "đang tìm phòng", "cần tìm phòng", "cần tìm nhà", "đang tìm nhà",
]

PRICE_PATTERN = re.compile(
    r'(\d{1,4})\s*(tr|triệu|만원|만|천원|천|월|보증|cọc|k\b|/tháng|tháng)',
    re.IGNORECASE
)

ROOM_PATTERN = re.compile(
    r'(1룸|2룸|3룸|oneroom|one\s*room|투룸|쓰리룸|고시원|gosiwon|옥탑방|반지하|복층|studio|'
    r'cạnh\s*ga|gần\s*ga|cách\s*ga|đi\s*bộ|line\s*\d|nhà\s*line)',
    re.IGNORECASE
)

TRANSFER_PHRASE = re.compile(
    r'(em|mình|mk|e|tôi|toei|mik)\s*(nhượng|pass|sang)|'
    r'(cần|muốn)\s*(nhượng|pass|sang)|'
    r'nhượng\s*(nhà|phòng|lại|oneroom|1룸|2룸)|'
    r'pass\s*(nhà|phòng|oneroom|room|1룸)',
    re.IGNORECASE
)


def _score(norm: str, raw_len: int):
    strong = [kw for kw in STRONG_TRANSFER if kw in norm]
    weak = [kw for kw in WEAK_TRANSFER if kw in norm]
    seek = [kw for kw in SEEK_STRONG if kw in norm]
    from_cfg = [kw for kw in TRANSFER_KW if kw in norm]

    pts = 0
    pts += len(strong) * 3
    pts += len(weak) * 1
    pts += len(from_cfg) * 1

    has_price = bool(PRICE_PATTERN.search(norm))
    has_room = bool(ROOM_PATTERN.search(norm))
    has_phrase = bool(TRANSFER_PHRASE.search(norm))

    if has_price:
        pts += 2
    if has_room:
        pts += 1
    if has_phrase:
        pts += 2

    # Bài dài (>=40 ký tự): ưu tiên giữ nếu có tín hiệu nhượng
    if raw_len >= 40:
        if strong or has_phrase or (weak and (has_price or has_room)):
            pts = max(pts, 3)
        if len(seek) > 0 and not (strong or has_phrase):
            pts -= len(seek) * 2
        elif len(seek) > len(strong) + 1:
            pts -= 1
    else:
        pts -= len(seek) * 2

    return pts, strong, weak, seek, from_cfg, has_price, has_room, has_phrase


def classify(text: str) -> dict:
    if not text or not text.strip():
        return _result(False, "empty", [], [], "low", 0)

    raw_len = len(text.strip())
    norm = normalize(text)
    pts, strong, weak, seek, from_cfg, has_price, has_room, has_phrase = _score(norm, raw_len)

    all_transfer = list(dict.fromkeys(strong + weak + from_cfg))
    if has_phrase and "transfer_phrase" not in all_transfer:
        all_transfer.append("transfer_phrase")

    if raw_len >= 40:
        matched = pts >= 2 or (pts >= 1 and (has_price or has_room or strong or has_phrase))
    else:
        matched = pts >= 3

    if not matched:
        if not all_transfer and not has_phrase:
            reason = "no_transfer_keyword"
        elif seek and pts <= 0:
            reason = "seek_dominates"
        else:
            reason = "score_too_low"
        return _result(False, reason, all_transfer, seek, "low", pts)

    if pts >= 6:
        confidence = "high"
    elif pts >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    return _result(True, "transfer_found", all_transfer, seek, confidence, pts)


def _result(matched, reason, transfer, seek, confidence, score=0) -> dict:
    return {
        "matched": matched,
        "reason": reason,
        "matched_transfer": transfer,
        "matched_seek": seek,
        "confidence": confidence,
        "score": score,
    }
