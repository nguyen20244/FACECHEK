# FACECHEK Fix v3.1 — ổn định browser + filter nhượng nhà

## Sửa lỗi TargetClosedError

Nguyên nhân: mỗi group mở 1 `new_page()` rồi `close()`, context đôi khi bị đóng
giữa Group 1 → Group 2 (Facebook / cloakbrowser / tab crash).

**Cách xử lý trong `fb_collector.py`:**
- Dùng **1 page chung** cho cả batch (navigate lại giữa các group)
- Kiểm tra context/page còn sống trước mỗi group
- Tự tạo lại page nếu page chết; dừng batch sạch nếu context chết (không crash cycle)

## File cần copy đè

| File đích | File trong zip |
|-----------|----------------|
| `browser/fb_collector.py` | `fb_collector.py` |
| `filters/strict_filter.py` | `strict_filter.py` |
| `config/groups.json` | `groups.json` |
| `config/keywords.json` | `keywords.json` |
| `main_auto.py` | `main_auto.py` |

## Sau khi copy

1. Tắt bot đang chạy (Ctrl+C).
2. Copy đè 5 file trên.
3. Chạy lại: `python main_auto.py`
4. Log phải hiện: `Filter: STRICT v3`
5. Group 1 xong → nghỉ vài giây → Group 2/3 không còn TargetClosedError.

Nếu vẫn bị đóng context:
- Chạy lại `python browser/cloak_session.py` để login lại
- Tắt headless = False, xem cửa sổ browser có popup checkpoint không
- Giảm SCROLL_TIMES (8 → 5) trong fb_collector nếu máy yếu

## Filter v3 (giữ nguyên)

Bài ≥40 ký tự có tín hiệu nhượng/cọc/ga/룸 → ưu tiên match.
