#!/usr/bin/env bash
# 启动语音输入工具
# 用法:
#   bash run.sh                     # GPU + 右Ctrl + 中英自动
#   bash run.sh --device cpu        # 改用 CPU
#   bash run.sh --hotkey f9         # 改快捷键
#   bash run.sh --language zh       # 强制中文（更快）

set -e
cd "$(dirname "$0")"

ENV_NAME="voice_input"

if ! command -v conda >/dev/null 2>&1; then
  if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
  fi
fi

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${ENV_NAME}"

python main.py "$@"
