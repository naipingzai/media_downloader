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

    # ===== 统一扩展接口 (默认不支持, 各平台 adapter 覆写) =====
    async def fetch_current_user(self) -> dict | None:
        """获取当前登录用户 (Cookie 作者信息)。"""
        return None

    async def fetch_user_profile(self, sec_uid: str) -> dict | None:
        """获取作者资料。"""
        return None

    async def fetch_user_posts(self, sec_uid: str, count: int = 20,
                               max_cursor: str = "0") -> dict | list | None:
        """分页获取作者所有作品。"""
        return None

    async def fetch_user_following(self, sec_uid: str, count: int = 20,
                                   max_time: str = "0") -> dict | None:
        """分页获取关注列表。"""
        return None

    async def fetch_collection(self, cursor: str = "0", count: int = 20) -> dict | None:
        """分页获取收藏作品。"""
        return None

    async def fetch_comments(self, work_id: str) -> list[dict]:
        """获取作品评论 (nickname/content)。"""
        return []

    @abstractmethod
    async def close(self): ...


# ===== 通用归一化辅助 (各平台 adapter 复用) =====
def norm_user(u: dict, platform: str = "") -> dict:
    """任意平台用户 dict → 统一 profile (与抖音字段对齐)。"""
    if not isinstance(u, dict):
        return {}
    av = u.get("avatar") or u.get("avatar_larger") or u.get("face") or u.get("headerUrl") or ""
    if isinstance(av, dict):
        av = (av.get("url_list") or [av.get("url", "")])[0] or ""
    return {
        "user_id": str(u.get("user_id") or u.get("uid") or u.get("mid") or u.get("id") or ""),
        "sec_user_id": str(u.get("sec_user_id") or u.get("sec_uid") or u.get("userId")
                           or u.get("mid") or u.get("user_id") or ""),
        "nickname": u.get("nickname") or u.get("nick_name") or u.get("uname") or u.get("name") or "",
        "signature": u.get("signature") or u.get("sign") or u.get("desc") or "",
        "avatar": av,
        "follower_count": u.get("follower_count") or u.get("fans") or u.get("fansCount") or 0,
        "following_count": u.get("following_count") or u.get("following") or u.get("attention") or 0,
        "total_favorited": u.get("total_favorited") or u.get("likeCount") or 0,
        "aweme_count": u.get("aweme_count") or u.get("videoCount") or u.get("publishCount") or 0,
        "platform": platform or u.get("platform", ""),
    }


def _cover_of(v: dict) -> str:
    for k in ("cover", "origin_cover", "dynamic_cover", "coverUrl", "poster"):
        c = v.get(k) if isinstance(v, dict) else None
        if isinstance(c, dict):
            urls = c.get("url_list") or c.get("url") or []
            if isinstance(urls, str):
                return urls
            if urls:
                return urls[0]
        elif isinstance(c, str) and c:
            return c
    return ""


def norm_work(raw: dict, platform: str = "") -> dict:
    """任意平台作品 dict → 统一 work (供作品资料卡/批量卡片)。"""
    if not isinstance(raw, dict):
        return {}
    v = raw.get("video") or raw
    au = raw.get("author") or raw.get("user") or {}
    stat = raw.get("statistics") or raw.get("stat") or raw.get("interactInfo") or {}
    wid = raw.get("work_id") or raw.get("aweme_id") or raw.get("photoId") or raw.get("bvid") \
        or raw.get("noteId") or raw.get("id") or ""
    share = raw.get("share_url") or raw.get("shareUrl") or ""
    if not share and wid:
        if platform == "bilibili":
            share = f"https://www.bilibili.com/video/{wid}"
        elif platform == "kuaishou":
            share = f"https://www.kuaishou.com/short-video/{wid}"
        elif platform == "xiaohongshu":
            share = f"https://www.xiaohongshu.com/discovery/item/{wid}"
        elif platform == "douyin":
            share = f"https://www.douyin.com/video/{wid}"
    dur = raw.get("duration") or v.get("duration") or 0
    try:
        dur = int(dur)
        if dur > 10000:
            dur //= 1000
    except (TypeError, ValueError):
        dur = 0
    return {
        "platform": platform or raw.get("platform", ""),
        "work_id": str(wid),
        "title": raw.get("title") or raw.get("desc") or raw.get("caption") or "",
        "author_name": au.get("nickname") or au.get("name") or raw.get("author_name") or "",
        "sec_user_id": au.get("sec_uid") or au.get("userId") or au.get("mid") or raw.get("sec_user_id") or "",
        "duration": dur,
        "digg_count": stat.get("digg_count") or stat.get("likeCount") or stat.get("liked_count") or 0,
        "comment_count": stat.get("comment_count") or stat.get("commentCount") or 0,
        "view_count": stat.get("play_count") or stat.get("viewCount") or stat.get("playCount") or 0,
        "share_url": share,
        "cover_url": _cover_of(raw) or _cover_of(v),
        "video_url": raw.get("video_url") or raw.get("mainMvUrl") or "",
    }


def norm_comment(c: dict) -> dict:
    """任意平台评论 dict → {nickname, content}。"""
    if not isinstance(c, dict):
        return {}
    m = c.get("member") or c.get("user") or c.get("author") or {}
    return {
        "nickname": (m.get("uname") or m.get("nickname") or m.get("name")
                     or c.get("nickname") or c.get("user_name") or "?"),
        "content": (c.get("content") or c.get("message") or c.get("text")
                    or c.get("comment") or ""),
    }
