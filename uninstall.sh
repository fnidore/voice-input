#!/usr/bin/env bash
# Voice Input 卸载脚本
#
# 默认行为: dry-run, 先列出会删什么, 用户输 yes 才真删
#
# 用法:
#   bash uninstall.sh                  # 标准卸载 (保留 conda 环境 + 模型缓存)
#   bash uninstall.sh --keep-data      # 保留 ~/.config + ~/.local/share 数据
#   bash uninstall.sh --purge          # 全删 (含 conda 环境 + 模型缓存 + 源码 pyc)
#   bash uninstall.sh --yes            # 跳过确认
#   bash uninstall.sh --dry-run        # 只列出, 不删除 (显式开关, 默认本来就先列再问)

set -e

C_R='\033[1;31m'; C_G='\033[1;32m'; C_Y='\033[1;33m'; C_B='\033[1;34m'; C_0='\033[0m'

err()  { echo -e "${C_R}[fatal]${C_0} $*" >&2; }
warn() { echo -e "${C_Y}[warn]${C_0}  $*"; }
info() { echo -e "${C_B}[info]${C_0}  $*"; }
ok()   { echo -e "${C_G}[ok]${C_0}    $*"; }
step() { echo -e "\n${C_B}════ $* ════${C_0}"; }

# 参数
KEEP_DATA=0
PURGE=0
ASSUME_YES=0
DRY_ONLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --keep-data) KEEP_DATA=1 ;;
    --purge)     PURGE=1 ;;
    --yes|-y)    ASSUME_YES=1 ;;
    --dry-run)   DRY_ONLY=1 ;;
    --help|-h)
      sed -n '2,15p' "$0"
      exit 0
      ;;
    *) err "未知参数: $1"; exit 2 ;;
  esac
  shift
done

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"
ENV_NAME="voice_input"

# ───────────────────────────────────────────────────────────────────
# 收集待删项 (用数组分类, 便于后续 dry-run 展示 + 实际删除)
# ───────────────────────────────────────────────────────────────────
declare -a SERVICE_ITEMS  # systemd unit + .desktop
declare -a CONFIG_ITEMS   # 配置 / 历史 / 日志 / 图标缓存
declare -a HEAVY_ITEMS    # conda env + 模型缓存
declare -a SRC_PYC_ITEMS  # 项目内 __pycache__

# 1) systemd service + .desktop
SVC_FILE="$HOME/.config/systemd/user/voice-input.service"
DESKTOP_FILE="$HOME/.local/share/applications/voice-input.desktop"
[ -f "$SVC_FILE" ]     && SERVICE_ITEMS+=("$SVC_FILE")
[ -f "$DESKTOP_FILE" ] && SERVICE_ITEMS+=("$DESKTOP_FILE")

# 2) 配置 + 数据 + 缓存 + QSettings
if [ $KEEP_DATA -eq 0 ]; then
  for p in \
    "$HOME/.config/voice-input" \
    "$HOME/.local/share/voice-input" \
    "$HOME/.cache/voice-input" \
    "$HOME/.config/VoiceInput"; do
    [ -e "$p" ] && CONFIG_ITEMS+=("$p")
  done
fi

