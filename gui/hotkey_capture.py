"""自定义快捷键捕获按钮：点击 -> 监听下一次按键 -> 转成 spec 字符串"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton
from pynput import keyboard


class HotkeyCaptureButton(QPushButton):
    """点击进入捕获模式，下一次按键作为快捷键。

    输出 spec 兼容 core.hotkey.parse_hotkey：
      - 特殊键 -> "f4" / "ctrl_r" / ...
      - 字符   -> "a" / "1" / ...
      - 兜底   -> "vk:数字"
    """

    captured = Signal(str)   # 捕获到的 spec

    def __init__(self, initial_spec: str = "f4", parent=None) -> None:
        super().__init__(parent)
        self._spec = initial_spec
        self._capturing = False
        self._listener: keyboard.Listener | None = None
        self._update_label()
        self.clicked.connect(self._start_capture)

    def spec(self) -> str:
        return self._spec

    def set_spec(self, spec: str) -> None:
        self._spec = spec
        self._update_label()

    def _update_label(self) -> None:
        if self._capturing:
            self.setText("⌨️ 按下你想要的键…（Esc 取消）")
        else:
            self.setText("点击重新捕获")

    def _start_capture(self) -> None:
        if self._capturing:
            return
        self._capturing = True
        self._update_label()
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.start()

    def _stop_capture(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._capturing = False
        self._update_label()

    def _on_press(self, key) -> bool:
        # Esc 取消
        if key == keyboard.Key.esc:
            self._stop_capture()
            return False

        spec: str
        try:
            # 特殊键
            spec = key.name
        except AttributeError:
            if getattr(key, "char", None):
                spec = key.char
            else:
                vk = getattr(key, "vk", None)
                spec = f"vk:{vk}" if vk else "f4"

        self._spec = spec
        self.captured.emit(spec)
        self._stop_capture()
        return False
