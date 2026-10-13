"""MediaDownloader Android 桥接 —— Chaquopy 入口。

Kotlin MainActivity 调用本模块的顶层函数完成解析/下载/登录,
复用仓库根的 shared/ + platforms/ 代码 (由 copyPythonSources 复制为顶层包)。
"""
import asyncio
import json
import os
import sys

# 确保顶层包可导入 (Chaquopy srcDirs 已含 shared/ platforms/)
def _ensure_path():
    for p in sys.path:
        if os.path.isdir(os.path.join(p, "shared")):
            return
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_ensure_path()


def _run(coro):
    """在独立事件循环中执行协步函数 (同步桥接)。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ================= Cookie =================

def set_cookie(platform: str, cookie: str) -> str:
    from shared.core.cookies import CookieManager
    CookieManager().set(platform, cookie or "")
    return json.dumps({"ok": True})


def get_cookie(platform: str) -> str:
    from shared.core.cookies import CookieManager
    return json.dumps({"cookie": CookieManager().get(platform or "")})


# ================= 解析 =================

async def _resolve(url: str, platform: str):
    from shared.flow.link import LinkExtractor
    from shared.core.session import create_async_client
    from shared.core.adapter import PlatformConfig
    from platforms import get_platform

    client = create_async_client()
    try:
        links = await LinkExtractor(client).run(url, platform)
    finally:
        await client.close()
    if not links:
        return {"ok": False, "error": "未提取到有效链接"}
    link = links[0]
    cls = get_platform(platform or "douyin")
    if not cls:
        return {"ok": False, "error": "平台适配器未找到"}
    from shared.core.cookies import CookieManager
    adapter = cls(config=PlatformConfig(
        name=platform or "douyin", display_name="",
        domains=[], cookie=CookieManager().get(platform or "")))
    try:
        raw = await adapter.request_detail(link)
    finally:
        await adapter.close()
    if not raw:
        return {"ok": False, "error": "获取详情失败"}
    work = adapter.parse_detail(raw)
    if not work:
        return {"ok": False, "error": "解析失败"}
    work.setdefault("platform", platform or "douyin")
    return {"ok": True, "work": work}


def parse(url: str, platform: str = "douyin") -> str:
    """解析链接 → 作品信息 JSON 字符串。"""
    try:
        return json.dumps(_run(_resolve((url or "").strip(), platform or "douyin")),
                          ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)


# ================= 下载 =================

async def _download(url: str, platform: str, save_dir: str):
    from shared.flow.link import LinkExtractor
    from shared.flow.download import FileDownloader
    from shared.core.session import create_async_client
    from shared.core.adapter import PlatformConfig
    from shared.core.config import ConfigManager
    from platforms import get_platform
    from shared.core.cookies import CookieManager

    client = create_async_client()
    try:
        links = await LinkExtractor(client).run(url, platform)
    finally:
        await client.close()
    if not links:
        return {"ok": False, "error": "未提取到有效链接"}
    cls = get_platform(platform or "douyin")
    if not cls:
        return {"ok": False, "error": "平台适配器未找到"}
    adapter = cls(config=PlatformConfig(
        name=platform or "douyin", display_name="",
        domains=[], cookie=CookieManager().get(platform or "")))
    storage = ConfigManager.get_storage_ops(platform or "douyin")
    files = []
    try:
        for link in links:
            raw = await adapter.request_detail(link)
            if not raw:
                continue
            work = adapter.parse_detail(raw)
            if not work:
                continue
            urls = adapter.get_download_urls(work)
            if not urls:
                continue
            target = storage.resolve(work)
            dlc = create_async_client()
            try:
                dl = FileDownloader(client=dlc, save_dir=target.parent)
                # 图集: 逐张下载全部图片
                if work.get("media_type") == "images":
                    stem = target.name.rsplit(".", 1)[0]
                    for j, img in enumerate(urls, 1):
                        r = await dl.download_file(img, f"{stem}_{j:02d}.jpg")
                        if r:
                            files.append(str(r))
                else:
                    r = await dl.download_file(urls[0], target.name)
                    if r:
                        files.append(str(r))
            finally:
                await dlc.close()
        return {"ok": True, "files": files, "count": len(files)}
    finally:
        await adapter.close()


def download(url: str, platform: str = "douyin", save_dir: str = "") -> str:
    """下载作品 → 结果 JSON 字符串。"""
    try:
        sd = save_dir or os.path.join(os.path.expanduser("~"), "MediaDownloader")
        os.makedirs(sd, exist_ok=True)
        return json.dumps(_run(_download((url or "").strip(), platform or "douyin", sd)),
                          ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)


def version() -> str:
    return json.dumps({"app": "MediaDownloader", "version": "1.0"})