# 3) conda 环境 + 模型缓存 (重量级, 默认保留, 需 --purge 才删)
if [ $PURGE -eq 1 ]; then
  if command -v conda >/dev/null 2>&1 || [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ] \
                                       || [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    CONDA_BASE=$(conda info --base 2>/dev/null || \
                 ( [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ] && echo "$HOME/miniconda3" ) || \
                 echo "$HOME/anaconda3")
    ENV_PATH="$CONDA_BASE/envs/$ENV_NAME"
    [ -d "$ENV_PATH" ] && HEAVY_ITEMS+=("$ENV_PATH  (conda env, ~3GB)")
  fi
  # modelscope 模型缓存
  if [ -d "$HOME/.cache/modelscope" ]; then
    HEAVY_ITEMS+=("$HOME/.cache/modelscope/hub/iic/SenseVoiceSmall*  (模型, ~1GB)")
  fi
  # 源码内 __pycache__
  while IFS= read -r p; do
    SRC_PYC_ITEMS+=("$p")
  done < <(find "$PROJECT_DIR" -type d -name __pycache__ 2>/dev/null)
fi

# ───────────────────────────────────────────────────────────────────
# 展示
# ───────────────────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════════"
echo "  Voice Input 卸载预览"
echo "  项目: $PROJECT_DIR"
echo "  模式: $([ $KEEP_DATA -eq 1 ] && echo '保留数据' || echo '标准')$([ $PURGE -eq 1 ] && echo ' + 完全清理')"
echo "═══════════════════════════════════════════════════════════════"

show_block() {
  local title="$1"; shift
  local items=("$@")
  if [ ${#items[@]} -eq 0 ]; then
    echo -e "  ${C_Y}∘ $title: 无${C_0}"
  else
    echo -e "  ${C_R}● $title:${C_0}"
    for item in "${items[@]}"; do
      echo "      - $item"
    done
  fi
}

show_block "[A] systemd 服务 + 桌面快捷方式" "${SERVICE_ITEMS[@]}"
show_block "[B] 配置 / 历史 / 日志 / 图标缓存" "${CONFIG_ITEMS[@]}"
show_block "[C] 重量级 (--purge 时才删)" "${HEAVY_ITEMS[@]}"
show_block "[D] 源码内 __pycache__" "${SRC_PYC_ITEMS[@]}"

echo ""
echo -e "  ${C_B}⚠ 项目源码本身 (${PROJECT_DIR}) 不会删除, 需要手动 rm -rf${C_0}"
echo ""

if [ $DRY_ONLY -eq 1 ]; then
  ok "--dry-run 模式, 退出"
  exit 0
fi

# 没东西可删
total=$(( ${#SERVICE_ITEMS[@]} + ${#CONFIG_ITEMS[@]} + ${#HEAVY_ITEMS[@]} + ${#SRC_PYC_ITEMS[@]} ))
if [ $total -eq 0 ]; then
  ok "没有需要删除的内容, 系统已干净"
  exit 0
fi

# 确认
if [ $ASSUME_YES -eq 0 ]; then
  echo -ne "${C_Y}确认执行卸载? 输入 ${C_R}yes${C_Y} 继续, 其他任意键放弃: ${C_0}"
  read -r answer
  if [ "$answer" != "yes" ]; then
    info "已取消"
    exit 0
  fi
fi

# ───────────────────────────────────────────────────────────────────
# 执行
# ───────────────────────────────────────────────────────────────────
step "[1/4] 停止 + 禁用 systemd 服务"
if [ -f "$SVC_FILE" ]; then
  systemctl --user stop voice-input.service 2>/dev/null || true
  systemctl --user disable voice-input.service 2>/dev/null || true
  rm -f "$SVC_FILE"
  systemctl --user daemon-reload 2>/dev/null || true
  ok "已停止并删除 voice-input.service"
fi
# 顺手把跑着的进程也干掉 (前台 / 浮窗模式)
if pgrep -f "voice_input_gui.py" >/dev/null 2>&1; then
  pkill -f "voice_input_gui.py" 2>/dev/null || true
  ok "已杀掉残留的 voice_input_gui.py 进程"
fi

step "[2/4] 删除 .desktop"
[ -f "$DESKTOP_FILE" ] && rm -f "$DESKTOP_FILE" && ok "已删除 $DESKTOP_FILE"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

step "[3/4] 删除配置 / 历史 / 日志 / 图标缓存"
if [ $KEEP_DATA -eq 1 ]; then
  warn "已用 --keep-data 跳过"
else
  for p in "${CONFIG_ITEMS[@]}"; do
    rm -rf "$p" && ok "已删除 $p"
  done
fi

step "[4/4] 重量级清理"
if [ $PURGE -eq 1 ]; then
  # conda env
  if command -v conda >/dev/null 2>&1; then
    : # already loaded
  elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
  elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
  fi
  if command -v conda >/dev/null 2>&1 && conda env list 2>/dev/null | grep -qE "^${ENV_NAME}\s"; then
    info "删除 conda 环境 $ENV_NAME (这一步比较慢)..."
    conda env remove -n "$ENV_NAME" -y
    ok "conda 环境 $ENV_NAME 已删除"
  fi
  # 模型
  if [ -d "$HOME/.cache/modelscope/hub" ]; then
    find "$HOME/.cache/modelscope/hub" -maxdepth 4 -type d -iname "SenseVoiceSmall*" \
      -exec rm -rf {} + 2>/dev/null || true
    ok "SenseVoice 模型缓存已清理"
  fi
  # 源码内 __pycache__
  for p in "${SRC_PYC_ITEMS[@]}"; do
    rm -rf "$p"
  done
  [ ${#SRC_PYC_ITEMS[@]} -gt 0 ] && ok "已清理 ${#SRC_PYC_ITEMS[@]} 个 __pycache__"
else
  warn "未指定 --purge, conda 环境和模型缓存已保留"
fi

# ═══════════════════════════════════════════════════════════════════
echo ""
echo -e "${C_G}═══════════════════════════════════════════════════════════════${C_0}"
echo -e "${C_G}  ✓ Voice Input 卸载完成${C_0}"
echo -e "${C_G}═══════════════════════════════════════════════════════════════${C_0}"
echo ""
if [ $PURGE -eq 0 ]; then
  echo "💡 残留项 (如想完全清理, 重新跑 bash uninstall.sh --purge):"
  echo "   • conda 环境:  voice_input  (~3GB)"
  echo "   • 模型缓存:    ~/.cache/modelscope/hub/.../SenseVoiceSmall*"
fi
echo "💡 源码目录需手动删除 (如不再需要):"
echo "   rm -rf $PROJECT_DIR"
echo ""
