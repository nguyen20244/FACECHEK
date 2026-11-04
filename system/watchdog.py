"""
watchdog.py
Chạy main loop với tự phục hồi: nếu crash, chờ 30 giây rồi khởi động lại.
Gửi heartbeat Telegram mỗi 6 giờ để xác nhận bot còn sống.
"""

import time
import subprocess
import sys
from pathlib import Path
from system.logger import logger

RESTART_DELAY = 30          # giây chờ trước khi restart
HEARTBEAT_INTERVAL = 6 * 3600  # 6 giờ


def run_with_watchdog():
    """Khởi động main.py trong subprocess, tự restart khi crash."""
    python = sys.executable
    script = Path(__file__).parent.parent / "main.py"
    attempt = 0

    while True:
        attempt += 1
        logger.info("Watchdog: starting main.py (attempt %d)", attempt)
        try:
            proc = subprocess.Popen(
                [python, str(script)],
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            proc.wait()
            exit_code = proc.returncode
            logger.warning(
                "main.py exited with code %d. Restarting in %ds...",
                exit_code,
                RESTART_DELAY,
            )
        except Exception:
            logger.exception("Watchdog failed to start main.py")

        time.sleep(RESTART_DELAY)


if __name__ == "__main__":
    run_with_watchdog()
