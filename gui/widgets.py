"""清新简约风格的自定义控件。

- ToggleSwitch: iOS 风格滑动开关，带动画，替代设置里的 QCheckBox 开关项。
- HSep: 卡片内的发丝线分隔。

依赖 .style.PALETTE 取色，与窗口主题保持一致。
"""

from __future__ import annotations

from PySide6.QtCore import (
    Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QFrame

from .style import PALETTE


def _mix(c1: QColor, c2: QColor, t: float) -> QColor:
    """在 c1→c2 之间线性插值（t: 0~1）。"""
    return QColor(
        round(c1.red()   + (c2.red()   - c1.red())   * t),
        round(c1.green() + (c2.green() - c1.green()) * t),
        round(c1.blue()  + (c2.blue()  - c1.blue())  * t),
    )


class ToggleSwitch(QAbstractButton):
    """可勾选的滑动开关。用法同 QCheckBox：

        sw = ToggleSwitch()
        sw.setChecked(True)
        sw.toggled.connect(...)
        sw.isChecked()
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._w, self._h, self._pad = 46, 26, 3
        self.setFixedSize(self._w, self._h)
        self._pos = 0.0  # 旋钮位置 0(关)~1(开)
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate_to)

    # --- 动画属性 ---
    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, v: float) -> None:
        self._pos = v
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def _animate_to(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def setChecked(self, on: bool) -> None:  # noqa: N802
        super().setChecked(on)
        # 初始化时直接落位，避免开窗即播放动画
        if not self.isVisible():
            self._pos = 1.0 if on else 0.0

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._w, self._h)

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        track = QRectF(0, 0, self._w, self._h)
        off = QColor(PALETTE["surface_3"])
        on = QColor(PALETTE["accent"])
        p.setPen(Qt.NoPen)
        p.setBrush(_mix(off, on, self._pos))
        p.drawRoundedRect(track, self._h / 2, self._h / 2)

        d = self._h - self._pad * 2
        x = self._pad + self._pos * (self._w - d - self._pad * 2)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, self._pad, d, d))
        p.end()


class HSep(QFrame):
    """卡片内发丝线分隔。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background: {PALETTE['border']}; border: none;")
