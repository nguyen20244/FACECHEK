"""
setup_groups.py
Điền URL 4 Facebook group vào config/groups.json một cách dễ dàng.
Chạy: python setup_groups.py
"""

import json
from pathlib import Path

CONFIG_PATH = Path("config/groups.json")

def main():
    print("=" * 55)
    print("  CẤU HÌNH 4 FACEBOOK GROUP")
    print("=" * 55)
    print("Mở group trên Facebook → copy URL trên thanh địa chỉ")
    print("Ví dụ: https://www.facebook.com/groups/1234567890")
    print()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    groups = config["groups"]

    for i, g in enumerate(groups, 1):
        print(f"Group {i} — tên hiện tại: {g['name']}")
        name = input(f"  Tên group {i} (Enter để giữ nguyên): ").strip()
        url  = input(f"  URL group {i}: ").strip()

        if name:
            groups[i-1]["name"] = name
        if url:
            groups[i-1]["url"] = url
        groups[i-1]["enabled"] = True
        print()

    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print("✅ Đã lưu config/groups.json")
    print()
    print("Nội dung hiện tại:")
    for g in groups:
        status = "✅" if g["enabled"] else "❌"
        print(f"  {status} {g['name']}: {g['url']}")

if __name__ == "__main__":
    main()
