"""平台适配器抽象基类 —— 所有平台必须实现的接口。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

__all__ = ["PlatformAdapter", "PlatformConfig", "DownloadResult"]


@dataclass
class PlatformConfig:
    name: str
    display_name: str
    domains: list[str]
    cookie: str = ""
    proxy: str | None = None
    timeout: int = 10
    max_retry: int = 5
    folder_name: str = "Download"
    name_format: str = ""
    impersonate: str = "chrome146"
    max_workers: int = 4
    download: bool = True
    folder_mode: bool = False
    author_archive: bool = False
    extra: dict = field(default_factory=dict)


@dataclass
class DownloadResult:
    success: bool
    message: str
    data: dict | None = None
    file_path: str | None = None


class PlatformAdapter(ABC):
    @abstractmethod
    def get_config_schema(self) -> dict: ...

    @abstractmethod
    async def extract_links(self, text: str) -> list: ...

    @abstractmethod
    async def request_detail(self, link) -> dict | None: ...

    @abstractmethod
    def parse_detail(self, raw: dict) -> dict | None: ...

    @abstractmethod
    def get_download_urls(self, work: dict) -> list[str]: ...

    @abstractmethod
    async def get_account_works(self, user_id: str, pages: int) -> list[dict]: ...

    @abstractmethod
    async def close(self): ...
