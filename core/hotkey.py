"""全局快捷键监听：按住 / 松开 触发，支持单按键 / 字符 / vk 码"""

from __future__ import annotations

import logging
import threading
from typing import Callable

from pynput import keyboard

logger = logging.getLogger(__name__)


def parse_hotkey(spec: str) -> tuple[Callable, str]:
    """
    返回 (matcher, human_readable_desc)
    支持:
      - 特殊键: ctrl_r / alt_r / f1..f24 / shift / cmd ...
      - 字符:   a / 1 / `
      - VK 码:  vk:269025067
    """
    spec = spec.strip()

    if spec.startswith("vk:"):
        target_vk = int(spec[3:])

        def match(key):
            return getattr(key, "vk", None) == target_vk

        return match, f"vk={target_vk}"

    if hasattr(keyboard.Key, spec):
        target = getattr(keyboard.Key, spec)

        def match(key):
            return key == target

        return match, spec

    if len(spec) == 1:
        def match(key):
            return getattr(key, "char", None) == spec

        return match, f"char '{spec}'"

    raise ValueError(
        f"无法解析快捷键 '{spec}'。可选: ctrl_r/alt_r/f1~f12 等特殊键，"
        f"或单字符，或 vk:数字"
    )


class HotkeyListener:
    """后台线程监听快捷键的按下 / 松开。"""

    def __init__(
        self,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        self.on_press = on_press
        self.on_release = on_release
        self._matcher: Callable | None = None
        self._desc: str = ""
        self._listener: keyboard.Listener | None = None
        self._lock = threading.Lock()

    def set_hotkey(self, spec: str) -> None:
        matcher, desc = parse_hotkey(spec)
        with self._lock:
            self._matcher = matcher
            self._desc = desc
        logger.info("hotkey set to %s", desc)

    @property
    def description(self) -> str:
        return self._desc

    def _on_press_raw(self, key):
        with self._lock:
            matcher = self._matcher
        if matcher and matcher(key):
            try:
                self.on_press()
            except Exception as e:
                logger.error("on_press error: %s", e)

    def _on_release_raw(self, key):
        with self._lock:
            matcher = self._matcher
        if matcher and matcher(key):
            try:
                self.on_release()
            except Exception as e:
                logger.error("on_release error: %s", e)

    def start(self) -> None:
        if self._listener is not None:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press_raw,
            on_release=self._on_release_raw,
        )
        self._listener.start()
        logger.info("hotkey listener started")

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            logger.info("hotkey listener stopped")
