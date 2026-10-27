"""Cookie 管理器 —— 多配置存储、切换、更新 (线程安全 + 原子写入)。"""
from __future__ import annotations

import json
import os
import threading

from shared.core.constants import VOLUME
from shared.core.logger import get_logger
from shared.core.secret import decrypt_value, encrypt_value

__all__ = ["CookieManager"]

log = get_logger("core.cookies")

COOKIE_FILE = VOLUME / "cookies.json"


def _atomic_write_json(path, data: dict) -> None:
    """原子写入 JSON: 先写临时文件再 rename, 避免写一半崩溃丢数据。"""
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)  # 原子替换
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class CookieManager:
    """管理多个平台的 Cookie (单例, 线程安全)。

    存储格式:
    {
        "active": "默认",              # 当前使用的 Cookie 名称
        "cookies": {
            "默认": {"douyin": "...", "kuaishou": "...", "bilibili": "..."},
            "work": {"douyin": "...", ...}
        }
    }
    """

    _instance = None
    _lock = threading.Lock()  # 类级锁: 保护单例创建与所有读写

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._initialized = False
                cls._instance = inst
            return cls._instance

    def __init__(self):
        if not getattr(self, "_initialized", False):
            self.data = self._load()
            self._initialized = True
        else:
            self.reload()

    # ==================== 加载/保存 ====================
    def reload(self):
        """从磁盘重新加载 (外部文件被修改后可用)。"""
        with self._lock:
            self.data = self._load()
        return self.data

    def _load(self) -> dict:
        if COOKIE_FILE.is_file():
            try:
                with open(COOKIE_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                log.warning("Cookie 文件读取失败, 使用默认配置: %s", e)
        return {"active": "默认", "cookies": {"默认": {}}}

    def _save(self):
        # 调用方已持锁
        try:
            _atomic_write_json(COOKIE_FILE, self.data)
        except OSError as e:
            log.error("Cookie 文件保存失败: %s", e)

    # ==================== 获取 ====================
    def get(self, platform: str = "") -> str:
        """获取当前激活的 Cookie。platform 为空时返回全部平台的合并。"""
        with self._lock:
            # 保证读取到最新落盘数据 (跨实例/跨页面一致)
            self.data = self._load()
            active = self.data.get("active", "默认")
            cookies = self.data.get("cookies", {}).get(active, {})
            if platform:
                # 密文解密返回; 旧版明文原样透传 (平滑兼容)
                return decrypt_value(cookies.get(platform, ""))
            return "; ".join(
                f"{k}={decrypt_value(v)}" for k, v in cookies.items() if v)

    def get_profile_names(self) -> list[str]:
        """获取所有 Cookie 配置名称。"""
        with self._lock:
            self.data = self._load()
            return list(self.data.get("cookies", {}).keys())

    def get_active(self) -> str:
        """获取当前激活的配置名称。"""
        with self._lock:
            self.data = self._load()
            return self.data.get("active", "默认")

    def get_platforms(self, profile: str = "") -> dict:
        """获取指定配置的所有平台 Cookie。"""
        with self._lock:
            self.data = self._load()
            p = profile or self.data.get("active", "默认")
            raw = self.data.get("cookies", {}).get(p, {})
            # 返回解密后的平台 Cookie (UI 显示/校验用)
            return {k: decrypt_value(v) for k, v in raw.items()}

    # ==================== 设置 ====================
    def set(self, platform: str, cookie: str, profile: str = ""):
        """设置指定平台的 Cookie。"""
        with self._lock:
            self.data = self._load()
            p = profile or self.data.get("active", "默认")
            self.data.setdefault("cookies", {}).setdefault(p, {})
            # 落盘一律加密 (Fernet); 内存读路径统一解密
            self.data["cookies"][p][platform] = encrypt_value(cookie)
            self._save()

    def set_active(self, profile: str):
        """切换激活的 Cookie 配置。"""
        with self._lock:
            self.data = self._load()
            self.data["active"] = profile
            self._save()

    def create_profile(self, name: str):
        """创建新的 Cookie 配置。"""
        with self._lock:
            self.data = self._load()
            if name not in self.data.get("cookies", {}):
                self.data.setdefault("cookies", {})[name] = {}
                self._save()

    def delete_profile(self, name: str):
        """删除 Cookie 配置。"""
        with self._lock:
            self.data = self._load()
            cookies = self.data.get("cookies", {})
            if name in cookies and name != "默认":
                del cookies[name]
                if self.data.get("active") == name:
                    self.data["active"] = "默认"
                self._save()

    def update(self, platform: str, cookie: str):
        """更新当前激活配置中指定平台的 Cookie。"""
        self.set(platform, cookie)

    # ==================== 便捷方法 ====================
    def has_cookie(self, platform: str = "") -> bool:
        """检查是否有 Cookie。"""
        return bool(self.get(platform))

    def status_text(self, platforms: list[str] | None = None) -> str:
        """返回 Cookie 状态摘要。

        platforms: 平台 ID 列表 (由 UI 从 PlatformBus.list_platforms() 传入)。
        未传时自动探测已存储的平台 key, 避免核心层硬编码平台名单。
        """
        active = self.get_active()
        stored = self.get_platforms()
        if platforms is None:
            platforms = sorted(stored.keys())
        parts = [f"{p}:{'✓' if stored.get(p) else '✗'}" for p in platforms]
        return f"[{active}] {' '.join(parts)}"

    def load_from_file(self, filepath: str, platform: str = "douyin"):
        """从文件加载 Cookie。"""
        if os.path.isfile(filepath):
            try:
                with open(filepath, encoding="utf-8") as f:
                    cookie = f.read().strip()
            except OSError:
                return False
            if cookie:
                self.set(platform, cookie)
                return True
        return False

    def import_text(self, text: str, platform: str = "douyin"):
        """从文本导入 Cookie。"""
        cookie = text.strip()
        if cookie:
            self.set(platform, cookie)
            return True
        return False
