"""
strict_filter.py
Chỉ cần khớp 1 từ khóa nhượng là gửi thông báo.
Từ khóa được so sánh không phân biệt hoa/thường.
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


def classify(text: str) -> dict:
    norm = normalize(text)  # đã lowercase trong normalizer

    matched_transfer = [kw for kw in TRANSFER_KW if kw in norm]
    matched_seek     = [kw for kw in SEEK_KW     if kw in norm]

    # Không có từ nhượng → loại
    if not matched_transfer:
        return _result(
            matched=False,
            reason="no_transfer_keyword",
            transfer=matched_transfer,
            seek=matched_seek,
            confidence="low",
        )

    # Có từ nhượng → MATCH ngay, dù có hay không có từ tìm
    # (ưu tiên độ phủ, tránh bỏ sót)
    confidence = "high" if len(matched_transfer) >= 2 else "medium"

    # Nếu seek nhiều hơn transfer rõ rệt → hạ xuống low nhưng vẫn gửi
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
