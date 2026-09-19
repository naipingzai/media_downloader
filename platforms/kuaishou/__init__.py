from shared.core.ops import PlatformBus
from .adapter import KuaishouAdapter
from .ops import KuaishouOps

PlatformBus.register(KuaishouOps())
__all__ = ["KuaishouAdapter", "KuaishouOps"]
