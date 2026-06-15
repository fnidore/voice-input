"""智能离线加载测试：本地已缓存 → 解析成本地路径不联网；缺失 → 维持在线下载。

全部 mock 缓存目录，不依赖真模型 / 真网络 / funasr。
"""

from __future__ import annotations

import sys
import types

import core.presets as presets
from core.presets import plan_offline_load, resolve_local_model_dir
from core.recognizer import Recognizer


# ---------- resolve_local_model_dir ----------

def test_resolve_returns_none_for_empty():
    assert resolve_local_model_dir("") is None
    assert resolve_local_model_dir("   ") is None


def test_resolve_user_local_dir_directly(tmp_path):
    d = tmp_path / "my_model"
    d.mkdir()
    assert resolve_local_model_dir(str(d)) == d


def test_resolve_real_id_via_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(presets, "MODELSCOPE_CACHE", tmp_path)
    (tmp_path / "iic" / "SenseVoiceSmall").mkdir(parents=True)
    got = resolve_local_model_dir("iic/SenseVoiceSmall")
    assert got == tmp_path / "iic" / "SenseVoiceSmall"


def test_resolve_alias_via_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(presets, "MODELSCOPE_CACHE", tmp_path)
    # 别名 fsmn-vad → 真实 ID（mock 别名表，免依赖 funasr）
    monkeypatch.setattr(
        presets, "_resolve_alias",
        lambda mid: {"fsmn-vad": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"}.get(mid, mid),
    )
    real = tmp_path / "iic" / "speech_fsmn_vad_zh-cn-16k-common-pytorch"
    real.mkdir(parents=True)
    assert resolve_local_model_dir("fsmn-vad") == real


def test_resolve_returns_none_when_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(presets, "MODELSCOPE_CACHE", tmp_path)
    monkeypatch.setattr(presets, "_resolve_alias", lambda mid: mid)
    assert resolve_local_model_dir("iic/NotDownloaded") is None


# ---------- plan_offline_load ----------

def test_plan_offline_when_main_and_sub_all_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(presets, "MODELSCOPE_CACHE", tmp_path)
    monkeypatch.setattr(
        presets, "_resolve_alias",
        lambda mid: {"fsmn-vad": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"}.get(mid, mid),
    )
    main = tmp_path / "iic" / "SenseVoiceSmall"
    main.mkdir(parents=True)
    vad = tmp_path / "iic" / "speech_fsmn_vad_zh-cn-16k-common-pytorch"
    vad.mkdir(parents=True)

    ok, resolved = plan_offline_load("iic/SenseVoiceSmall", {"vad_model": "fsmn-vad"})
    assert ok is True
    assert resolved["model"] == str(main)
    assert resolved["load_kwargs"]["vad_model"] == str(vad)


def test_plan_online_when_main_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(presets, "MODELSCOPE_CACHE", tmp_path)
    monkeypatch.setattr(presets, "_resolve_alias", lambda mid: mid)
    ok, resolved = plan_offline_load("iic/SenseVoiceSmall", {})
    assert ok is False
    assert resolved == {}


def test_plan_online_when_sub_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(presets, "MODELSCOPE_CACHE", tmp_path)
    monkeypatch.setattr(presets, "_resolve_alias", lambda mid: mid)
    (tmp_path / "iic" / "SenseVoiceSmall").mkdir(parents=True)  # 主模型在，VAD 缺
    ok, resolved = plan_offline_load("iic/SenseVoiceSmall", {"vad_model": "fsmn-vad"})
    assert ok is False
    assert resolved == {}


def test_plan_offline_no_sub_models(tmp_path, monkeypatch):
    """paraformer_zh: load_kwargs 为空，只解析主模型。"""
    monkeypatch.setattr(presets, "MODELSCOPE_CACHE", tmp_path)
    monkeypatch.setattr(
        presets, "_resolve_alias",
        lambda mid: {"paraformer-zh":
                     "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"}.get(mid, mid),
    )
    main = tmp_path / "iic" / "speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    main.mkdir(parents=True)
    ok, resolved = plan_offline_load("paraformer-zh", {})
    assert ok is True
    assert resolved["model"] == str(main)
    assert resolved["load_kwargs"] == {}


def test_plan_does_not_mutate_input_load_kwargs(tmp_path, monkeypatch):
    """不可变：输入的 load_kwargs 不被改动。"""
    monkeypatch.setattr(presets, "MODELSCOPE_CACHE", tmp_path)
    monkeypatch.setattr(presets, "_resolve_alias", lambda mid: mid)
    (tmp_path / "iic" / "SenseVoiceSmall").mkdir(parents=True)
    (tmp_path / "fsmn-vad").mkdir()
    original = {"vad_model": "fsmn-vad", "vad_kwargs": {"x": 1}}
    plan_offline_load("iic/SenseVoiceSmall", original)
    assert original == {"vad_model": "fsmn-vad", "vad_kwargs": {"x": 1}}


# ---------- recognizer.load() 接线 ----------

def _install_fake_funasr(monkeypatch):
    """注入假 funasr.AutoModel，记录构造参数，返回 captured dict。"""
    captured = {}

    class _FakeAutoModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_mod = types.ModuleType("funasr")
    fake_mod.AutoModel = _FakeAutoModel
    monkeypatch.setitem(sys.modules, "funasr", fake_mod)
    return captured


def test_load_offline_passes_local_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(presets, "MODELSCOPE_CACHE", tmp_path)
    monkeypatch.setattr(
        presets, "_resolve_alias",
        lambda mid: {"fsmn-vad": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"}.get(mid, mid),
    )
    main = tmp_path / "iic" / "SenseVoiceSmall"
    main.mkdir(parents=True)
    vad = tmp_path / "iic" / "speech_fsmn_vad_zh-cn-16k-common-pytorch"
    vad.mkdir(parents=True)
    captured = _install_fake_funasr(monkeypatch)

    r = Recognizer(preset_key="sensevoice", device="cpu")
    r.load()

    assert captured["model"] == str(main)              # 主模型 → 本地路径
    assert captured["vad_model"] == str(vad)           # VAD → 本地路径
    assert captured["disable_update"] is True


def test_load_online_passes_id_when_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(presets, "MODELSCOPE_CACHE", tmp_path)  # 空 cache
    monkeypatch.setattr(presets, "_resolve_alias", lambda mid: mid)
    captured = _install_fake_funasr(monkeypatch)

    r = Recognizer(preset_key="sensevoice", device="cpu")
    r.load()

    assert captured["model"] == "iic/SenseVoiceSmall"  # 维持 ID，首次联网下载
    assert captured["vad_model"] == "fsmn-vad"         # 子模型也维持别名
