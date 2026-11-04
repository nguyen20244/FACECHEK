"""
normalizer.py - Chuẩn hóa text, GIỮ NGUYÊN tiếng Việt có dấu và tiếng Hàn.
"""
import re
import unicodedata

def normalize(text: str) -> str:
    if not text:
        return ""
    # NFC - quan trọng cho tiếng Việt và Hàn
    text = unicodedata.normalize("NFC", text)
    # Chỉ lowercase, KHÔNG xóa ký tự nào
    text = text.lower()
    # Chuẩn hóa khoảng trắng thừa
    text = re.sub(r"\s+", " ", text).strip()
    return text
