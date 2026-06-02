"""设置窗口深色霓虹主题（呼应 app 图标的青 #22d3ee / 品紫 #e23bf0 配色）。

只负责样式，不含业务逻辑。SettingsWindow 在 __init__ 里调用 apply_neon_theme(self)。
"""

from __future__ import annotations

NEON_QSS = """
QDialog, QWidget { background: #0d1320; color: #e6edf3; font-size: 14px; }

/* ---- Tab ---- */
QTabWidget::pane { border: 1px solid #2a3550; border-radius: 8px; top: -1px; background: #0f1626; }
QTabBar::tab {
    background: #161d2e; color: #9aa7bd;
    padding: 8px 18px; margin-right: 4px;
    border: 1px solid #2a3550; border-bottom: none;
    border-top-left-radius: 8px; border-top-right-radius: 8px;
}
QTabBar::tab:selected { background: #0f1626; color: #22d3ee; border-color: #22d3ee; }
QTabBar::tab:hover:!selected { color: #cfe9ff; }

QLabel { background: transparent; color: #cdd7e6; }

/* ---- 输入类控件 ---- */
QComboBox, QLineEdit, QPlainTextEdit, QTextEdit, QListWidget, QDoubleSpinBox, QSpinBox {
    background: #161d2e; color: #e6edf3;
    border: 1px solid #2a3550; border-radius: 7px;
    padding: 6px 10px; selection-background-color: #0e7490;
}
QComboBox:hover, QLineEdit:hover, QDoubleSpinBox:hover, QSpinBox:hover { border-color: #22d3ee; }
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus { border-color: #22d3ee; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow {
    width: 0; height: 0; margin-right: 10px;
    border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid #22d3ee;
}
QComboBox QAbstractItemView {
    background: #161d2e; color: #e6edf3;
    border: 1px solid #22d3ee; border-radius: 6px;
    selection-background-color: #0e7490; outline: none;
}
QComboBox:disabled, QLineEdit:disabled, QPlainTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: #5a6678; background: #121826; border-color: #222c40;
}

/* ---- 按钮 ---- */
QPushButton {
    background: #1b2438; color: #cfe9ff;
    border: 1px solid #2a3550; border-radius: 7px;
    padding: 7px 16px; font-weight: 600;
}
QPushButton:hover { border-color: #22d3ee; color: #22d3ee; }
QPushButton:pressed { background: #0e7490; color: #ffffff; }
QPushButton:disabled { color: #5a6678; border-color: #222c40; }

/* ---- 复选框 ---- */
QCheckBox { background: transparent; color: #cdd7e6; spacing: 8px; }
QCheckBox::indicator {
    width: 18px; height: 18px; border-radius: 5px;
    border: 1px solid #2a3550; background: #161d2e;
}
QCheckBox::indicator:checked { background: #22d3ee; border-color: #22d3ee; }
QCheckBox::indicator:hover { border-color: #22d3ee; }

/* ---- 分组框 ---- */
QGroupBox {
    border: 1px solid #2a3550; border-radius: 8px;
    margin-top: 14px; padding-top: 10px; font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #22d3ee; }

/* ---- 微调按钮 ---- */
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button { width: 18px; background: #1b2438; border: none; }

/* ---- 滚动条 ---- */
QScrollBar:vertical { background: #0f1626; width: 12px; border-radius: 6px; margin: 0; }
QScrollBar::handle:vertical { background: #2a3550; border-radius: 6px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #22d3ee; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #0f1626; height: 12px; border-radius: 6px; }
QScrollBar::handle:horizontal { background: #2a3550; border-radius: 6px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #22d3ee; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ---- 列表 ---- */
QListWidget::item { padding: 5px; border-radius: 4px; }
QListWidget::item:selected { background: #0e7490; color: #ffffff; }
QListWidget::item:hover { background: #1f2940; }

QToolTip { background: #161d2e; color: #e6edf3; border: 1px solid #22d3ee; padding: 4px; }
"""


def apply_neon_theme(widget) -> None:
    """给窗口套上深色霓虹主题。"""
    widget.setStyleSheet(NEON_QSS)
