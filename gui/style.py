"""设置窗口浅色「柔和卡片」主题（清新简约 · 单一蓝点缀 #5b8def）。

只负责样式，不含业务逻辑。SettingsWindow 在 __init__ 里调用 apply_soft_theme(self)。
为兼容老代码，apply_neon_theme 作为别名保留。

其它模块（icons.py / volume_meter.py）可 `from .style import PALETTE` 复用配色，
保持托盘图标、音量条与窗口同一套颜色。
"""

from __future__ import annotations

# ---- 调色板（与设计稿 tokens 对应；浅色为主，单一蓝点缀）----
PALETTE = {
    "bg":          "#f1f4f8",   # 窗口底（浅冷灰）
    "surface":     "#ffffff",   # 卡片 / 输入框
    "surface_2":   "#f6f7f9",   # 次级面（分段控件槽）
    "surface_3":   "#eef0f3",   # 三级面（滑块槽 / 音量条底）
    "text":        "#1b1e25",
    "text_2":      "#5a6071",
    "text_3":      "#99a0b0",
    "border":      "#e8eaef",
    "border_2":    "#dde0e7",
    "accent":      "#5b8def",
    "accent_press":"#3f72db",
    "accent_tint": "rgba(91, 141, 239, 0.12)",
    "on_accent":   "#ffffff",
    # 状态色（供 icons / 浮窗复用）
    "rec":   "#ef6c54",
    "proc":  "#e8a13a",
    "done":  "#5b8def",
    "error": "#e0584f",
    "idle":  "#99a0b0",
}

# 跨平台友好的字体栈（Manrope 装了就用，否则回退系统中英文）
_FONT = ('"Manrope", "PingFang SC", "Microsoft YaHei", '
         '"Noto Sans CJK SC", "Segoe UI", -apple-system, sans-serif')
_MONO = ('"JetBrains Mono", "SF Mono", "Cascadia Code", '
         '"Roboto Mono", Menlo, Consolas, monospace')


def _qss() -> str:
    P = PALETTE
    return f"""
* {{ font-family: {_FONT}; }}
QDialog, QWidget {{ background: {P['bg']}; color: {P['text']}; font-size: 14px; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ---- Tab：顶部居中分段胶囊 ---- */
QTabWidget::pane {{ border: none; background: transparent; top: 2px; }}
QTabWidget::tab-bar {{ alignment: center; }}
QTabBar {{ background: transparent; qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent; color: {P['text_2']};
    padding: 8px 20px; margin: 6px 3px;
    border: 1px solid transparent; border-radius: 9px;
    font-weight: 600; font-size: 13px;
}}
QTabBar::tab:hover:!selected {{ color: {P['text']}; }}
QTabBar::tab:selected {{
    background: {P['surface']}; color: {P['accent']};
    border: 1px solid {P['border']};
}}

QLabel {{ background: transparent; color: {P['text']}; }}

/* ---- 卡片（QGroupBox 作为分组卡）---- */
QGroupBox {{
    background: {P['surface']};
    border: 1px solid {P['border']};
    border-radius: 16px;
    margin-top: 16px;
    padding: 20px 18px 16px;
    font-weight: 700;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 16px; top: 2px; padding: 0 6px;
    color: {P['text']}; font-size: 14px;
}}

/* ---- 输入类控件 ---- */
QComboBox, QLineEdit, QPlainTextEdit, QTextEdit, QListWidget, QDoubleSpinBox, QSpinBox {{
    background: {P['surface']}; color: {P['text']};
    border: 1px solid {P['border_2']}; border-radius: 10px;
    padding: 9px 12px; selection-background-color: {P['accent']};
    selection-color: {P['on_accent']};
}}
QComboBox:hover, QLineEdit:hover, QDoubleSpinBox:hover, QSpinBox:hover {{ border-color: {P['accent']}; }}
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QDoubleSpinBox:focus, QSpinBox:focus {{ border-color: {P['accent']}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{
    width: 0; height: 0; margin-right: 12px;
    border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid {P['text_3']};
}}
QComboBox QAbstractItemView {{
    background: {P['surface']}; color: {P['text']};
    border: 1px solid {P['border_2']}; border-radius: 10px;
    selection-background-color: {P['accent']}; selection-color: {P['on_accent']};
    outline: none; padding: 4px;
}}
QComboBox:disabled, QLineEdit:disabled, QPlainTextEdit:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {P['text_3']}; background: {P['surface_2']}; border-color: {P['border']};
}}
QPlainTextEdit, QTextEdit {{ padding: 12px 14px; }}

/* ---- 按钮 ---- */
QPushButton {{
    background: {P['surface']}; color: {P['text']};
    border: 1px solid {P['border_2']}; border-radius: 10px;
    padding: 9px 18px; font-weight: 600;
}}
QPushButton:hover {{ border-color: {P['accent']}; color: {P['accent']}; }}
QPushButton:pressed {{ background: {P['accent_tint']}; }}
QPushButton:disabled {{ color: {P['text_3']}; border-color: {P['border']}; }}
/* 主按钮（保存）：btn.setObjectName("primary") */
QPushButton#primary {{ background: {P['accent']}; color: {P['on_accent']}; border-color: {P['accent']}; }}
QPushButton#primary:hover {{ background: {P['accent_press']}; border-color: {P['accent_press']}; color: {P['on_accent']}; }}
QPushButton#primary:pressed {{ background: {P['accent_press']}; }}

/* ---- 复选框（保留；推荐用 widgets.ToggleSwitch 替换开关项）---- */
QCheckBox {{ background: transparent; color: {P['text']}; spacing: 9px; }}
QCheckBox::indicator {{
    width: 20px; height: 20px; border-radius: 6px;
    border: 1px solid {P['border_2']}; background: {P['surface']};
}}
QCheckBox::indicator:checked {{ background: {P['accent']}; border-color: {P['accent']}; }}
QCheckBox::indicator:hover {{ border-color: {P['accent']}; }}

/* ---- 微调按钮 ---- */
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {{
    width: 20px; background: {P['surface_2']}; border: none; border-radius: 5px;
}}

/* ---- 滚动条 ---- */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {P['border_2']}; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {P['accent']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {P['border_2']}; border-radius: 5px; min-width: 28px; }}
QScrollBar::handle:horizontal:hover {{ background: {P['accent']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ---- 列表 ---- */
QListWidget {{ padding: 6px; }}
QListWidget::item {{ padding: 9px 11px; border-radius: 9px; margin: 1px 0; }}
QListWidget::item:selected {{ background: {P['accent_tint']}; color: {P['text']}; }}
QListWidget::item:hover {{ background: {P['surface_2']}; }}

QToolTip {{
    background: {P['surface']}; color: {P['text']};
    border: 1px solid {P['border_2']}; border-radius: 6px; padding: 5px 8px;
}}
"""


def apply_soft_theme(widget) -> None:
    """给窗口套上浅色「柔和卡片」主题。"""
    widget.setStyleSheet(_qss())


# 兼容旧入口
def apply_neon_theme(widget) -> None:
    apply_soft_theme(widget)


# 旧常量名兼容（如有引用）
NEON_QSS = ""
