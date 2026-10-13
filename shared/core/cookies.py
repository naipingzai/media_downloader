"""Cookie 管理器 —— 支持多 Cookie 存储、切换、更新。"""
import json
import os
from pathlib import Path
from shared.core.constants import VOLUME

__all__ = ["CookieManager"]

COOKIE_FILE = VOLUME / "cookies.json"


class CookieManager:
    """管理多个平台的 Cookie (单例)。

    存储格式:
    {
        "active": "默认",              # 当前使用的 Cookie 名称
        "cookies": {
            "默认": {"douyin": "...", "kuaishou": "...", "xiaohongshu": "..."},
            "work": {"douyin": "...", ...}
        }
    }

    作为单例实现: 全工程共用一个实例, 避免多个实例内存数据不同步
    (例如登录页保存 Cookie 后, 主窗口缓存仍是旧数据导致读取为空)。
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._initialized = False
            cls._instance = inst
        return cls._instance

    def __init__(self):
        # 单例: 只初始化一次; 之后每次构造都从磁盘刷新数据
        if not getattr(self, "_initialized", False):
            self.data = self._load()
            self._initialized = True
        else:
            self.reload()

    def reload(self):
        """从磁盘重新加载 (外部文件被修改后可用)。"""
        self.data = self._load()
        return self.data

    def _load(self) -> dict:
        if COOKIE_FILE.is_file():
            try:
                with open(COOKIE_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"active": "默认", "cookies": {"默认": {}}}

    def _save(self):
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # ==================== 获取 ====================

    def get(self, platform: str = "") -> str:
        """获取当前激活的 Cookie。platform 为空时返回全部平台的合并。"""
        # 保证读取到最新落盘数据 (跨实例/跨页面一致)
        self.reload()
        active = self.data.get("active", "默认")
        cookies = self.data.get("cookies", {}).get(active, {})
        if platform:
            return cookies.get(platform, "")
        return "; ".join(f"{k}={v}" for k, v in cookies.items() if v)

    def get_profile_names(self) -> list[str]:
        """获取所有 Cookie 配置名称。"""
        return list(self.data.get("cookies", {}).keys())

    def get_active(self) -> str:
        """获取当前激活的配置名称。"""
        return self.data.get("active", "默认")

    def get_platforms(self, profile: str = "") -> dict:
        """获取指定配置的所有平台 Cookie。"""
        p = profile or self.get_active()
        return self.data.get("cookies", {}).get(p, {})

    # ==================== 设置 ====================

    def set(self, platform: str, cookie: str, profile: str = ""):
        """设置指定平台的 Cookie。"""
        p = profile or self.get_active()
        if p not in self.data["cookies"]:
            self.data["cookies"][p] = {}
        self.data["cookies"][p][platform] = cookie
        self._save()

    def set_active(self, profile: str):
        """切换激活的 Cookie 配置。"""
        self.data["active"] = profile
        self._save()

    def create_profile(self, name: str):
        """创建新的 Cookie 配置。"""
        if name not in self.data["cookies"]:
            self.data["cookies"][name] = {}
            self._save()

    def delete_profile(self, name: str):
        """删除 Cookie 配置。"""
        if name in self.data["cookies"] and name != "默认":
            del self.data["cookies"][name]
            if self.data["active"] == name:
                self.data["active"] = "默认"
            self._save()

    def update(self, platform: str, cookie: str):
        """更新当前激活配置中指定平台的 Cookie。"""
        self.set(platform, cookie)

    # ==================== 便捷方法 ====================

    def get_douyin(self) -> str:
        return self.get("douyin")

    def get_kuaishou(self) -> str:
        return self.get("kuaishou")

    def get_xiaohongshu(self) -> str:
        return self.get("xiaohongshu")

    def has_cookie(self, platform: str = "") -> bool:
        """检查是否有 Cookie。"""
        return bool(self.get(platform))

    def status_text(self) -> str:
        """返回 Cookie 状态摘要。"""
        active = self.get_active()
        platforms = self.get_platforms()
        parts = []
        for p in ["douyin", "kuaishou", "xiaohongshu"]:
            parts.append(f"{p}:{'✓' if platforms.get(p) else '✗'}")
        return f"[{active}] {' '.join(parts)}"

    def load_from_file(self, filepath: str, platform: str = "douyin"):
        """从文件加载 Cookie。"""
        if os.path.isfile(filepath):
            with open(filepath, encoding="utf-8") as f:
                cookie = f.read().strip()
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
