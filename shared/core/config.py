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
    # 存储
    storage_mode: str = "flat"
    storage_format: str = "json"
    dedup: bool = True
    language: str = "zh_CN"
    # 输出格式
    default_profile: str = "mp4_copy"
    default_video_codec: str = "copy"
    default_audio_codec: str = "copy"
    default_image_format: str = "png"
    # 下载选项
    download_danmaku: bool = True
    download_subtitle: bool = True
    download_cover: bool = True
    download_metadata: bool = True
    # FFmpeg
    ffmpeg_path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> AppConfig:
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in valid})


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
                # 兼容旧格式
                flat = {}
                if "storage" in data:
                    s = data["storage"]
                    flat["storage_mode"] = s.get("mode", "flat")
                    flat["storage_format"] = s.get("format", "json")
                    flat["dedup"] = s.get("dedup", True)
                for k, v in data.items():
                    if k not in ("storage", "platforms"):
                        flat.setdefault(k, v)
                cls._config = AppConfig.from_dict(flat)
                return cls._config
            except Exception:
                pass
        cls._config = AppConfig()
        cls.save(cls._config)
        return cls._config

    @classmethod
    def save(cls, config: AppConfig):
        cls._config = config
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def get_storage_ops(cls, platform: str) -> StorageOps:
        config = cls.load()
        return StorageOps(platform, StorageConfig(
            mode=config.storage_mode,
            data_format=config.storage_format,
            dedup=config.dedup,
        ))
