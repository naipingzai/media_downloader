"""平台注册 —— 各平台在 __init__.py 中 self-register。"""
from importlib import import_module


def load_all_platforms():
    for name in ("douyin", "kuaishou", "xiaohongshu", "bilibili"):
        try:
            import_module(f"platforms.{name}")
        except ImportError:
            pass
    # 注册登录管理器到 LoginBus
    _register_login_managers()


def _register_login_managers():
    """动态注册各平台的登录管理器。"""
    from shared.core.login import LoginBus
    _map = {
        "douyin": ("platforms.douyin.login", "DouyinLoginManager"),
        "kuaishou": ("platforms.kuaishou.login", "KuaishouLoginManager"),
        "xiaohongshu": ("platforms.xiaohongshu.login", "XiaohongshuLoginManager"),
        "bilibili": ("platforms.bilibili.login", "BilibiliLoginManager"),
    }
    for pid, (mod_path, cls_name) in _map.items():
        try:
            mod = import_module(mod_path)
            cls = getattr(mod, cls_name, None)
            if cls:
                LoginBus.register(cls())
        except Exception:
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
    """返回平台的 adapter 类（向后兼容）。"""
    from shared.core.ops import PlatformBus
    ops = PlatformBus.get_ops(name)
    if ops and hasattr(ops, '_adapter_class'):
        return ops._adapter_class
    # 尝试直接导入
    try:
        mod = import_module(f"platforms.{name}.adapter")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and hasattr(attr, 'request_detail'):
                return attr
    except ImportError:
        pass
    return None
