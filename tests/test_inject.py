"""core.inject 跨平台文字注入层测试。

设计目标：
- Linux 后端保留原有 xdotool/xclip 行为（回归保护）。
- Windows / macOS 后端用 pyperclip 写剪贴板 + pynput 模拟粘贴键。
- 公共接口（inject_via_paste / inject_via_type / check_deps 等）跨平台一致。
"""

from __future__ import annotations

import sys
import types

import pytest

from core import inject
from core.inject import linux as linux_backend
from core.inject import macos as mac_backend
from core.inject import windows as win_backend


# --------------------------------------------------------------------------- #
# 平台分发
# --------------------------------------------------------------------------- #
class TestBackendSelection:
    def test_linux(self):
        assert inject._select_backend("linux") is linux_backend

    def test_linux2(self):
        assert inject._select_backend("linux2") is linux_backend

    def test_windows(self):
        assert inject._select_backend("win32") is win_backend

    def test_macos(self):
        assert inject._select_backend("darwin") is mac_backend

    def test_unknown_defaults_to_linux(self):
        assert inject._select_backend("freebsd14") is linux_backend


# --------------------------------------------------------------------------- #
# 公共接口存在且可调用
# --------------------------------------------------------------------------- #
class TestPublicApi:
    @pytest.mark.parametrize(
        "name",
        [
            "inject_via_paste",
            "inject_via_type",
            "check_deps",
            "is_terminal_window",
            "detect_active_window_class",
            "get_backend_name",
        ],
    )
    def test_export_is_callable(self, name):
        assert callable(getattr(inject, name))


# --------------------------------------------------------------------------- #
# Linux 后端：保留 xclip/xdotool 行为
# --------------------------------------------------------------------------- #
class TestLinuxBackend:
    def _patch_subprocess(self, monkeypatch):
        calls = []

        def fake_run(cmd, *a, **k):
            calls.append(cmd)

            class R:
                returncode = 0
                stdout = ""  # detect 返回空串 -> 非终端，避免触发 bytes 分支

            return R()

        monkeypatch.setattr(linux_backend.subprocess, "run", fake_run)
        return calls

    def test_paste_writes_clipboard_and_presses_key(self, monkeypatch):
        calls = self._patch_subprocess(monkeypatch)
        linux_backend.inject_via_paste("你好", "ctrl+v", "ctrl+shift+v")
        assert any("xclip" in str(c) for c in calls), "应写入 xclip 剪贴板"
        assert any("xdotool" in str(c) for c in calls), "应用 xdotool 模拟粘贴键"

    def test_paste_empty_is_noop(self, monkeypatch):
        calls = self._patch_subprocess(monkeypatch)
        linux_backend.inject_via_paste("", "ctrl+v", "ctrl+shift+v")
        assert calls == []

    def test_type_uses_xdotool_type(self, monkeypatch):
        calls = self._patch_subprocess(monkeypatch)
        linux_backend.inject_via_type("abc")
        assert any("xdotool" in str(c) and "type" in str(c) for c in calls)

    def test_check_deps_reports_missing(self, monkeypatch):
        # which 全部返回非 0 -> 全部缺失
        def fake_run(cmd, *a, **k):
            class R:
                returncode = 1
                stdout = ""

            return R()

        monkeypatch.setattr(linux_backend.subprocess, "run", fake_run)
        missing = linux_backend.check_deps("paste")
        assert "xdotool" in missing
        assert "xclip" in missing


# --------------------------------------------------------------------------- #
# Windows / macOS 后端：pyperclip + pynput
# --------------------------------------------------------------------------- #
def _install_fake_clipboard_and_keyboard(monkeypatch):
    """注入假的 pyperclip 与 pynput，返回 (state) 供断言。"""
    state = {"copies": [], "pressed": []}

    fake_pyperclip = types.SimpleNamespace(
        copy=lambda t: state["copies"].append(t),
        paste=lambda: "",
    )
    monkeypatch.setitem(sys.modules, "pyperclip", fake_pyperclip)

    class FakeController:
        def press(self, k):
            state["pressed"].append(("press", k))

        def release(self, k):
            state["pressed"].append(("release", k))

        def type(self, t):
            state["pressed"].append(("type", t))

    fake_key = types.SimpleNamespace(ctrl="KEY_CTRL", cmd="KEY_CMD", shift="KEY_SHIFT")
    fake_keyboard = types.SimpleNamespace(Controller=FakeController, Key=fake_key)
    fake_pynput = types.SimpleNamespace(keyboard=fake_keyboard)
    monkeypatch.setitem(sys.modules, "pynput", fake_pynput)
    monkeypatch.setitem(sys.modules, "pynput.keyboard", fake_keyboard)
    return state


class TestWindowsBackend:
    def test_paste_copies_text_and_presses_ctrl(self, monkeypatch):
        state = _install_fake_clipboard_and_keyboard(monkeypatch)
        win_backend.inject_via_paste("你好世界")
        assert "你好世界" in state["copies"]
        # 用到了 ctrl 修饰键
        assert any(item[1] == "KEY_CTRL" for item in state["pressed"])

    def test_paste_empty_is_noop(self, monkeypatch):
        state = _install_fake_clipboard_and_keyboard(monkeypatch)
        win_backend.inject_via_paste("")
        assert state["copies"] == []
        assert state["pressed"] == []

    def test_check_deps_is_empty(self, monkeypatch):
        # Windows 不依赖外部命令行工具（mock pyperclip/pynput 模拟已安装，
        # 避免在 headless Linux CI 上真实 import pynput 触发 X 连接失败）
        _install_fake_clipboard_and_keyboard(monkeypatch)
        assert win_backend.check_deps("paste") == []

    def test_is_terminal_window_false(self):
        assert win_backend.is_terminal_window() is False


class TestMacosBackend:
    def test_paste_copies_text_and_presses_cmd(self, monkeypatch):
        state = _install_fake_clipboard_and_keyboard(monkeypatch)
        mac_backend.inject_via_paste("hello")
        assert "hello" in state["copies"]
        # macOS 用 Cmd 粘贴
        assert any(item[1] == "KEY_CMD" for item in state["pressed"])

    def test_check_deps_is_empty(self, monkeypatch):
        _install_fake_clipboard_and_keyboard(monkeypatch)
        assert mac_backend.check_deps("paste") == []
