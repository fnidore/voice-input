"""实时音量条 widget（清新简约浅色版）：圆角浅底 + 蓝色填充 + peak hold。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

try:
    from .style import PALETTE
except Exception:
    PALETTE = {"surface_3": "#eef0f3", "border": "#e8eaef",
               "accent": "#5b8def", "accent_press": "#3f72db"}


def _rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class VolumeMeter(QWidget):
    """横向电平表（peak 显示）。"""

    levelChanged = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(24)
        self.setMinimumWidth(180)
        self._level = 0.0
        self._peak_hold = 0.0
        self._hold_decay = 0.985

    def set_level(self, level: float) -> None:
        level = max(0.0, min(1.0, float(level)))
        self._level = level
        if level > self._peak_hold:
            self._peak_hold = level
        else:
            self._peak_hold *= self._hold_decay
        self.levelChanged.emit(level)
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        rad = rect.height() / 2

        # 圆角浅底
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(*_rgb(PALETTE["surface_3"])))
        p.drawRoundedRect(rect, rad, rad)

        # 蓝色填充（浅→深）
        if self._level > 0:
            accent = _rgb(PALETTE["accent"])
            light = tuple(min(255, c + 40) for c in accent)
            level_w = max(rect.height(), rect.width() * self._level)
            fill = QRectF(rect.left(), rect.top(), level_w, rect.height())
            grad = QLinearGradient(fill.topLeft(), fill.topRight())
            grad.setColorAt(0.0, QColor(*light))
            grad.setColorAt(1.0, QColor(*accent))
            p.setBrush(grad)
            p.drawRoundedRect(fill, rad, rad)

        # peak hold 竖线
        if self._peak_hold > 0.02:
            peak_x = rect.left() + rect.width() * self._peak_hold
            p.setPen(QPen(QColor(*_rgb(PALETTE["accent_press"])), 2))
            p.drawLine(int(peak_x), int(rect.top() + 3), int(peak_x), int(rect.bottom() - 3))

        # 描边
        p.setPen(QPen(QColor(*_rgb(PALETTE["border"])), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect, rad, rad)
        p.end()
