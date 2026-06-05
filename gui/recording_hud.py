"""录音胶囊 HUD（设计稿 floating.jsx / floating.css 同款）。

默认屏幕底部居中弹出，可按住拖到任意位置（记忆上次位置），不抢焦点：
- 正在聆听：珊瑚色话筒徽章 + 扩散光环 + 实时波形 + 计时
- 识别中：琥珀色 + 三个跳动圆点
- 已粘贴：蓝色 ✓ + 「已注入到光标位置」，1.5s 后淡出
- 错误：红色短暂提示

接线（tray_app）：
    hud.set_app_state(state.value)   # TrayApp.stateChanged
    hud.on_level(v)                  # TrayApp.levelChanged
    hud.on_recognized()              # TrayApp.recognized
"""

from __future__ import annotations

import math

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPropertyAnimation, QRect, QRectF, QSettings,
    Qt, QTimer,
)
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget,
)

from . import line_icons
from .style import FONT_MONO, current_theme, palette
from .volume_meter import BarMeter

# 状态表（与设计稿 FSTATE 对应；color 取 palette 键名）
_STATES = {
    "recording":  {"color": "rec",    "label": "正在聆听", "sub": "松开 {key} 结束并识别"},
    "processing": {"color": "proc",   "label": "识别中",   "sub": "模型推理…"},
    "done":       {"color": "accent", "label": "已粘贴",   "sub": "已注入到光标位置"},
    "error":      {"color": "error",  "label": "错误",     "sub": "请到 设置 → 日志 查看"},
}

_MARGIN_BOTTOM = 48
_SLIDE = 14
_POS_KEY = "hud_pos"   # QSettings("VoiceInput","ui") 中记忆的拖动位置


class _GlyphBadge(QWidget):
    """42px 圆角话筒徽章：状态色淡彩底 + 线性麦克风 + 录音扩散光环。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(52, 52)   # 含光环外溢 5px
        self._color_key = "rec"
        self._ring = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def set_state(self, color_key: str, ring: bool) -> None:
        self._color_key = color_key
        self._ring = ring
        if ring:
            self._phase = 0.0
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.033 / 1.4) % 1.0   # 1.4s 一轮
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802
        P = palette()
        color = QColor(P[self._color_key])
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tile = QRectF(5, 5, 42, 42)
        # 扩散光环
        if self._ring:
            t = self._phase
            ring_c = QColor(color)
            ring_c.setAlphaF(0.7 * (1.0 - t))
            grow = 4.0 * t
            p.setPen(QPen(ring_c, 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(tile.adjusted(-1 - grow, -1 - grow, 1 + grow, 1 + grow),
                              13 + grow, 13 + grow)
        # 淡彩底
        tint = QColor(color)
        tint.setAlphaF(0.14)
        p.setPen(Qt.NoPen)
        p.setBrush(tint)
        p.drawRoundedRect(tile, 13, 13)
        # 麦克风
        icon_r = QRectF(0, 0, 19, 19)
        icon_r.moveCenter(tile.center())
        line_icons.draw_line_icon(p, "mic", icon_r, color.name())
        p.end()


class _Dots(QWidget):
    """识别中三个跳动圆点。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(22)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.033) % 1.0
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        color = QColor(palette()["proc"])
        cy = self.height() / 2
        for i in range(3):
            t = (self._phase - i * 0.16) % 1.0
            lift = math.sin(t * math.pi) if t < 1.0 else 0.0
            c = QColor(color)
            c.setAlphaF(0.3 + 0.7 * lift)
            p.setBrush(c)
            p.drawEllipse(QRectF(6 + i * 13, cy - 3.5 - 3.0 * lift, 7, 7))
        p.end()


