"""
键位探测器：按任意键，看 pynput 实际收到的键名
用法: python keytest.py
"""

from pynput import keyboard


def on_press(key):
    try:
        # 特殊键: keyboard.Key.xxx
        name = key.name
        kind = "special"
        cfg_name = name
    except AttributeError:
        # 字符键: KeyCode(char='a', vk=...)
        kind = "char"
        name = repr(key.char) if getattr(key, "char", None) else f"vk={key.vk}"
        cfg_name = key.char if getattr(key, "char", None) else f"vk:{key.vk}"

    vk = getattr(key, "vk", None)
    print(f"  ↓ 按下 | 类型={kind:7s} | 名称={name:20s} | vk={vk}  → 配置写: --hotkey {cfg_name}")


def on_release(key):
    if key == keyboard.Key.esc:
        print("\n[exit] Esc 退出")
        return False


print("=" * 60)
print("键位探测器：按你想用的按键看实际键名，按 Esc 退出")
print("=" * 60)
with keyboard.Listener(on_press=on_press, on_release=on_release) as L:
    L.join()
