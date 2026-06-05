"""BarMeter 电平表：跨线程 set_level（音频回调线程）必须能驱动波形。

回归：sounddevice 回调线程直接调 set_level 时 QTimer.start() 跨线程失败，
波形条永远不动（设置窗口「测试 5 秒」无响应）。
"""

import os
import threading

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.volume_meter import BarMeter  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_set_level_from_gui_thread(app):
    meter = BarMeter()
    meter.set_level(0.6)
    for _ in range(5):
        app.processEvents()
    assert meter._level == 0.6
    assert meter._timer.isActive()


def test_set_level_from_worker_thread(app):
    """模拟 sounddevice 音频回调线程：跨线程调用也要能点亮波形。"""
    meter = BarMeter()
    t = threading.Thread(target=lambda: meter.set_level(0.8))
    t.start()
    t.join()
    for _ in range(10):
        app.processEvents()   # 排队信号送达 GUI 线程
    assert meter._level == 0.8
    assert meter._timer.isActive()


def test_level_clamped(app):
    meter = BarMeter()
    meter.set_level(2.5)
    for _ in range(5):
        app.processEvents()
    assert meter._level == 1.0
    meter.set_level(-1)
    for _ in range(5):
        app.processEvents()
    assert meter._level == 0.0
