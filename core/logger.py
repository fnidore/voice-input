"""统一日志配置：滚动文件 + 控制台"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import LOG_DIR, ensure_dirs

_INITIALIZED = False
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO, console: bool = True) -> Path:
    """初始化全局日志，返回当前日志文件路径"""
    global _INITIALIZED
    ensure_dirs()
    log_path = LOG_DIR / "voice-input.log"

    if _INITIALIZED:
        return log_path

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # 滚动文件: 5MB x 5
    file_h = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_h.setFormatter(formatter)
    root.addHandler(file_h)

    if console:
        stream_h = logging.StreamHandler(sys.stdout)
        stream_h.setFormatter(formatter)
        root.addHandler(stream_h)

    # 把噪声调低
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("modelscope").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    _INITIALIZED = True
    logging.getLogger(__name__).info("logging initialized -> %s", log_path)
    return log_path
