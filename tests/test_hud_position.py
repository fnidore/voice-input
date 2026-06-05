"""录音胶囊 HUD 拖动位置记忆（QSettings hud_pos）。

离屏运行：QT_QPA_PLATFORM=offscreen（conftest 外手动跑需自带该环境变量）。
"""

import os

import pytest

pytest.importorskip("PySide6")   # CI 轻量测试环境无 GUI 依赖时跳过
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.recording_hud import _POS_KEY, RecordingHUD  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path, app):
    """QSettings 重定向到临时目录，避免污染真实用户配置。"""
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    QSettings.setDefaultFormat(QSettings.IniFormat)
    s = QSettings("VoiceInput", "ui")
    s.remove(_POS_KEY)
    s.sync()
    yield s
    s.remove(_POS_KEY)
    s.sync()


def test_default_pos_is_bottom_center(settings, app):
    hud = RecordingHUD()
    pos = hud._target_pos()
    geo = app.primaryScreen().availableGeometry()
    assert pos.x() == geo.center().x() - hud.width() // 2
    assert pos.y() < geo.bottom()


def test_saved_pos_is_restored(settings, app):
    hud = RecordingHUD()
    geo = app.primaryScreen().availableGeometry()
    saved = QPoint(geo.x() + 30, geo.y() + 40)   # 屏幕内任意点
    settings.setValue(_POS_KEY, saved)
    settings.sync()
    assert hud._target_pos() == saved


def test_offscreen_saved_pos_falls_back(settings, app):
    """记忆坐标已不在任何屏幕上（换显示器）→ 回落默认底部居中。"""
    hud = RecordingHUD()
    settings.setValue(_POS_KEY, QPoint(-99999, -99999))
    settings.sync()
    assert hud._target_pos() == hud._default_pos()


def test_reset_position_clears_memory(settings, app):
    hud = RecordingHUD()
    settings.setValue(_POS_KEY, QPoint(100, 100))
    settings.sync()
    hud.reset_position()
    assert QSettings("VoiceInput", "ui").value(_POS_KEY) is None
    assert hud._target_pos() == hud._default_pos()


def test_drag_release_saves_pos(settings, app):
    """模拟 press → move → release，松手后位置写入 QSettings。"""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QMouseEvent

    hud = RecordingHUD()
    hud._state = "recording"   # 淡出/未显示时拖动被忽略，模拟可见状态
    hud.move(200, 200)

    def mouse_ev(etype, gpos):
        return QMouseEvent(etype, QPoint(10, 10), gpos,
                           Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)

    hud.mousePressEvent(mouse_ev(QEvent.MouseButtonPress, QPoint(210, 210)))
    hud.mouseMoveEvent(mouse_ev(QEvent.MouseMove, QPoint(310, 260)))
    assert hud.pos() == QPoint(300, 250)   # 整体平移 (+100, +50)
    hud.mouseReleaseEvent(mouse_ev(QEvent.MouseButtonRelease, QPoint(310, 260)))
    assert QSettings("VoiceInput", "ui").value(_POS_KEY) == QPoint(300, 250)
