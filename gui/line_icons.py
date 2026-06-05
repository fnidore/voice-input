"""设计稿同款线性图标（stroke-based, 24×24 viewBox）。

与设计稿 icons.jsx 对应：mic / wave / key / tag / clock / log / cpu /
check / x / sun / moon / sliders / minus。

用法：
    draw_line_icon(painter, "mic", QRectF(0, 0, 18, 18), "#5b8def")
    pix = icon_pixmap("key", size=15, color="#5a6071")
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _pen(color: str, sw: float) -> QPen:
    pen = QPen(QColor(color), sw)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


# ---- 各图标的描边路径（24×24 viewBox）----

def _mic(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(9, 2.5, 6, 11), 3, 3)
    path = QPainterPath(QPointF(5.5, 11))
    path.arcTo(QRectF(5.5, 5, 13, 13), 180, 180)  # U 形支架
    p.drawPath(path)
    p.drawLine(QPointF(12, 18), QPointF(12, 21))
    p.drawLine(QPointF(9, 21.5), QPointF(15, 21.5))


def _wave(p: QPainter) -> None:
    for x, y0, y1 in ((4, 10, 14), (8, 7, 17), (12, 4, 20), (16, 7, 17), (20, 10, 14)):
        p.drawLine(QPointF(x, y0), QPointF(x, y1))


def _key(p: QPainter) -> None:
    p.drawEllipse(QRectF(4, 12, 7.5, 7.5))
    p.drawLine(QPointF(10.8, 13.2), QPointF(20, 4))
    p.drawLine(QPointF(16.5, 7.5), QPointF(19.5, 10.5))


def _tag(p: QPainter) -> None:
    path = QPainterPath(QPointF(3.5, 3.5))
    path.lineTo(11, 3.5)
    path.lineTo(20.5, 13)
    path.lineTo(13, 20.5)
    path.lineTo(3.5, 11)
    path.closeSubpath()
    p.drawPath(path)
    p.drawEllipse(QRectF(7.3, 7.3, 1.6, 1.6))


def _clock(p: QPainter) -> None:
    p.drawEllipse(QRectF(3.5, 3.5, 17, 17))
    p.drawLine(QPointF(12, 7.5), QPointF(12, 12))
    p.drawLine(QPointF(12, 12), QPointF(15.5, 14))


def _log(p: QPainter) -> None:
    p.drawLine(QPointF(4, 6), QPointF(20, 6))
    p.drawLine(QPointF(4, 12), QPointF(20, 12))
    p.drawLine(QPointF(4, 18), QPointF(14, 18))


def _cpu(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(6.5, 6.5, 11, 11), 2, 2)
    p.drawRect(QRectF(10, 10, 4, 4))
    for v in (9.5, 14.5):
        p.drawLine(QPointF(v, 3), QPointF(v, 6.5))
        p.drawLine(QPointF(v, 17.5), QPointF(v, 21))
        p.drawLine(QPointF(3, v), QPointF(6.5, v))
        p.drawLine(QPointF(17.5, v), QPointF(21, v))


def _check(p: QPainter) -> None:
    path = QPainterPath(QPointF(4.5, 12.5))
    path.lineTo(10, 18)
    path.lineTo(19.5, 6.5)
    p.drawPath(path)


def _x(p: QPainter) -> None:
    p.drawLine(QPointF(6, 6), QPointF(18, 18))
    p.drawLine(QPointF(18, 6), QPointF(6, 18))


def _sun(p: QPainter) -> None:
    p.drawEllipse(QRectF(8, 8, 8, 8))
    for x0, y0, x1, y1 in (
        (12, 2.5, 12, 5), (12, 19, 12, 21.5), (2.5, 12, 5, 12), (19, 12, 21.5, 12),
        (5.2, 5.2, 7, 7), (17, 17, 18.8, 18.8), (18.8, 5.2, 17, 7), (7, 17, 5.2, 18.8),
    ):
        p.drawLine(QPointF(x0, y0), QPointF(x1, y1))


def _moon(p: QPainter) -> None:
    path = QPainterPath(QPointF(20.2, 13.5))
    path.arcTo(QRectF(3.5, 3.5, 17, 17), -30, -270)   # 大圆弧
    path.arcTo(QRectF(7.6, 1.8, 13.2, 13.2), 150, 122)  # 内咬一口
    p.drawPath(path)


def _sliders(p: QPainter) -> None:
    rows = ((7, 9.5), (12, 15), (17, 7))   # (y, 旋钮 x)
    for y, kx in rows:
        p.drawLine(QPointF(4, y), QPointF(20, y))
        p.save()
        p.setBrush(p.pen().color())
        p.drawEllipse(QRectF(kx - 2.2, y - 2.2, 4.4, 4.4))
        p.restore()


def _minus(p: QPainter) -> None:
    p.drawLine(QPointF(6, 12), QPointF(18, 12))


def _chevron_down(p: QPainter) -> None:
    path = QPainterPath(QPointF(6, 9.5))
    path.lineTo(12, 15.5)
    path.lineTo(18, 9.5)
    p.drawPath(path)


def _folder(p: QPainter) -> None:
    path = QPainterPath(QPointF(3.5, 7))
    path.lineTo(3.5, 18.5)
    path.lineTo(20.5, 18.5)
    path.lineTo(20.5, 8.5)
    path.lineTo(11.5, 8.5)
    path.lineTo(9.5, 5.5)
    path.lineTo(5, 5.5)
    path.closeSubpath()
    p.drawPath(path)


_DRAWERS = {
    "mic": _mic, "wave": _wave, "key": _key, "tag": _tag, "clock": _clock,
    "log": _log, "cpu": _cpu, "check": _check, "x": _x, "sun": _sun,
    "moon": _moon, "sliders": _sliders, "minus": _minus, "folder": _folder,
    "chevron-down": _chevron_down,
}


def draw_line_icon(
    p: QPainter, name: str, rect: QRectF, color: str, stroke: float = 2.0,
) -> None:
    """在指定矩形内绘制图标（按 24×24 viewBox 等比缩放）。"""
    drawer = _DRAWERS.get(name)
    if drawer is None:
        return
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    scale = min(rect.width(), rect.height()) / 24.0
    p.translate(rect.center().x() - 12 * scale, rect.center().y() - 12 * scale)
    p.scale(scale, scale)
    p.setPen(_pen(color, stroke))
    p.setBrush(Qt.NoBrush)
    drawer(p)
    p.restore()


def icon_pixmap(name: str, size: int = 16, color: str = "#5a6071",
                stroke: float = 2.0, dpr: float = 2.0) -> QPixmap:
    """生成高分屏友好的图标 QPixmap。"""
    pix = QPixmap(int(size * dpr), int(size * dpr))
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    draw_line_icon(p, name, QRectF(0, 0, size, size), color, stroke)
    p.end()
    return pix


def line_qicon(name: str, size: int = 16, color: str = "#5a6071",
               stroke: float = 2.0) -> QIcon:
    return QIcon(icon_pixmap(name, size, color, stroke))
