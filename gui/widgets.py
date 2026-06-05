"""「柔和卡片」自定义控件库（与设计稿 atoms.jsx / variants.css 对应）。

- ToggleSwitch  iOS 式滑动开关（动画，主题实时取色）
- HSep          发丝线分隔（卡片内通栏）
- IconBadge     淡彩底圆角图标徽章（卡片头 / 品牌标）
- Card          白色圆角卡片：图标徽章 + 标题 + 描述 + 分节
- SegmentedControl  胶囊分段控件（可带图标，用于顶部 Tab / cuda:0|cpu 等）
- FlowLayout / ChipFlow  热词流式 chips（× 删除、回车添加）

自绘控件一律在 paintEvent 里调 style.palette() 实时取色，
主题切换后只需 update()；QSS 控件由窗口统一重新 polish。
"""

from __future__ import annotations

from PySide6.QtCore import (
    Property, QEasingCurve, QPoint, QPropertyAnimation, QRect, QRectF,
    QSize, Qt, Signal,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractButton, QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from . import line_icons
from .style import palette


def _mix(c1: QColor, c2: QColor, t: float) -> QColor:
    """c1→c2 线性插值（t: 0~1）。"""
    return QColor(
        round(c1.red()   + (c2.red()   - c1.red())   * t),
        round(c1.green() + (c2.green() - c1.green()) * t),
        round(c1.blue()  + (c2.blue()  - c1.blue())  * t),
    )


def repolish(w: QWidget) -> None:
    """动态属性变更后刷新 QSS。"""
    w.style().unpolish(w)
    w.style().polish(w)


# ============================================================
# ToggleSwitch
# ============================================================
class ToggleSwitch(QAbstractButton):
    """滑动开关，用法同 QCheckBox：setChecked / isChecked / toggled。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._w, self._h, self._pad = 42, 24, 3
        self.setFixedSize(self._w, self._h)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate_to)

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
        if not self.isVisible():   # 初始化直接落位，不播动画
            self._pos = 1.0 if on else 0.0

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._w, self._h)

    def paintEvent(self, _ev) -> None:  # noqa: N802
        P = palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(_mix(QColor(P["surface_3"]), QColor(P["accent"]), self._pos))
        p.drawRoundedRect(QRectF(0, 0, self._w, self._h), self._h / 2, self._h / 2)
        d = self._h - self._pad * 2
        x = self._pad + self._pos * (self._w - d - self._pad * 2)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, self._pad, d, d))
        p.end()


# ============================================================
# HSep — 发丝线
# ============================================================
class HSep(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(1)

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(palette()["border"]))
        p.end()


# ============================================================
# IconBadge — 淡彩底圆角图标徽章
# ============================================================
class IconBadge(QWidget):
    def __init__(self, icon: str, size: int = 30, icon_size: int = 17,
                 radius: int = 9, parent=None) -> None:
        super().__init__(parent)
        self._icon = icon
        self._isz = icon_size
        self._radius = radius
        self.setFixedSize(size, size)

    def paintEvent(self, _ev) -> None:  # noqa: N802
        P = palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tint = QColor(P["accent"])
        tint.setAlphaF(0.13)
        p.setPen(Qt.NoPen)
        p.setBrush(tint)
        p.drawRoundedRect(QRectF(self.rect()), self._radius, self._radius)
        r = QRectF(0, 0, self._isz, self._isz)
        r.moveCenter(QRectF(self.rect()).center())
        line_icons.draw_line_icon(p, self._icon, r, P["accent"])
        p.end()


# ============================================================
# Card — 柔和卡片（图标徽章 + 标题 + 描述 + 分节）
# ============================================================
class Card(QFrame):
    """白色圆角卡片。card.add(widget/layout) 往当前节加内容，
    card.divider() 插入通栏发丝线并开新节。可选 corner 放在头部右侧。"""

    def __init__(self, icon: str, title: str, desc: str = "",
                 corner: QWidget | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("vi", "card")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        head = QHBoxLayout()
        head.setContentsMargins(20, 18, 20, 0)
        head.setSpacing(10)
        head.addWidget(IconBadge(icon))
        col = QVBoxLayout()
        col.setSpacing(1)
        lbl_t = QLabel(title)
        lbl_t.setProperty("vi", "cardTitle")
        col.addWidget(lbl_t)
        if desc:
            lbl_d = QLabel(desc)
            lbl_d.setProperty("vi", "cardDesc")
            col.addWidget(lbl_d)
        head.addLayout(col, 1)
        if corner is not None:
            head.addWidget(corner, 0, Qt.AlignVCenter)
        head_w = QWidget()
        head_w.setLayout(head)
        self._outer.addWidget(head_w)

        self._section: QVBoxLayout | None = None
        self._new_section()

    def _new_section(self) -> None:
        sec = QWidget()
        lay = QVBoxLayout(sec)
        lay.setContentsMargins(20, 15, 20, 17)
        lay.setSpacing(13)
        self._outer.addWidget(sec)
        self._section = lay

    def add(self, item) -> None:
        if isinstance(item, QLayout):
            self._section.addLayout(item)
        else:
            self._section.addWidget(item)

    def divider(self) -> None:
        """通栏发丝线 + 开新节。"""
        self._outer.addWidget(HSep())
        self._new_section()


# ============================================================
# SegmentedControl — 胶囊分段控件
# ============================================================
class SegmentedControl(QFrame):
    """items: [(value, label, icon|None), ...]；changed(str) 信号。"""

    changed = Signal(str)

    def __init__(self, items: list[tuple], full: bool = False,
                 icon_size: int = 15, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("segSlot")
        self._items = items
        self._icon_size = icon_size
        self._value = items[0][0]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(3)
        self._buttons: dict[str, QPushButton] = {}
        for value, label, icon in items:
            btn = QPushButton(label)
            btn.setProperty("segItem", "true")
            btn.setProperty("segOn", "false")
            btn.setProperty("segIcon", icon or "")
            btn.setCursor(Qt.PointingHandCursor)
            if full:
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _=False, v=value: self.set_value(v, emit=True))
            lay.addWidget(btn, 1 if full else 0)
            self._buttons[value] = btn
        if not full:
            self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._sync()

    def value(self) -> str:
        return self._value

    def set_value(self, value: str, emit: bool = False) -> None:
        if value not in self._buttons:
            return
        changed = value != self._value
        self._value = value
        self._sync()
        if emit and changed:
            self.changed.emit(value)

    def refresh_theme(self) -> None:
        self._sync()

    def _sync(self) -> None:
        P = palette()
        for value, btn in self._buttons.items():
            on = value == self._value
            btn.setProperty("segOn", "true" if on else "false")
            icon = btn.property("segIcon")
            if icon:
                color = P["accent"] if on else P["text_2"]
                btn.setIcon(line_icons.line_qicon(icon, self._icon_size, color))
                btn.setIconSize(QSize(self._icon_size, self._icon_size))
            repolish(btn)


# ============================================================
# FlowLayout — 流式布局（Qt 官方示例移植）
# ============================================================
class FlowLayout(QLayout):
    def __init__(self, parent=None, hspacing: int = 8, vspacing: int = 8) -> None:
        super().__init__(parent)
        self._items: list = []
        self._h, self._v = hspacing, vspacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i: int):  # noqa: N802
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i: int):  # noqa: N802
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientations(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, test: bool) -> int:
        x, y, line_h = rect.x(), rect.y(), 0
        for item in self._items:
            w, h = item.sizeHint().width(), item.sizeHint().height()
            if x + w > rect.right() + 1 and line_h > 0:
                x = rect.x()
                y += line_h + self._v
                line_h = 0
            if not test:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x += w + self._h
            line_h = max(line_h, h)
        return y + line_h - rect.y()


# ============================================================
# ChipFlow — 热词 chips（× 删除、回车添加）
# ============================================================
class _Chip(QFrame):
    removed = Signal(str)

    def __init__(self, word: str, parent=None) -> None:
        super().__init__(parent)
        self.word = word
        self.setProperty("vi", "chip")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(13, 5, 7, 5)
        lay.setSpacing(7)
        lbl = QLabel(word)
        lbl.setProperty("vi", "chipText")
        lay.addWidget(lbl)
        btn = QPushButton()
        btn.setProperty("chipX", "true")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip("移除")
        btn.setIcon(line_icons.line_qicon("x", 11, palette()["text_3"], stroke=2.4))
        btn.setIconSize(QSize(11, 11))
        btn.clicked.connect(lambda: self.removed.emit(self.word))
        lay.addWidget(btn)


class ChipFlow(QWidget):
    """热词流：chips + 末尾虚线输入框（回车 / 空格分隔批量添加）。"""

    wordsChanged = Signal()

    def __init__(self, words: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._flow = FlowLayout(self, hspacing=8, vspacing=8)
        self._input = QLineEdit()
        self._input.setProperty("vi", "chipInput")
        self._input.setPlaceholderText("+ 添加热词，回车确认")
        self._input.setMinimumWidth(170)
        self._input.returnPressed.connect(self._on_enter)
        self._words: list[str] = []
        self.set_words(words or [])

    def words(self) -> list[str]:
        return list(self._words)

    def set_words(self, words: list[str]) -> None:
        self._words = []
        while self._flow.count():
            item = self._flow.takeAt(0)
            if item.widget() is not None and item.widget() is not self._input:
                item.widget().deleteLater()
        seen = set()
        for w in words:
            w = w.strip()
            if w and w not in seen:
                seen.add(w)
                self._words.append(w)
                self._add_chip(w)
        self._flow.addWidget(self._input)
        self.updateGeometry()

    def _add_chip(self, word: str) -> None:
        chip = _Chip(word)
        chip.removed.connect(self._remove)
        self._flow.addWidget(chip)

    def _on_enter(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        merged = self._words + text.split()
        self.set_words(merged)
        self.wordsChanged.emit()

    def _remove(self, word: str) -> None:
        self.set_words([w for w in self._words if w != word])
        self.wordsChanged.emit()


# ============================================================
# 小工具
# ============================================================
def field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("vi", "fieldLabel")
    return lbl


def hint_label(text: str, mono: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("vi", "hintMono" if mono else "hint")
    lbl.setWordWrap(True)
    return lbl


def pill_label(text: str, kind: str = "pill") -> QLabel:
    """kind: pill / pillOk / pillWarn"""
    lbl = QLabel(text)
    lbl.setProperty("vi", kind)
    return lbl


def set_pill_kind(lbl: QLabel, kind: str) -> None:
    lbl.setProperty("vi", kind)
    repolish(lbl)


def toggle_row(title: str, desc: str, switch: ToggleSwitch) -> QHBoxLayout:
    """设计稿 tog-row：左标题+描述，右开关。"""
    row = QHBoxLayout()
    row.setSpacing(14)
    col = QVBoxLayout()
    col.setSpacing(2)
    t = QLabel(title)
    t.setProperty("vi", "togTitle")
    d = QLabel(desc)
    d.setProperty("vi", "togDesc")
    col.addWidget(t)
    col.addWidget(d)
    row.addLayout(col, 1)
    row.addWidget(switch, 0, Qt.AlignVCenter)
    return row
