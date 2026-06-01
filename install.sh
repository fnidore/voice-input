#!/usr/bin/env bash
# Voice Input 一键安装脚本
#
# 前置假设:
#   - 操作系统: Ubuntu 22.04 (或同系列)
#   - 已安装 Anaconda / Miniconda (脚本不会自动装 conda)
#   - 有 sudo 权限 (装 apt 依赖时需要)
#   - 显卡: RTX 5060 (Blackwell sm_120) → 使用 PyTorch cu128
#
# 用法:
#   bash install.sh                  # 完整安装
#   bash install.sh --no-model       # 跳过预下载模型 (首次启动时联网拉)
#   bash install.sh --no-autostart   # 不启用开机自启
#   bash install.sh --skip-deps      # 跳过 apt 装系统包 (已装过)
#   bash install.sh --help

set -e

# 颜色
C_R='\033[1;31m'; C_G='\033[1;32m'; C_Y='\033[1;33m'; C_B='\033[1;34m'; C_0='\033[0m'

err()  { echo -e "${C_R}[fatal]${C_0} $*" >&2; }
warn() { echo -e "${C_Y}[warn]${C_0}  $*"; }
info() { echo -e "${C_B}[info]${C_0}  $*"; }
ok()   { echo -e "${C_G}[ok]${C_0}    $*"; }
step() { echo -e "\n${C_B}════ $* ════${C_0}"; }

# 参数解析
DOWNLOAD_MODEL=1
ENABLE_AUTOSTART=1
SKIP_DEPS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --no-model)      DOWNLOAD_MODEL=0 ;;
    --no-autostart)  ENABLE_AUTOSTART=0 ;;
    --skip-deps)     SKIP_DEPS=1 ;;
    --help|-h)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *) err "未知参数: $1"; exit 2 ;;
  esac
  shift
done

# 切到脚本目录
cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"
ENV_NAME="voice_input"

echo "═══════════════════════════════════════════════════════════════"
echo "  Voice Input 一键安装"
echo "  项目目录: $PROJECT_DIR"
echo "  conda 环境: $ENV_NAME"
echo "═══════════════════════════════════════════════════════════════"

# ───────────────────────────────────────────────────────────────────
step "[1/7] 系统检查"
# ───────────────────────────────────────────────────────────────────

# OS
if [ -f /etc/os-release ]; then
  . /etc/os-release
  info "OS: $PRETTY_NAME"
  if [ "$ID" != "ubuntu" ] && [ "$ID_LIKE" != "debian" ] && [[ "$ID_LIKE" != *debian* ]]; then
    warn "非 Ubuntu/Debian 系，apt 步骤可能失败，请根据需要手动处理"
  fi
else
  warn "/etc/os-release 不存在，无法识别 OS"
fi

# X11
if [ "$XDG_SESSION_TYPE" = "wayland" ]; then
  warn "当前是 Wayland 会话，xdotool 无法工作 → 全局快捷键 + 文本注入会失败"
  warn "建议登录界面选择 Ubuntu on Xorg"
elif [ -n "$XDG_SESSION_TYPE" ]; then
  info "Session: $XDG_SESSION_TYPE"
fi

# conda (B1: 假设已装)
if ! command -v conda >/dev/null 2>&1; then
  for c in "$HOME/miniconda3/etc/profile.d/conda.sh" \
           "$HOME/anaconda3/etc/profile.d/conda.sh" \
           "/opt/miniconda3/etc/profile.d/conda.sh"; do
    [ -f "$c" ] && { source "$c"; break; }
  done
fi
if ! command -v conda >/dev/null 2>&1; then
  err "找不到 conda。请先安装 Miniconda: https://docs.conda.io/en/latest/miniconda.html"
  exit 1
fi
info "conda: $(conda --version)"

# 显卡 (软检查)
if command -v nvidia-smi >/dev/null 2>&1; then
  GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
  info "GPU: ${GPU:-(检测失败)}"
else
  warn "找不到 nvidia-smi → 将以 CPU 模式运行 (识别会很慢)"
fi

ok "系统检查通过"

