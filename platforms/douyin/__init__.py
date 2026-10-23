"""douyin 平台插件 —— 自注册到框架 (功能 + 扫码登录)。"""
from shared.core.ops import PlatformBus
from .adapter import DouyinAdapter
from .ops import DouyinOps

PlatformBus.register(DouyinOps())

try:
    from shared.core.login import LoginBus
    from .login import DouyinLoginManager
    LoginBus.register(DouyinLoginManager())
except ImportError:
    pass

__all__ = ["DouyinAdapter", "DouyinOps"]
