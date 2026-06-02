"""模型预设表 + Recognizer 参数透传 / 设备回退测试（mock，不需真模型）。"""

from __future__ import annotations

import sys
import types

import numpy as np

from core.presets import DEFAULT_PRESET, PRESETS, clean_text, get_preset
from core.recognizer import Recognizer, resolve_device


class _FakeModel:
    """假模型：记录 generate 收到的 kwargs，返回带 tag 的结果。"""

    def __init__(self):
        self.last_kwargs = None

    def generate(self, **kwargs):
        self.last_kwargs = kwargs
        return [{"text": "<|zh|><|NEUTRAL|>你好世界"}]


# ---------- presets ----------

def test_presets_has_two_and_default_valid():
    assert "sensevoice" in PRESETS
    assert "paraformer_zh" in PRESETS
    assert DEFAULT_PRESET in PRESETS


def test_get_preset_unknown_falls_back_to_default():
    assert get_preset("nonexistent").key == DEFAULT_PRESET


def test_clean_text_strips_sensevoice_tags():
    assert clean_text("<|zh|><|NEUTRAL|><|Speech|>你好") == "你好"
    # 纯文本无 tag 时是 no-op
    assert clean_text("  你好，世界  ") == "你好，世界"


# ---------- recognizer 参数透传 ----------

def _recognize_with(preset_key: str, hotwords: str = "涛涛鱼"):
    r = Recognizer(preset_key=preset_key, device="cpu")
    fake = _FakeModel()
    r.model = fake  # 跳过真实 load
    result = r.recognize(np.zeros(16000, dtype=np.float32), language="zh", hotwords=hotwords)
    return fake.last_kwargs, result


def test_sensevoice_passes_language_not_hotword():
    kw, result = _recognize_with("sensevoice")
    assert kw["language"] == "zh"        # 多语种模型吃 language
    assert "hotword" not in kw           # accepts_hotword=False
    assert kw["use_itn"] is True
    assert result.text == "你好世界"      # tag 已清洗


def test_paraformer_passes_hotword_not_language():
    kw, _ = _recognize_with("paraformer_zh")
    assert "language" not in kw          # 纯中文模型不传 language
    assert kw["hotword"] == "涛涛鱼"      # accepts_hotword=True


def test_empty_hotword_not_passed_even_if_supported():
    kw, _ = _recognize_with("paraformer_zh", hotwords="   ")
    assert "hotword" not in kw


# ---------- 设备回退 ----------

def test_resolve_device_cpu_stays_cpu():
    assert resolve_device("cpu") == "cpu"


def test_resolve_device_cuda_falls_back_when_unavailable(monkeypatch):
    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    assert resolve_device("cuda:0") == "cpu"


def test_resolve_device_cuda_kept_when_available(monkeypatch):
    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(is_available=lambda: True)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    assert resolve_device("cuda:0") == "cuda:0"
