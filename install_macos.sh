#!/usr/bin/env bash
# Voice Input - macOS 一键安装
set -euo pipefail

echo "===== Voice Input macOS 安装 ====="

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. 检查 python3
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ 未找到 python3，请先安装 Python 3.10+（推荐 https://www.python.org 或 brew install python@3.10）"
    exit 1
fi
echo "检测到 $(python3 --version)"

# 2. 创建虚拟环境
VENV="$PROJ/.venv"
if [ ! -d "$VENV" ]; then
    echo "创建虚拟环境 .venv ..."
    python3 -m venv "$VENV"
fi
PY="$VENV/bin/python"

# 3. 升级 pip + 安装依赖
echo "安装依赖 (requirements.txt) ..."
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r "$PROJ/requirements.txt"

# 4. 安装 PyTorch（CPU 版；Apple Silicon 会自动支持 MPS 加速）
echo "安装 PyTorch ..."
"$PY" -m pip install torch

# 5. 完成提示
cat <<EOF

✅ 安装完成!
启动命令:
  "$PY" "$PROJ/voice_input_gui.py"

⚠️  首次运行需在「系统设置 → 隐私与安全性 → 辅助功能」中授权本程序，
    pynput 才能模拟全局快捷键与粘贴。
ℹ️  首次运行会自动下载 ~1GB SenseVoice 模型，请耐心等待。
EOF
