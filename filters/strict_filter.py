"""
strict_filter.py
Chỉ cần khớp 1 từ khóa nhượng là gửi thông báo.
Ưu tiên không bỏ sót bài nhượng thật.
Loại mạnh bài chỉ tìm nhà / tìm phòng.
"""

import json
from pathlib import Path
from filters.normalizer import normalize

_kw = json.loads(Path("config/keywords.json").read_text(encoding="utf-8"))

# Lowercase toàn bộ keywords để so sánh nhất quán
TRANSFER_KW = [k.lower() for k in (
    _kw.get("transfer_keywords_ko", []) +
    _kw.get("transfer_keywords_vi", [])
)]

SEEK_KW = [k.lower() for k in (
    _kw.get("seek_keywords_ko", []) +
    _kw.get("seek_keywords_vi", [])
)]

# Từ khóa nhượng "mạnh" (rõ ràng là đang nhượng)
STRONG_TRANSFER = [
    "nhượng", "sang nhượng", "pass oneroom", "pass phòng", "pass nhà",
    "양도", "계약 승계", "계약승계", "넘겨", "방 빼", "퇴실",
    "tiếp quản", "sang lại", "chuyển nhượng"
]

# Từ khóa cọc (yếu hơn, dễ xuất hiện ở bài tìm cũng như bài nhượng)
DEPOSIT_KW = [
    "cọc 5tr", "cọc 4tr", "cọc 3tr", "cọc 2tr", "cọc 1tr",
    "cọc 300", "cọc 500", "cọc 600", "cọc 700", "cọc 800", "cọc 900"
]


def classify(text: str) -> dict:
    norm = normalize(text)  # đã lowercase trong normalizer

    matched_transfer = [kw for kw in TRANSFER_KW if kw in norm]
    matched_seek     = [kw for kw in SEEK_KW     if kw in norm]

    # Không có từ nhượng → loại ngay
    if not matched_transfer:
        return _result(
            matched=False,
            reason="no_transfer_keyword",
            transfer=matched_transfer,
            seek=matched_seek,
            confidence="low",
        )

    # Có từ nhượng mạnh → MATCH chắc chắn
    has_strong = any(s in norm for s in STRONG_TRANSFER)

    # Chỉ match vì từ cọc + không có từ nhượng mạnh
    only_deposit = (
        not has_strong
        and all(any(d in kw for d in DEPOSIT_KW) or kw.startswith("cọc ") for kw in matched_transfer)
        and len(matched_transfer) <= 2
    )

    # Nếu chỉ có cọc + có nhiều từ tìm nhà → coi là bài tìm, loại
    if only_deposit and len(matched_seek) >= 1:
        return _result(
            matched=False,
            reason="deposit_only_with_seek",
            transfer=matched_transfer,
            seek=matched_seek,
            confidence="low",
        )

    # Nếu chỉ có cọc yếu và không có dấu hiệu nhượng khác → hạ confidence nhưng vẫn gửi
    if only_deposit:
        confidence = "low"
    elif has_strong or len(matched_transfer) >= 2:
        confidence = "high"
    else:
        confidence = "medium"

    # Nếu seek nhiều hơn transfer rõ rệt → hạ confidence
    if len(matched_seek) > len(matched_transfer) * 2:
        confidence = "low"

    return _result(
        matched=True,
        reason="transfer_found",
        transfer=matched_transfer,
        seek=matched_seek,
        confidence=confidence,
    )


def _result(matched, reason, transfer, seek, confidence) -> dict:
    return {
        "matched":          matched,
        "reason":           reason,
        "matched_transfer": transfer,
        "matched_seek":     seek,
        "confidence":       confidence,
    }
