from shared.core.ops import PlatformBus
from .adapter import BilibiliAdapter
from .ops import BilibiliOps

PlatformBus.register(BilibiliOps())
__all__ = ["BilibiliAdapter", "BilibiliOps"]
