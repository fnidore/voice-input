"""跨平台单例锁：绑定本地回环 TCP 端口。

早先 GUI 入口用 abstract Unix domain socket 做单例（``bind("\\0...")``），
只在 Linux 可用——Windows 没有 ``socket.AF_UNIX`` 会直接报 AttributeError，
macOS 虽有 AF_UNIX 但不支持 ``\\0`` 抽象命名空间。这里改用 ``127.0.0.1`` TCP
端口绑定，三平台行为一致；独立成模块（不依赖 PySide6）便于单元测试。
"""

from __future__ import annotations

import socket

# 单例锁固定占用的本地回环端口（选少见的高位端口，降低与其它程序冲突概率）
SINGLETON_PORT = 47923


def acquire_single_instance_lock(port: int = SINGLETON_PORT) -> socket.socket | None:
    """绑定 ``127.0.0.1:port`` 实现跨平台单例，端口被占用返回 ``None``。

    返回的 socket 必须由调用方持有引用；进程退出时端口自动释放，
    下一次启动即可重新获取。

    不设 ``SO_REUSEADDR``：单例场景要的就是"第二个进程绑不上"。
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        sock.listen(1)
        return sock
    except OSError:
        sock.close()
        return None
