"""GPU 下载进度信号回归测试：字节数 >2^31 必须无损传递、进度条不溢出。

历史 bug：_gpuProgress 曾声明为 Signal(int)，Linux 运行时 3.5GB 字节数
超 32 位 int 上限，溢出成负数把进度条算崩（显示恒为空）。改 Signal(float) 修复。
"""

import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QObject, Signal  # noqa: E402


class _Probe(QObject):
    # 必须与 SettingsWindow._gpuProgress 同型：float 而非 int
    sig = Signal(float, float, str)

    def __init__(self):
        super().__init__()
        self.received = []
        self.sig.connect(lambda d, t, n: self.received.append((d, t, n)))


def test_large_byte_counts_pass_intact():
    """3.5GB 量级字节数经信号传递后不溢出、不变负。"""
    p = _Probe()
    done, total = 3_400_000_000.0, 3_749_000_000.0  # > 2^31
    p.sig.emit(done, total, "torch.whl")
    assert p.received, "信号未送达"
    rd, rt, _ = p.received[0]
    assert rd == pytest.approx(done) and rt == pytest.approx(total)
    assert rt > 0, "总字节变负——又溢出了"


def test_permille_in_range_for_big_total():
    """大字节数算出的千分比仍落在 0~1000（喂给 QProgressBar 不溢出）。"""
    done, total = 3_400_000_000.0, 3_749_000_000.0
    permille = round(done / max(total, 1.0) * 1000)
    assert 0 <= permille <= 1000


def test_settings_signal_is_float():
    """护栏：SettingsWindow._gpuProgress 的参数类型必须是 float。"""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from gui.settings_window import SettingsWindow
    # Signal 未绑定时是 SignalInstance 描述符；其签名应含 'double'（float 的 C++ 型）
    sig = SettingsWindow._gpuProgress
    assert "double" in str(sig) or "float" in str(sig).lower(), \
        "_gpuProgress 不是 float 信号，大字节数会 32 位溢出"
