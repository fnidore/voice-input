"""无系统托盘时的替代 UI：浮动状态小窗口
- 无边框 + 始终置顶
- 鼠标左键拖动到任意位置
- 双击打开设置
- 右键菜单（暂停/设置/重载模型/退出）
- 接口模仿 QSystemTrayIcon，方便 TrayApp 复用
"""

from __future__ import annotations

import logging
from enum import IntEnum

from PySide6.QtCore import QPoint, QSettings, Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QLabel, QMenu, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class ActivationReason(IntEnum):
    Unknown = 0
    Context = 1
    DoubleClick = 2
    Trigger = 3
    MiddleClick = 4


class FloatingStatusWindow(QWidget):
    """浮动状态窗口，行为类似系统托盘"""

    SIZE = 72  # 窗口边长（像素）

    activated = Signal(int)  # 兼容 QSystemTrayIcon.activated 信号

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(self.SIZE, self.SIZE)

        self.label = QLabel(self)
        self.label.setFixedSize(self.SIZE, self.SIZE)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setScaledContents(True)
        self.label.setStyleSheet("background: transparent;")

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.label)

        self._drag_origin: QPoint | None = None
        self._menu: QMenu | None = None

        # 恢复上次位置；如果上次位置不在屏幕内或没保存，落到屏幕右上角（顶栏下方）
        self._settings = QSettings("VoiceInput", "FloatingWindow")
        self._place_default_or_restore()

    def _place_default_or_restore(self) -> None:
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()

        # 默认: 屏幕右上角顶栏下方，模拟"托盘"位置
        default_pos = QPoint(
            geo.right() - self.SIZE - 16,
            geo.top() + 4,
        )

        saved = self._settings.value("pos")
        if saved is None:
            self.move(default_pos)
            return

        # 检查上次保存的位置是否还在屏幕可见区域内（防止换屏 / 改分辨率后丢失）
        try:
            px, py = int(saved.x()), int(saved.y())
        except Exception:
            self.move(default_pos)
            return

        if not (geo.left() <= px <= geo.right() - self.SIZE
                and geo.top() <= py <= geo.bottom() - self.SIZE):
            self.move(default_pos)
        else:
            self.move(px, py)

    def reset_position(self) -> None:
        """把窗口位置重置回默认（顶栏下方右上角）"""
        self._settings.remove("pos")
        self._place_default_or_restore()

    # ---------- 模仿 QSystemTrayIcon 的接口 ----------
    def setIcon(self, qicon: QIcon) -> None:
        pix = qicon.pixmap(self.SIZE, self.SIZE)
        self.label.setPixmap(pix)

    def setToolTip(self, text: str) -> None:
        super().setToolTip(text)
        self.label.setToolTip(text)

    def setContextMenu(self, menu: QMenu) -> None:
        self._menu = menu

    def showMessage(self, title: str, body: str, *_args, **_kwargs) -> None:
        """兼容 QSystemTrayIcon.showMessage，用 notify-send 实现"""
        import subprocess
        try:
            subprocess.Popen(
                ["notify-send", "-a", "Voice Input",
                 "-i", "audio-input-microphone", title, body],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    # ---------- 鼠标事件 ----------
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._drag_origin = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()
        elif e.button() == Qt.RightButton:
            if self._menu is not None:
                self._menu.exec(e.globalPosition().toPoint())
            e.accept()

    def mouseMoveEvent(self, e) -> None:
        if self._drag_origin is not None and (e.buttons() & Qt.LeftButton):
            new_pos = e.globalPosition().toPoint() - self._drag_origin
            self.move(new_pos)
            e.accept()

    def mouseReleaseEvent(self, e) -> None:
        if self._drag_origin is not None:
            self._settings.setValue("pos", self.pos())
        self._drag_origin = None
        e.accept()

    def mouseDoubleClickEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self.activated.emit(ActivationReason.DoubleClick)
            e.accept()

    def closeEvent(self, e) -> None:
        # 不真的关闭，只隐藏（用户应该走右键菜单退出）
        e.ignore()
        self.hide()
