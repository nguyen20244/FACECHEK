"""
cloak_session.py - Khởi động CloakBrowser, đăng nhập Facebook thủ công.
Chạy 1 lần để lưu session: python browser/cloak_session.py
"""

import time
from pathlib import Path
import cloakbrowser

PROFILE_DIR = Path("data/cloak_profile").resolve()
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

GROUP_URLS = []  # Không cần test group ở đây, chỉ cần login

def open_session():
    print(f"[INFO] Profile: {PROFILE_DIR}")
    print("[INFO] Đang khởi động CloakBrowser...")

    context = cloakbrowser.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        args=["--disable-notifications"],
    )

    page = context.new_page()
    page.goto("https://www.facebook.com/", timeout=30000)
    time.sleep(3)

    if "login" in page.url or "checkpoint" in page.url:
        print("[ACTION] Chưa đăng nhập. Hãy đăng nhập Facebook trong cửa sổ trình duyệt.")
        print("[ACTION] Sau khi đăng nhập xong, nhấn Enter tại đây.")
        input()
    else:
        print("[OK] Đã đăng nhập Facebook.")

    print(f"[OK] Session lưu tại: {PROFILE_DIR}")
    input("Nhấn Enter để đóng trình duyệt...")
    context.close()

if __name__ == "__main__":
    open_session()
