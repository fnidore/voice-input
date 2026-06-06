"""Voice Input GUI 入口
- PySide6 托盘 + 设置窗口
- 单例运行（避免重复启动）
- 异常上抓到日志
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

# 让 from core/from gui 这种绝对导入能找到包
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import Config, ensure_dirs       # noqa: E402
from core.gpu_runtime import activate as activate_gpu_runtime  # noqa: E402
from core.logger import setup_logging              # noqa: E402
from core.singleton import acquire_single_instance_lock  # noqa: E402

logger = logging.getLogger(__name__)


def _wait_for_tray(app: QApplication, max_wait_seconds: int = 30) -> bool:
    """等待系统托盘就绪。
    通过 systemd 启动时，voice-input 可能比 GNOME Shell + AppIndicator 早就绪，
    那时候 D-Bus 上 StatusNotifierWatcher 还没注册，isSystemTrayAvailable() 返回 False。
    主动等到它就绪。
    """
    import time as _time

    if QSystemTrayIcon.isSystemTrayAvailable():
        return True

    logger.info("waiting up to %ds for system tray to become available...",
                max_wait_seconds)
    deadline = _time.time() + max_wait_seconds
    checks = 0
    while _time.time() < deadline:
        # 边等边跑 Qt 事件循环，否则有些资源初始化不了
        app.processEvents()
        _time.sleep(0.5)
        checks += 1
        if QSystemTrayIcon.isSystemTrayAvailable():
            logger.info("tray became available after %.1fs", checks * 0.5)
            return True
    return False


def _install_signal_handlers(app: QApplication) -> None:
    def _quit(sig, _frame):
        logger.info("signal %s received, quitting", sig)
        app.quit()

    signal.signal(signal.SIGINT, _quit)
    signal.signal(signal.SIGTERM, _quit)


def main() -> int:
    ensure_dirs()
    setup_logging()

    # GPU 运行时插队加载——必须在任何 torch import 之前
    activate_gpu_runtime()

    logger.info("=" * 60)
    logger.info("Voice Input GUI starting (pid=%d)", os.getpid())

    lock = acquire_single_instance_lock()
    if lock is None:
        QApplication(sys.argv)
        QMessageBox.warning(None, "已在运行", "Voice Input 已经在运行了。\n请到系统托盘查看。")
        return 1

    # 让 QApplication 不要在最后一个窗口关闭后退出（我们用托盘/浮窗常驻）
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Voice Input")

    # 等待系统托盘就绪（systemd 启动时 GNOME Shell + AppIndicator 通常需要 10~20s）
    tray_available = _wait_for_tray(app, max_wait_seconds=30)
    if not tray_available:
        logger.warning(
            "system tray not available after waiting → fallback to floating window"
        )
    else:
        logger.info("system tray is available, using it")

    _install_signal_handlers(app)

    # 加载配置
    try:
        cfg = Config.load()
    except Exception:
        logger.exception("config load failed, using defaults")
        cfg = Config()

    # 启动托盘 / 浮动窗口应用
    from gui.tray_app import TrayApp  # 延迟 import 减少冷启动
    tray = TrayApp(app, cfg, use_floating=not tray_available)
    tray.start()

    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logging.getLogger(__name__).exception("fatal error in main")
        raise