# ───────────────────────────────────────────────────────────────────
step "[2/7] 安装系统依赖 (apt)"
# ───────────────────────────────────────────────────────────────────
if [ $SKIP_DEPS -eq 1 ]; then
  warn "已用 --skip-deps 跳过"
else
  bash "$PROJECT_DIR/install_system_deps.sh"
  ok "系统依赖完成"
fi

# ───────────────────────────────────────────────────────────────────
step "[3/7] 创建 conda 环境 + 安装 Python 依赖"
# ───────────────────────────────────────────────────────────────────
bash "$PROJECT_DIR/setup_env.sh"
ok "Python 环境就绪"

# ───────────────────────────────────────────────────────────────────
step "[4/7] 写入桌面快捷方式 (.desktop)"
# ───────────────────────────────────────────────────────────────────
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/voice-input.desktop"
ICON_PATH="$HOME/.cache/voice-input/icons/voice-input-idle.png"

mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Voice Input
Comment=Push-to-talk voice dictation (SenseVoice)
Exec=/bin/bash $PROJECT_DIR/run_gui.sh
Icon=$ICON_PATH
Terminal=false
Categories=Utility;AudioVideo;
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF
ok "已写入 $DESKTOP_FILE"

# 刷新桌面数据库 (失败不致命)
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

# ───────────────────────────────────────────────────────────────────
step "[5/7] 配置开机自启 (systemd user service)"
# ───────────────────────────────────────────────────────────────────
if [ $ENABLE_AUTOSTART -eq 1 ]; then
  bash "$PROJECT_DIR/install_autostart.sh" enable
  ok "已启用 voice-input.service"
else
  warn "已用 --no-autostart 跳过"
  info "如需启用: bash install_autostart.sh enable"
fi

# ───────────────────────────────────────────────────────────────────
step "[6/7] 预下载 SenseVoice 模型 (~1GB)"
# ───────────────────────────────────────────────────────────────────
if [ $DOWNLOAD_MODEL -eq 1 ]; then
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate "$ENV_NAME"
  info "首次下载需要联网，请耐心等待..."
  python - <<'PY'
from funasr import AutoModel
print("→ 拉取 iic/SenseVoiceSmall ...")
m = AutoModel(model="iic/SenseVoiceSmall", disable_update=True)
print("✓ 模型已缓存到 ~/.cache/modelscope/")
PY
  ok "模型预下载完成"
else
  warn "已用 --no-model 跳过，首次启动时会自动下载"
fi

# ───────────────────────────────────────────────────────────────────
step "[7/7] GNOME AppIndicator 提示"
# ───────────────────────────────────────────────────────────────────
if command -v gnome-shell >/dev/null 2>&1; then
  EXT_ID="ubuntu-appindicators@ubuntu.com"
  ALT_EXT_ID="appindicatorsupport@rgcjonas.gmail.com"
  if gnome-extensions list --enabled 2>/dev/null | grep -qE "($EXT_ID|$ALT_EXT_ID)"; then
    ok "AppIndicator 扩展已启用 → 顶栏托盘可用"
  else
    warn "GNOME 检测到，但 AppIndicator 扩展未启用"
    info "如果托盘图标不显示，运行: bash install_appindicator.sh"
  fi
else
  info "非 GNOME 桌面，跳过 AppIndicator 检查"
fi

# ═══════════════════════════════════════════════════════════════════
echo ""
echo -e "${C_G}═══════════════════════════════════════════════════════════════${C_0}"
echo -e "${C_G}  ✓ Voice Input 安装完成!${C_0}"
echo -e "${C_G}═══════════════════════════════════════════════════════════════${C_0}"
echo ""
echo "🚀 现在就能用:"
echo "   • 手动启动:    bash $PROJECT_DIR/run_gui.sh"
echo "   • 默认快捷键:  按住 F4 说话, 松开识别"
echo "   • 应用菜单里:  搜索 'Voice Input'"
echo ""
echo "🔧 常用命令:"
echo "   • 看日志:      journalctl --user -u voice-input.service -f"
echo "   • 重启服务:    systemctl --user restart voice-input.service"
echo "   • 停止服务:    systemctl --user stop voice-input.service"
echo "   • 完全卸载:    bash $PROJECT_DIR/uninstall.sh"
echo ""
