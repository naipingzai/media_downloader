"""xiaohongshu 平台插件 —— 自注册到框架 (功能 + 扫码登录)。"""
from shared.core.ops import PlatformBus
from .adapter import XiaohongshuAdapter
from .ops import XiaohongshuOps

PlatformBus.register(XiaohongshuOps())

try:
    from shared.core.login import LoginBus
    from .login import XiaohongshuLoginManager
    LoginBus.register(XiaohongshuLoginManager())
except ImportError:
    pass

__all__ = ["XiaohongshuAdapter", "XiaohongshuOps"]
