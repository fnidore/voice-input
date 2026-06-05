"""实时音量条（设计稿 .vmeter 同款）：竖向分段小条，中间高两边低。

- BarMeter: 通用波形条控件（设置窗口麦克风电平 / 录音 HUD 共用）
- VolumeMeter = BarMeter 别名，保持旧 API（set_level / levelChanged）
"""

from __future__ import annotations

import random

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from .style import palette

_IDLE_H = 0.10   # 待机时小条高度占比


class BarMeter(QWidget):
    """横排竖条电平表。set_level(0~1) 驱动；无电平时显示灰色短条。"""

    levelChanged = Signal(float)

    def __init__(self, bars: int = 22, parent=None) -> None:
        super().__init__(parent)
        self._bars = bars
        self._level = 0.0
        self._heights = [_IDLE_H] * bars
        self.setMinimumHeight(26)
        self.setMinimumWidth(140)
        # 90ms 抖动刷新（与设计稿动画节奏一致）
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(90)

    # ---- 旧 API 兼容 ----
    def set_level(self, level: float) -> None:
        level = max(0.0, min(1.0, float(level)))
        self._level = level
        if level > 0.02 and not self._timer.isActive():
            self._timer.start()
        self.levelChanged.emit(level)

    def _tick(self) -> None:
        if self._level <= 0.02:
            self._timer.stop()
            self._heights = [_IDLE_H] * self._bars
        else:
            amp = 0.25 + 0.75 * self._level
            n = self._bars
            self._heights = [
                max(0.08, min(1.0,
                    (1 - abs(i - n / 2) / (n / 2)) * (0.35 + random.random() * 0.65) * amp))
                for i in range(n)
            ]
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802
        P = palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        w, h = self.width(), self.height()
        gap = 3.0
        bw = max(2.0, (w - gap * (self._bars - 1)) / self._bars)
        active = self._level > 0.02
        color = QColor(P["accent"] if active else P["surface_3"])
        x = 0.0
        for hh in self._heights:
            bh = max(3.0, h * hh)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x, h - bh, bw, bh), 1.5, 1.5)
            x += bw + gap
        p.end()


# 旧名字兼容（settings_window 历史用法）
VolumeMeter = BarMeter
