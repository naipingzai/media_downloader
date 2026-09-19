from shared.core.ops import PlatformBus
from .adapter import DouyinAdapter
from .ops import DouyinOps

PlatformBus.register(DouyinOps())
__all__ = ["DouyinAdapter", "DouyinOps"]
