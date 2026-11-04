"""登录框架 — 各平台登录管理器的统一接口。"""
from abc import ABC, abstractmethod
from PIL import Image

__all__ = ["PlatformLoginManager", "LoginBus"]


class PlatformLoginManager(ABC):
    """平台登录管理器接口。各平台实现此接口并注册到 LoginBus。"""

    platform_id: str = ""
    login_methods: list[str] = ["qr"]  # 支持的登录方式：qr / cookie

    @abstractmethod
    def generate_qr(self) -> tuple[str, str, Image.Image]:
        """生成二维码。返回 (url, token, PIL.Image)。"""
        ...

    @abstractmethod
    def check_qr_status(self, token: str) -> dict:
        """轮询二维码状态。返回 {"code": 0/86090/86038, "cookies": {}}。"""
        ...

    def close(self):
        """清理资源。"""
        pass


class LoginBus:
    """登录管理器总线 — 全局单例。"""
    _registry: dict[str, PlatformLoginManager] = {}

    @classmethod
    def register(cls, manager: PlatformLoginManager):
        cls._registry[manager.platform_id] = manager

    @classmethod
    def get_manager(cls, platform: str) -> PlatformLoginManager | None:
        return cls._registry.get(platform)

    @classmethod
    def has_qr(cls, platform: str) -> bool:
        mgr = cls._registry.get(platform)
        return mgr is not None and "qr" in mgr.login_methods
