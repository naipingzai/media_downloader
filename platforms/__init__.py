"""平台注册 —— 各平台在 __init__.py 中 self-register。"""
from importlib import import_module


def load_all_platforms():
    for name in ("douyin", "kuaishou", "xiaohongshu"):
        try:
            import_module(f"platforms.{name}")
        except ImportError:
            pass


# 向后兼容
def register_platform(name: str):
    def decorator(cls):
        return cls
    return decorator


def list_platforms():
    from shared.core.ops import PlatformBus
    return PlatformBus.list_platforms()


def get_platform(name: str):
    return None
