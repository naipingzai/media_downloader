"""kuaishou 平台插件 —— 自注册到框架 (功能 + 扫码登录)。"""
from shared.core.ops import PlatformBus
from .adapter import KuaishouAdapter
from .ops import KuaishouOps

PlatformBus.register(KuaishouOps())

try:
    from shared.core.login import LoginBus
    from .login import KuaishouLoginManager
    LoginBus.register(KuaishouLoginManager())
except ImportError:
    pass

__all__ = ["KuaishouAdapter", "KuaishouOps"]
