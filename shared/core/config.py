"""全局配置管理。"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .constants import VOLUME
from .storage import StorageOps, StorageConfig

__all__ = ["AppConfig", "ConfigManager"]

CONFIG_FILE = VOLUME / "config.json"


@dataclass
class AppConfig:
    storage_mode: str = "flat"
    storage_format: str = "json"
    dedup: bool = True
    language: str = "zh_CN"


class ConfigManager:
    _config: AppConfig | None = None

    @classmethod
    def load(cls) -> AppConfig:
        if cls._config:
            return cls._config
        if CONFIG_FILE.is_file():
            try:
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                s = data.get("storage", {})
                cls._config = AppConfig(
                    storage_mode=s.get("mode", "flat"),
                    storage_format=s.get("format", "json"),
                    dedup=s.get("dedup", True),
                    language=data.get("language", "zh_CN"),
                )
                return cls._config
            except Exception:
                pass
        cls._config = AppConfig()
        cls.save(cls._config)  # 首次启动时创建 config.json
        return cls._config

    @classmethod
    def save(cls, config: AppConfig):
        cls._config = config
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, ensure_ascii=False, indent=2)

    @classmethod
    def get_storage_ops(cls, platform: str) -> StorageOps:
        config = cls.load()
        return StorageOps(platform, StorageConfig(
            mode=config.storage_mode,
            data_format=config.storage_format,
            dedup=config.dedup,
        ))
