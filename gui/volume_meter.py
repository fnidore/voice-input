"""实时音量条 widget：绿/黄/红三段，跟着峰值跳动"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget


class VolumeMeter(QWidget):
    """横向 VU 表（peak 显示）"""

    levelChanged = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(18)
        self.setMinimumWidth(180)
        self._level = 0.0       # 当前峰值 0~1
        self._peak_hold = 0.0   # peak hold 标记
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

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 2, -1, -2)
        # 背景
        p.fillRect(rect, QColor(40, 42, 48))
        # 渐变填充
        if self._level > 0:
            grad = QLinearGradient(rect.topLeft(), rect.topRight())
            grad.setColorAt(0.0, QColor(80, 200, 80))   # 绿
            grad.setColorAt(0.6, QColor(220, 200, 60))  # 黄
            grad.setColorAt(0.9, QColor(220, 80, 60))   # 红
            level_w = int(rect.width() * self._level)
            level_rect = rect.adjusted(0, 0, -(rect.width() - level_w), 0)
            p.fillRect(level_rect, grad)
        # peak hold 竖线
        if self._peak_hold > 0:
            peak_x = rect.left() + int(rect.width() * self._peak_hold)
            p.setPen(QPen(QColor(255, 255, 255, 200), 2))
            p.drawLine(peak_x, rect.top(), peak_x, rect.bottom())
        # 边框
        p.setPen(QPen(QColor(70, 75, 85), 1))
        p.drawRect(rect)
        p.end()
