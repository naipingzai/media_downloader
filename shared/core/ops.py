"""平台总线 —— 注册、发现、调度。所有 UI 的唯一入口。"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["FeatureResult", "FeatureMeta", "PlatformOps", "PlatformBus"]


@dataclass
class FeatureResult:
    """所有功能的统一返回。UI 只需要理解这一个结构。"""
    success: bool
    message: str
    data: list[dict] | None = None
    log: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FeatureMeta:
    """单个功能的描述。UI 用此渲染菜单。"""
    id: str
    name: str
    need_url: bool


class PlatformOps(ABC):
    """平台操作表接口。每个平台继承并实现 _do_xxx。"""
    platform_id: str = ""
    display_name: str = ""
    cookie_hint: str = ""
    features: list[FeatureMeta] = []

    async def execute(self, feature_id: str, url: str,
                      cookie: str, save_dir: Path) -> FeatureResult:
        method = getattr(self, f"_do_{feature_id}", None)
        if method is None:
            return FeatureResult(False, f"功能 {feature_id} 未实现")
        return await method(url, cookie, save_dir)


class PlatformBus:
    """平台总线 — 全局单例。"""
    _registry: dict[str, PlatformOps] = {}

    @classmethod
    def register(cls, ops: PlatformOps):
        cls._registry[ops.platform_id] = ops

    @classmethod
    def get_ops(cls, platform: str) -> PlatformOps | None:
        return cls._registry.get(platform)

    @classmethod
    def list_platforms(cls) -> list[str]:
        return list(cls._registry.keys())

    @classmethod
    def get_features(cls, platform: str) -> list[FeatureMeta]:
        ops = cls._registry.get(platform)
        return list(ops.features) if ops else []

    @classmethod
    def get_all_features(cls) -> dict[str, list[FeatureMeta]]:
        return {pid: list(o.features) for pid, o in cls._registry.items()}

    @classmethod
    def get_cookie_hints(cls) -> dict[str, str]:
        return {pid: ops.cookie_hint for pid, ops in cls._registry.items()}

    @classmethod
    async def run(cls, platform: str, feature_id: str,
                  url: str, cookie: str, save_dir: Path) -> FeatureResult:
        ops = cls._registry.get(platform)
        if ops is None:
            return FeatureResult(False, f"平台 {platform} 未注册")
        return await ops.execute(feature_id, url, cookie, save_dir)
