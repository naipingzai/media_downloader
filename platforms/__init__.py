"""平台插件框架 —— 自动发现 + 自注册。

约定 (新增平台只需做两件事):
  1. 在 platforms/<name>/ 下创建包, 在其 __init__.py 中调用:
         PlatformBus.register(<Xxx>Ops())      # 功能接口
         LoginBus.register(<Xxx>LoginManager()) # 扫码登录 (可选)
  2. 在 <Xxx>Ops 中声明 features 并实现 _do_<feature_id>;

框架自动发现 platforms/ 下所有子包并 import (无需在此添加名单)。
adapter 类通过 <Xxx>Ops.adapter_class() 提供, UI 统一经 PlatformBus 调用。
"""
from importlib import import_module
from pathlib import Path

__all__ = ["load_all_platforms", "list_platforms", "get_platform",
           "register_platform"]


def load_all_platforms():
    """扫描 platforms/ 下所有子包并导入 (由包内 __init__ 自注册)。"""
    pkg_dir = Path(__file__).parent
    for sub in sorted(pkg_dir.iterdir()):
        if not sub.is_dir() or sub.name.startswith(("_", ".")):
            continue
        if not (sub / "__init__.py").exists():
            continue
        try:
            import_module(f"platforms.{sub.name}")
        except ImportError:
            pass


def list_platforms() -> list[str]:
    from shared.core.ops import PlatformBus
    return PlatformBus.list_platforms()


def get_platform(name: str):
    """返回平台 adapter 类 (统一走 Ops.adapter_class() 接口)。"""
    from shared.core.ops import PlatformBus
    ops = PlatformBus.get_ops(name)
    if ops and hasattr(ops, "adapter_class"):
        try:
            return ops.adapter_class()
        except Exception:
            pass
    if ops and getattr(ops, "_adapter_class", None):
        return ops._adapter_class
    try:
        mod = import_module(f"platforms.{name}.adapter")
    except ImportError:
        return None
    for attr_name in dir(mod):
        attr = getattr(mod, attr_name)
        if (isinstance(attr, type) and attr.__module__.endswith(f"{name}.adapter")
                and hasattr(attr, "request_detail")):
            return attr
    return None


def register_platform(name: str):
    """向后兼容装饰器 (adapter 类注册已由 PlatformBus 统一管理)。"""
    def decorator(cls):
        return cls
    return decorator
