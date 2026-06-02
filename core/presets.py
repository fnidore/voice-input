"""模型预设表：用数据描述每个模型的差异，让 Recognizer 读表、零分支。

新增模型 = 往 PRESETS 加一条，Recognizer 不用改（开闭原则）。

已确证（funasr 1.3.9 源码别名表 + 在用验证）：
- iic/SenseVoiceSmall：多语种，吃 language 参数，输出含 <|...|> tag 需清洗。
- paraformer-zh：funasr 别名实际指向 SeACo-Paraformer
  (iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch)，
  纯中文、输出纯文本、支持 hotword 热词增强；别名版自动带 VAD+标点。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

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
}

DEFAULT_PRESET = "sensevoice"


def get_preset(key: str) -> ModelPreset:
    """取预设，未知 key 回退默认。"""
    return PRESETS.get(key, PRESETS[DEFAULT_PRESET])


def model_cache_path(preset: ModelPreset) -> Path:
    """该预设模型在本地的缓存目录（用于 UI 展示；别名也按其字符串拼）。"""
    return MODELSCOPE_CACHE / preset.model_id
