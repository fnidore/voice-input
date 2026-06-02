"""gui.autostart 跨平台开机自启层测试。

- Linux: systemd user service（mock systemctl）
- Windows: 「启动」文件夹放 .bat
- macOS: ~/Library/LaunchAgents/*.plist（mock launchctl）
"""

from __future__ import annotations

import sys

import pytest

from gui import autostart
from gui.autostart import linux as linux_backend
from gui.autostart import macos as mac_backend
from gui.autostart import windows as win_backend


# --------------------------------------------------------------------------- #
# 平台分发
# --------------------------------------------------------------------------- #
class TestBackendSelection:
    def test_linux(self):
        assert autostart._select_backend("linux") is linux_backend

    def test_windows(self):
        assert autostart._select_backend("win32") is win_backend

    def test_macos(self):
        assert autostart._select_backend("darwin") is mac_backend

    def test_unknown_defaults_to_linux(self):
        assert autostart._select_backend("sunos5") is linux_backend


class TestPublicApi:
    @pytest.mark.parametrize("name", ["set_autostart", "is_enabled"])
    def test_export_is_callable(self, name):
        assert callable(getattr(autostart, name))


# --------------------------------------------------------------------------- #
# Windows：启动文件夹
# --------------------------------------------------------------------------- #
class TestWindowsBackend:
    def test_enable_creates_startup_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        assert win_backend.is_enabled() is False
        win_backend.set_autostart(True)
        assert win_backend.is_enabled() is True
        assert win_backend._startup_file().exists()

    def test_disable_removes_startup_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        win_backend.set_autostart(True)
        win_backend.set_autostart(False)
        assert win_backend.is_enabled() is False


# --------------------------------------------------------------------------- #
# macOS：LaunchAgent plist
# --------------------------------------------------------------------------- #
class TestMacosBackend:
    def _mock_launchctl(self, monkeypatch):
        def fake_run(cmd, *a, **k):
            class R:
                returncode = 0
                stdout = ""
                stderr = ""

            return R()

        monkeypatch.setattr(mac_backend.subprocess, "run", fake_run)

    def test_enable_creates_plist(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        self._mock_launchctl(monkeypatch)
        assert mac_backend.is_enabled() is False
        mac_backend.set_autostart(True)
        assert mac_backend.is_enabled() is True
        assert mac_backend._plist_path().exists()

    def test_disable_removes_plist(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        self._mock_launchctl(monkeypatch)
        mac_backend.set_autostart(True)
        mac_backend.set_autostart(False)
        assert mac_backend.is_enabled() is False


# --------------------------------------------------------------------------- #
# Linux：systemd（mock systemctl）
# --------------------------------------------------------------------------- #
class TestLinuxBackend:
    def test_enable_writes_service_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))

        def fake_run(cmd, *a, **k):
            class R:
                returncode = 0
                stdout = ""
                stderr = ""

            return R()

        monkeypatch.setattr(linux_backend.subprocess, "run", fake_run)
        linux_backend.set_autostart(True)
        assert linux_backend._service_file().exists()

    def test_is_enabled_reads_systemctl(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))

        def fake_run(cmd, *a, **k):
            class R:
                returncode = 0
                stdout = "enabled\n"
                stderr = ""

            return R()

        monkeypatch.setattr(linux_backend.subprocess, "run", fake_run)
        assert linux_backend.is_enabled() is True


# --------------------------------------------------------------------------- #
# 打包版(sys.frozen=True)：自启须指向可执行自身，不引用 python/.py/run_gui.sh
# --------------------------------------------------------------------------- #
class TestFrozenPackaging:
    def test_linux_frozen_uses_executable(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", "/opt/voice-input/voice-input", raising=False)
        content = linux_backend._service_unit_content()
        assert "/opt/voice-input/voice-input" in content
        assert "run_gui.sh" not in content

    def test_linux_source_uses_run_gui(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        assert "run_gui.sh" in linux_backend._service_unit_content()

    def test_windows_frozen_uses_executable(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", r"C:\Apps\VoiceInput\voice-input.exe", raising=False)
        cmd = win_backend._launch_command()
        assert "voice-input.exe" in cmd
        assert "voice_input_gui.py" not in cmd
        assert "pythonw" not in cmd

    def test_macos_frozen_uses_executable(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(
            sys, "executable",
            "/Applications/Voice Input.app/Contents/MacOS/voice-input", raising=False)
        plist = mac_backend._plist_content()
        assert "/Contents/MacOS/voice-input" in plist
        assert "voice_input_gui.py" not in plist
