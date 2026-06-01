#!/usr/bin/env bash
# 帮你找到当前终端真正能用的粘贴快捷键
# 用法: bash find_paste_key.sh

set -e

echo "==================== 终端粘贴键诊断 ===================="
echo ""

# 1) 看当前终端是什么
echo "[1/3] 当前焦点窗口信息:"
WID=$(xdotool getactivewindow 2>/dev/null || echo "")
if [ -n "$WID" ]; then
  echo "  窗口 ID:   $WID"
  echo "  窗口标题:  $(xdotool getactivewindow getwindowname 2>/dev/null)"
  echo "  WM_CLASS:  $(xprop -id $WID WM_CLASS 2>/dev/null | sed 's/^WM_CLASS(STRING) = //')"
  echo "  进程:      $(xdotool getactivewindow getwindowpid 2>/dev/null | xargs -I{} ps -p {} -o comm= 2>/dev/null)"
fi
echo ""

# 2) 写入剪贴板
TEST_TEXT="测试粘贴_TEST_$(date +%s)"
echo "[2/3] 已把这串测试文字写入 CLIPBOARD 和 PRIMARY:"
echo "      >>> $TEST_TEXT <<<"
echo -n "$TEST_TEXT" | xclip -selection clipboard
echo -n "$TEST_TEXT" | xclip -selection primary
echo ""

# 3) 让用户手动测试
cat <<EOF
[3/3] 请在【这个终端窗口】里手动按下面这些快捷键，看哪个能粘出 "$TEST_TEXT"：

    ① Ctrl + Shift + V      （GNOME Terminal / Konsole / Alacritty / Kitty / WezTerm 默认）
    ② Shift + Insert        （X11 通用，几乎所有终端都支持，最稳）
    ③ Ctrl + Insert         （少数终端用这个）
    ④ 鼠标中键点击          （PRIMARY selection 粘贴）
    ⑤ 鼠标右键 → Paste     （图形菜单粘贴）

如果某个键能粘贴出测试文字，记住它的名字，启动时这样指定：

    bash run.sh --hotkey f4 --terminal-paste-key shift+Insert
    bash run.sh --hotkey f4 --terminal-paste-key ctrl+shift+v
    bash run.sh --hotkey f4 --terminal-paste-key ctrl+Insert

如果【全都不行】，说明你的输入法（fcitx5/ibus）可能拦截了，或者终端禁用了粘贴绑定。
那就用 type 模式（中文可能丢字，但能出字）：

    bash run.sh --hotkey f4 --input-method type

========================================================
EOF
