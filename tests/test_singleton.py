"""core.singleton 跨平台单例锁测试（三平台 CI 均可跑，TCP loopback 通用）。"""

from __future__ import annotations

import socket

from core.singleton import acquire_single_instance_lock

# 测试专用端口，避开真实 SINGLETON_PORT(47923)，防止与本机运行的实例串扰
_TEST_PORT = 49321


def test_first_acquire_succeeds():
    lock = acquire_single_instance_lock(_TEST_PORT)
    try:
        assert lock is not None
        assert isinstance(lock, socket.socket)
    finally:
        if lock is not None:
            lock.close()


def test_second_acquire_returns_none_while_held():
    first = acquire_single_instance_lock(_TEST_PORT)
    try:
        assert first is not None
        # 端口被首个实例占用，第二个实例应拿不到锁
        second = acquire_single_instance_lock(_TEST_PORT)
        assert second is None
    finally:
        if first is not None:
            first.close()


def test_reacquire_after_release():
    first = acquire_single_instance_lock(_TEST_PORT)
    assert first is not None
    first.close()
    # 首个实例退出释放端口后，应能重新获取
    second = acquire_single_instance_lock(_TEST_PORT)
    try:
        assert second is not None
    finally:
        if second is not None:
            second.close()
