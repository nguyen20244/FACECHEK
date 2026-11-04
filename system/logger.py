"""
logger.py
Cấu hình logging: ghi ra console và file logs/monitor.log.
"""

import logging
import sys
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("housing_monitor")
logger.setLevel(logging.DEBUG)

# Format chung
_fmt = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Console handler
_ch = logging.StreamHandler(sys.stdout)
_ch.setLevel(logging.INFO)
_ch.setFormatter(_fmt)

# File handler (giữ log 7 ngày, mỗi file tối đa 5MB)
from logging.handlers import RotatingFileHandler
_fh = RotatingFileHandler(
    LOG_DIR / "monitor.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=7,
    encoding="utf-8",
)
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(_fmt)

if not logger.handlers:
    logger.addHandler(_ch)
    logger.addHandler(_fh)