class RecordingHUD(QWidget):
    """底部居中弹出的胶囊 HUD。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            | Qt.Tool | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(320, 78)
        self.setCursor(Qt.OpenHandCursor)   # 暗示可拖动
        self.setFocusPolicy(Qt.NoFocus)     # 拖动也绝不抢键盘焦点（粘贴依赖光标所在输入框）

        self._state = "hidden"
        self._hotkey = "F4"
        self._seconds = 0
        self._drag_off: QPoint | None = None

        # ---- 布局：glyph | mid(上波形/点/sub + 下 label) | right(计时) ----
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 13, 18, 13)
        root.setSpacing(13)

        self._glyph = _GlyphBadge()
        root.addWidget(self._glyph, 0, Qt.AlignVCenter)

        mid = QVBoxLayout()
        mid.setSpacing(4)
        self._stack = QStackedWidget()
        self._stack.setFixedHeight(22)
        self._bars = BarMeter(bars=16)
        self._bars.setMinimumWidth(120)
        self._dots = _Dots()
        self._sub = QLabel()
        self._stack.addWidget(self._bars)    # 0 录音波形
        self._stack.addWidget(self._dots)    # 1 识别跳点
        self._stack.addWidget(self._sub)     # 2 文案
        mid.addWidget(self._stack)
        self._label = QLabel()
        mid.addWidget(self._label)
        root.addLayout(mid, 1)

        self._timer_lbl = QLabel()
        root.addWidget(self._timer_lbl, 0, Qt.AlignVCenter)

        self._sec_timer = QTimer(self)
        self._sec_timer.setInterval(1000)
        self._sec_timer.timeout.connect(self._on_second)

        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._fade_out)

        self._anim: QPropertyAnimation | None = None

    # ---------- 对外接口 ----------
    def set_hotkey_label(self, desc: str) -> None:
        self._hotkey = desc

    def set_app_state(self, value: str) -> None:
        """TrayApp State.value: init/idle/recording/processing/error/paused"""
        if value == "recording":
            self._show_state("recording")
        elif value == "processing":
            self._show_state("processing")
        elif value == "error":
            self._show_state("error")
            self._hold_timer.start(2200)
        elif value in ("idle", "paused", "init"):
            # 已粘贴有自己的 1.5s 停留；其余直接淡出
            if self._state != "done" and self.isVisible():
                self._fade_out()

    def on_level(self, level: float) -> None:
        if self._state == "recording":
            self._bars.set_level(level)

    def on_recognized(self, *_a) -> None:
        self._show_state("done")
        self._hold_timer.start(1500)

    def reset_position(self) -> None:
        """清除记忆位置，回到默认底部居中（设置窗口「恢复默认位置」）。"""
        QSettings("VoiceInput", "ui").remove(_POS_KEY)
        if self.isVisible():
            self.move(self._default_pos())

    # ---------- 拖动（位置记忆到 QSettings） ----------
    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton and self._state != "hidden":
            # 淡出中不开始拖动（finished→hide 拦不住，胶囊本来就该消失了）
            if self._anim is not None:
                self._anim.stop()   # 滑入动画也在动 pos，先停
            self._drag_off = ev.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.ClosedHandCursor)
            ev.accept()

    def mouseMoveEvent(self, ev) -> None:  # noqa: N802
        if self._drag_off is not None:
            self.move(ev.globalPosition().toPoint() - self._drag_off)
            ev.accept()

    def mouseReleaseEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton and self._drag_off is not None:
            self._drag_off = None
            self.setCursor(Qt.OpenHandCursor)
            QSettings("VoiceInput", "ui").setValue(_POS_KEY, self.pos())
            ev.accept()

    # ---------- 状态切换 ----------
    def _show_state(self, state: str) -> None:
        m = _STATES[state]
        P = palette()
        color = P[m["color"]]
        first_show = not self.isVisible()
        prev = self._state
        self._state = state
        self._hold_timer.stop()

        self._glyph.set_state(m["color"], ring=(state == "recording"))

        # 中部上层：波形 / 跳点 / 文案
        if state == "recording":
            self._stack.setCurrentIndex(0)
            self._bars.set_level(0.05)
            self._dots.stop()
        elif state == "processing":
            self._stack.setCurrentIndex(1)
            self._dots.start()
        else:
            self._stack.setCurrentIndex(2)
            self._dots.stop()
            self._sub.setText(m["sub"].format(key=self._hotkey))

        # label（done 带 ✓）
        check = "✓ " if state == "done" else ""
        self._label.setText(check + m["label"])

        # 计时器
        if state == "recording":
            self._seconds = 0
            self._timer_lbl.setText("0:00")
            self._timer_lbl.show()
            self._sec_timer.start()
        else:
            self._sec_timer.stop()
            self._timer_lbl.hide()

        self._apply_colors(color)
        if first_show:
            self._fade_in()
        elif prev != state:
            self.update()

    def _apply_colors(self, color: str) -> None:
        P = palette()
        self._sub.setStyleSheet(
            f"font-size: 12px; color: {P['text_3']}; background: transparent;")
        self._label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {color}; background: transparent;")
        self._timer_lbl.setStyleSheet(
            f"font-family: {FONT_MONO}; font-size: 13px; font-weight: 600; "
            f"color: {P['text_2']}; background: transparent;")

    def _on_second(self) -> None:
        self._seconds += 1
        self._timer_lbl.setText(f"{self._seconds // 60}:{self._seconds % 60:02d}")

    # ---------- 进出场动画 ----------
    def _default_pos(self) -> QPoint:
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else None
        if geo is None:
            return QPoint(200, 200)
        return QPoint(
            geo.center().x() - self.width() // 2,
            geo.bottom() - self.height() - _MARGIN_BOTTOM,
        )

    def _target_pos(self) -> QPoint:
        """优先用上次拖动记忆的位置；坐标已不在任何屏幕上（换显示器/改分辨率）则回默认。"""
        saved = QSettings("VoiceInput", "ui").value(_POS_KEY)
        if isinstance(saved, QPoint) and self._on_any_screen(saved):
            return saved
        return self._default_pos()

    def _on_any_screen(self, pos: QPoint) -> bool:
        probe = QRect(pos, self.size())
        return any(s.availableGeometry().intersects(probe)
                   for s in QGuiApplication.screens())

    def _fade_in(self) -> None:
        pos = self._target_pos()
        self.move(pos.x(), pos.y() + _SLIDE)
        self.setWindowOpacity(0.0)
        self.show()
        self._animate(1.0, pos, on_done=None)

    def _fade_out(self) -> None:
        if not self.isVisible():
            return
        self._state = "hidden"
        self._sec_timer.stop()
        self._dots.stop()
        pos = self.pos() + QPoint(0, _SLIDE)
        self._animate(0.0, pos, on_done=self.hide)

    def _animate(self, opacity: float, pos: QPoint, on_done) -> None:
        if self._anim is not None:
            self._anim.stop()
            self._anim.deleteLater()   # 防止旧动画对象在常驻进程里累积
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(180)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setEndValue(pos)
        anim.start()
        self._anim = anim
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(180)
        fade.setEndValue(opacity)
        if on_done is not None:
            fade.finished.connect(on_done)
        fade.start(QPropertyAnimation.DeleteWhenStopped)

    # ---------- 胶囊本体 ----------
    def paintEvent(self, _ev) -> None:  # noqa: N802
        P = palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        bg = QColor(P["surface"])
        bg.setAlphaF(0.97)
        border = (QColor(255, 255, 255, 20) if current_theme() == "dark"
                  else QColor(24, 33, 56, 20))
        p.setPen(QPen(border, 1))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 18, 18)
        p.end()
