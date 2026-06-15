"""模型预设表：用数据描述每个模型的差异，让 Recognizer 读表、零分支。

新增模型 = 往 PRESETS 加一条，Recognizer 不用改（开闭原则）。

已确证（funasr 1.3.9 源码别名表 + 在用验证）：
- iic/SenseVoiceSmall：多语种，吃 language 参数，输出含 <|...|> tag 需清洗。
- paraformer-zh：funasr 别名实际指向 SeACo-Paraformer
  (iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch)，
  纯中文、输出纯文本、支持 hotword 热词增强；别名版自动带 VAD+标点。
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ModelScope 模型缓存根目录（首次运行自动下载到此）
MODELSCOPE_CACHE = (
    Path(os.environ.get("MODELSCOPE_CACHE", Path.home() / ".cache" / "modelscope"))
    / "hub" / "models"
)

# SenseVoice 输出的 <|zh|><|EMO|> 等 tag；纯文本模型无 tag，清洗也无副作用
_TAG_RE = re.compile(r"<\|[^|]*\|>")


def clean_text(raw: str) -> str:
    """统一输出清洗：去掉 <|...|> tag（对纯文本模型是 no-op）后 strip。"""
    return _TAG_RE.sub("", raw).strip()


@dataclass(frozen=True)
class ModelPreset:
    key: str                    # 内部标识 / config 存储值
    label: str                  # 下拉框显示名
    model_id: str               # ModelScope ID 或 funasr 别名
    desc: str = ""              # UI 说明
    load_kwargs: dict = field(default_factory=dict)   # 传给 AutoModel 的额外参数
    gen_kwargs: dict = field(default_factory=dict)     # generate 固定参数
    accepts_language: bool = False   # 是否吃 language 参数
    accepts_hotword: bool = False    # 是否支持 hotword 热词
    accepts_itn: bool = True         # 是否支持 use_itn


PRESETS: dict[str, ModelPreset] = {
    "sensevoice": ModelPreset(
        key="sensevoice",
        label="SenseVoice Small（多语种·快）",
        model_id="iic/SenseVoiceSmall",
        desc="中粤英日韩多语种 + 情感事件，速度快。支持「识别语言」选择。",
        load_kwargs={"vad_model": "fsmn-vad",
                     "vad_kwargs": {"max_single_segment_time": 30000}},
        gen_kwargs={"batch_size_s": 60},
        accepts_language=True,
        accepts_hotword=False,
        accepts_itn=True,
    ),
    "paraformer_zh": ModelPreset(
        key="paraformer_zh",
        label="Paraformer 中文（热词增强·SeACo）",
        model_id="paraformer-zh",   # funasr 别名 → SeACo-Paraformer
        desc="纯中文，标点干净，热词增强强（专业术语/人名更准）。不支持多语种切换。",
        load_kwargs={},             # 别名版自动带 VAD + 标点
        gen_kwargs={"batch_size_s": 60},
        accepts_language=False,
        accepts_hotword=True,
        accepts_itn=True,
    ),
    # 自定义模型：model_id 运行时由 config.custom_model_path 提供（ModelScope ID 或本地目录）
    "custom": ModelPreset(
        key="custom",
        label="📁 自定义模型（ID 或本地路径）",
        model_id="",  # 占位，实际取 config.custom_model_path
        desc="填 ModelScope 模型 ID（自动下载）或本地模型目录路径。按通用方式调用，"
             "多语种/热词可能不生效。",
        load_kwargs={},
        gen_kwargs={"batch_size_s": 60},
        accepts_language=False,
        accepts_hotword=False,
        accepts_itn=True,
    ),
}

DEFAULT_PRESET = "sensevoice"
CUSTOM_PRESET = "custom"


def get_preset(key: str) -> ModelPreset:
    """取预设，未知 key 回退默认。"""
    return PRESETS.get(key, PRESETS[DEFAULT_PRESET])


def model_cache_path(preset: ModelPreset) -> Path:
    """该预设模型在本地的缓存目录（用于 UI 展示；别名也按其字符串拼）。"""
    return MODELSCOPE_CACHE / preset.model_id


# AutoModel 会按需 build 的子模型 key（仅显式传入时才加载，funasr 不自动注入）
_SUB_MODEL_KEYS = ("vad_model", "punc_model", "spk_model")


def _resolve_alias(model_id: str) -> str:
    """把 funasr 别名（如 fsmn-vad / paraformer-zh）解析成真实 ModelScope ID。

    懒加载 funasr 别名表；funasr 不可用或无此别名时原样返回。
    """
    try:
        from funasr.download.name_maps_from_hub import name_maps_ms
        return name_maps_ms.get(model_id, model_id)
    except Exception as e:  # funasr 未装 / 别名表改名都回退原 ID（最坏只是误判联网）
        logger.debug("funasr 别名表不可用，按原 ID 处理: %s", e)
        return model_id


def resolve_local_model_dir(model_id_or_path: str) -> Path | None:
    """把 ModelScope ID / funasr 别名 / 本地路径 解析成「已存在」的本地目录。

    本地无缓存（需联网下载）时返回 None。
    """
    if not model_id_or_path or not model_id_or_path.strip():
        return None
    # 1) 用户直接填的本地目录
    p = Path(model_id_or_path).expanduser()
    if p.is_dir():
        return p
    # 2) 原 ID 直接按 cache 根目录拼（真实 ID 这步即命中，免触发 funasr import）
    cache_dir = MODELSCOPE_CACHE / model_id_or_path
    if cache_dir.is_dir():
        return cache_dir
    # 3) 仍未命中才解析别名（如 fsmn-vad / paraformer-zh）再拼一次
    real_id = _resolve_alias(model_id_or_path)
    if real_id != model_id_or_path:
        cache_dir = MODELSCOPE_CACHE / real_id
        if cache_dir.is_dir():
            return cache_dir
    return None


def plan_offline_load(model_id: str, load_kwargs: dict) -> tuple[bool, dict]:
    """规划离线加载：主模型 + 子模型(vad/punc/spk)全部本地已缓存才离线。

    返回 (能否离线, {"model": 主模型本地路径, "load_kwargs": {子模型: 本地路径}})。
    任一缺失返回 (False, {})，由调用方维持在线下载。不改动传入的 load_kwargs。
    """
    main_dir = resolve_local_model_dir(model_id)
    if main_dir is None:
        return False, {}
    resolved_subs: dict = {}
    for key in _SUB_MODEL_KEYS:
        sub_id = load_kwargs.get(key)
        if not sub_id:
            continue
        sub_dir = resolve_local_model_dir(sub_id)
        if sub_dir is None:
            return False, {}
        resolved_subs[key] = str(sub_dir)
    return True, {"model": str(main_dir), "load_kwargs": resolved_subs}
