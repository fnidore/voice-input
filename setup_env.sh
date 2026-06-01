#!/usr/bin/env bash
# 创建独立的 conda 环境（Python 3.10），并安装 PyTorch + FunASR
# 用法: bash setup_env.sh

set -e

ENV_NAME="voice_input"
PY_VER="3.10"

# 找到 conda
if ! command -v conda >/dev/null 2>&1; then
  # 尝试加载 anaconda
  if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
  else
    echo "[fatal] 找不到 conda，请先安装 Anaconda/Miniconda"
    exit 1
  fi
fi

# 创建环境（已存在则跳过）
if conda env list | grep -qE "^${ENV_NAME}\s"; then
  echo "==> conda 环境 ${ENV_NAME} 已存在，跳过创建"
else
  echo "==> 创建 conda 环境 ${ENV_NAME} (Python ${PY_VER}) ..."
  conda create -n "${ENV_NAME}" "python=${PY_VER}" -y
fi

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${ENV_NAME}"

echo "==> 升级 pip ..."
python -m pip install --upgrade pip

echo "==> 安装 PyTorch (CUDA 12.8, 支持 RTX 5060 Blackwell sm_120) ..."
# Blackwell (sm_120) 需要 PyTorch 2.7+ / cu128
pip install --index-url https://download.pytorch.org/whl/cu128 \
  torch torchvision torchaudio

echo "==> 安装 FunASR + 录音/快捷键依赖 ..."
pip install -r requirements.txt

echo "==> 验证 PyTorch CUDA 是否可用 ..."
python - <<'PY'
import torch
print(f"PyTorch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print(f"Capability: {torch.cuda.get_device_capability(0)}")
PY

echo ""
echo "==> 完成！下次启动直接运行: bash run.sh"
