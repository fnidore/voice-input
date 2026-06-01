#!/usr/bin/env bash
# 启动 Voice Input GUI（用 conda voice_input 环境）
# 这个脚本也是 systemd user service 的 ExecStart

set -e
cd "$(dirname "$0")"

ENV_NAME="voice_input"

# 加载 conda
if ! command -v conda >/dev/null 2>&1; then
  if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
  elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
  else
    echo "[fatal] 找不到 conda，请确保 Anaconda/Miniconda 已安装"
    exit 1
  fi
fi

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${ENV_NAME}"

# 让 systemd 启动时也能连上 X server
export DISPLAY="${DISPLAY:-:1}"
# X11 授权
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

exec python voice_input_gui.py "$@"
