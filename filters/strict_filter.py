"""
strict_filter.py — Nâng cấp v2

Thay đổi so với v1:
  - Bổ sung từ khóa nhượng tiếng Hàn / Việt thực tế từ các group
  - STRONG_TRANSFER mở rộng, bắt được nhiều pattern hơn
  - Logic confidence rõ ràng hơn: điểm số thay vì if/else phức tạp
  - PRICE_PATTERN: có giá cụ thể → tăng điểm
  - ROOM_PATTERN: có loại phòng → tăng điểm
  - Seek mạnh → trừ điểm (thay vì chỉ so sánh len)
"""

import re
import json
from pathlib import Path
from filters.normalizer import normalize

_kw = json.loads(Path("config/keywords.json").read_text(encoding="utf-8"))

# ── Từ khóa từ config ───────────────────────────────────────────────────────
TRANSFER_KW = [k.lower() for k in (
    _kw.get("transfer_keywords_ko", []) +
    _kw.get("transfer_keywords_vi", [])
)]
SEEK_KW = [k.lower() for k in (
    _kw.get("seek_keywords_ko", []) +
    _kw.get("seek_keywords_vi", [])
)]

# ── Từ khóa nhượng MẠNH (+2 điểm mỗi cái) ─────────────────────────────────
STRONG_TRANSFER = [
    # Tiếng Việt
    "nhượng", "sang nhượng", "chuyển nhượng", "tiếp quản", "sang lại",
    "pass nhà", "pass phòng", "pass oneroom", "pass 1룸", "pass room",
    "cần pass", "muốn pass", "nhượng lại", "nhượng nhà", "nhượng phòng",
    "sang tên", "bàn giao", "nhận nhà luôn", "dọn vào liền",
    "chuyển đi nên", "về nước nên", "về vn nên", "hết visa nên",
    # Tiếng Hàn
    "양도", "계약 승계", "계약승계", "넘겨", "방 빼", "퇴실",
    "방양도", "계약 넘기", "입주 가능", "즉시 입주",
    "보증금 승계", "전세 양도", "월세 양도",
]

# ── Từ khóa nhượng YẾU (+1 điểm mỗi cái) ──────────────────────────────────
WEAK_TRANSFER = [
    "cọc", "tiền cọc", "보증금", "deposit",
    "còn hợp đồng", "hợp đồng còn", "hết hợp đồng",
    "tháng sau chuyển", "cuối tháng chuyển", "chuyển nhà",
    "dọn đi", "không ở nữa", "không tiếp tục ở",
    "계약 남은", "계약기간 남", "잔여 계약",
]

# ── Từ khóa tìm phòng MẠNH (-2 điểm mỗi cái) ──────────────────────────────
SEEK_STRONG = [
    "tìm phòng", "tìm nhà", "tìm người ở ghép", "tìm chỗ ở",
    "cần thuê", "muốn thuê", "thuê phòng", "thuê nhà",
    "방 구해요", "방 찾아요", "구합니다", "구하고 있어요",
    "방 있나요", "방 있어요", "방 구함",
    "ai có phòng không", "ai có nhà không",
    "có phòng cho thuê không", "giới thiệu phòng cho mình",
]

# ── Pattern giá cụ thể (+1 điểm nếu có) ───────────────────────────────────
PRICE_PATTERN = re.compile(
    r'(\d{1,4})\s*(tr|triệu|만원|만|천원|천|월|보증|cọc)',
    re.IGNORECASE
)

# ── Pattern loại phòng (+1 điểm nếu có) ───────────────────────────────────
ROOM_PATTERN = re.compile(
    r'(1룸|2룸|3룸|oneroom|one\s*room|투룸|쓰리룸|고시원|옥탑방|반지하|복층|studio)',
    re.IGNORECASE
)


def _score(norm: str):
    strong  = [kw for kw in STRONG_TRANSFER if kw in norm]
    weak    = [kw for kw in WEAK_TRANSFER   if kw in norm]
    seek    = [kw for kw in SEEK_STRONG     if kw in norm]
    from_cfg = [kw for kw in TRANSFER_KW   if kw in norm]

    pts = 0
    pts += len(strong) * 2
    pts += len(weak)   * 1
    pts += len(from_cfg) * 1

    if PRICE_PATTERN.search(norm):
        pts += 1
    if ROOM_PATTERN.search(norm):
        pts += 1

    pts -= len(seek) * 2

    return pts, strong, weak, seek, from_cfg


def classify(text: str) -> dict:
    norm = normalize(text)
    pts, strong, weak, seek, from_cfg = _score(norm)

    all_transfer = list(dict.fromkeys(strong + weak + from_cfg))

    if pts <= 0:
        reason = "no_transfer_keyword" if not all_transfer else "seek_dominates"
        return _result(False, reason, all_transfer, seek, "low", pts)

    if pts >= 4:
        confidence = "high"
    elif pts >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    return _result(True, "transfer_found", all_transfer, seek, confidence, pts)


def _result(matched, reason, transfer, seek, confidence, score=0) -> dict:
    return {
        "matched":          matched,
        "reason":           reason,
        "matched_transfer": transfer,
        "matched_seek":     seek,
        "confidence":       confidence,
        "score":            score,
    }
