from shared.core.ops import PlatformBus
from .adapter import XiaohongshuAdapter
from .ops import XiaohongshuOps

PlatformBus.register(XiaohongshuOps())
__all__ = ["XiaohongshuAdapter", "XiaohongshuOps"]
