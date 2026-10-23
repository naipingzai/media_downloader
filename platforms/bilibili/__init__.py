"""bilibili 平台插件 —— 自注册到框架 (功能 + 扫码登录)。"""
from shared.core.ops import PlatformBus
from .adapter import BilibiliAdapter
from .ops import BilibiliOps

PlatformBus.register(BilibiliOps())

try:
    from shared.core.login import LoginBus
    from .login import BilibiliLoginManager
    LoginBus.register(BilibiliLoginManager())
except ImportError:
    pass

__all__ = ["BilibiliAdapter", "BilibiliOps"]
