# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 — Voice Input（Linux, CPU 版 torch, 不含模型权重）。

打包:  pyinstaller voice_input.spec
产物:  dist/voice-input/   (onedir)

模型权重不打进包，首次运行从 ModelScope 下载到 ~/.cache/modelscope。
"""

import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = []
binaries = []
hiddenimports = []

# 修复 conda 环境下 pyexpat 的符号不匹配：系统旧版 libexpat 缺
# XML_SetAllocTrackerActivationThreshold，conda Python 的 pyexpat 需要它。
# 显式打包 conda 的 libexpat.so.1 并 insert(0) 以在去重中优先保留。
_conda_prefix = os.environ.get("CONDA_PREFIX", "")
if _conda_prefix:
    _libexpat = os.path.join(_conda_prefix, "lib", "libexpat.so.1")
    if os.path.exists(_libexpat):
        binaries.insert(0, (_libexpat, "."))

# funasr / modelscope 动态导入与数据文件极多，全量收集
for pkg in ("funasr", "modelscope", "sounddevice", "pynput", "pyperclip"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # 某个包收集失败不致命，打印后继续
        print(f"[spec] collect_all({pkg}) skipped: {exc}")

hiddenimports += collect_submodules("funasr")
hiddenimports += ["sounddevice", "numpy", "core", "gui"]

a = Analysis(
    ["voice_input_gui.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # 排除明显用不到的重型可选依赖，给体积瘦身
    excludes=["tkinter", "matplotlib", "tensorflow", "jax", "tensorboard"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="voice-input",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="voice-input",
)
