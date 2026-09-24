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
    # 外观
    font_size: int = 14   # 12~20, 14 默认

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> dict:
        """兼容旧版嵌套 storage 字段; 只保留当前 dataclass 已声明的字段。"""
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        return {k: v for k, v in d.items() if k in valid}


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
                flat = cls._flatten_old(data)
                cls._config = AppConfig(**cls._filter(flat))
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

    # ===== 内部辅助 =====
    @staticmethod
    def _flatten_old(data: dict) -> dict:
        """兼容旧版 {storage: {mode, format, dedup}, language} 嵌套结构。"""
        flat = dict(data)
        if "storage" in flat and isinstance(flat["storage"], dict):
            s = flat.pop("storage")
            flat.setdefault("storage_mode", s.get("mode", "flat"))
            flat.setdefault("storage_format", s.get("format", "json"))
            flat.setdefault("dedup", s.get("dedup", True))
        flat.pop("language", None)   # 仅中文, 忽略旧字段
        return flat

    @staticmethod
    def _filter(d: dict) -> dict:
        """仅保留当前 dataclass 声明的字段。"""
        valid = {f.name for f in AppConfig.__dataclass_fields__.values()}
        return {k: v for k, v in d.items() if k in valid}
