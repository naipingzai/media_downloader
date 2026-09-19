"""Bilibili platform ops。"""
from pathlib import Path
from shared.core.ops import PlatformOps, FeatureMeta, FeatureResult
from shared.core.config import ConfigManager


class BilibiliOps(PlatformOps):
    platform_id = "bilibili"
    display_name = "Bilibili"
    cookie_hint = "需要 SESSDATA Cookie（从浏览器 DevTools 复制）"

    features = [
        FeatureMeta("download",   "下载单个视频",       True),
        FeatureMeta("account",    "批量下载用户作品",   True),
        FeatureMeta("series",     "批量下载合集/系列",  True),
        FeatureMeta("collection", "批量下载收藏夹",     True),
        FeatureMeta("comment",    "采集视频评论",       True),
        FeatureMeta("user",       "采集用户资料",       True),
    ]

    async def _get_adapter(self, cookie: str):
        from .adapter import BilibiliAdapter
        from shared.core.adapter import PlatformConfig
        return BilibiliAdapter(config=PlatformConfig(
            name="bilibili", display_name=self.display_name,
            domains=["bilibili.com"], cookie=cookie))

    async def _do_download(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("bilibili")
        try:
            from shared.flow.link import LinkExtractor
            from shared.core.session import create_async_client
            client = create_async_client()
            try:
                links = await LinkExtractor(client).run(url, "bilibili")
            finally:
                await client.close()
            if not links:
                return FeatureResult(False, "未提取到有效链接")
            log = []
            for i, link in enumerate(links, 1):
                log.append(f"[{i}/{len(links)}] {link.url[:60]}")
                raw = await adapter.request_detail(link)
                if raw:
                    work = adapter.parse_detail(raw)
                    if work:
                        log.append(f"  {work['author_name']}: {work['title'][:40]}")
                        log.append(f"  播放: {work.get('view_count', 0)}  点赞: {work.get('digg_count', 0)}")
            return FeatureResult(True, f"解析 {len(links)} 个视频", log=log)
        finally:
            await adapter.close()

    async def _do_account(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        try:
            from re import compile
            m = compile(r"bilibili\.com/space/([0-9]+)").search(url)
            if not m:
                return FeatureResult(False, "无法从链接提取用户ID")
            mid = m.group(1)
            self._log = []
            self._log.append(f"用户 MID: {mid}")
            return FeatureResult(True, f"用户 MID: {mid}", log=self._log)
        finally:
            await adapter.close()

    async def _do_series(self, url, cookie, save_dir) -> FeatureResult:
        return FeatureResult(True, "合集功能已注册，下载逻辑待完善", log=["合集功能需要额外 API 调用"])

    async def _do_collection(self, url, cookie, save_dir) -> FeatureResult:
        return FeatureResult(True, "收藏夹功能已注册，下载逻辑待完善", log=["收藏夹功能需要额外 API 调用"])

    async def _do_comment(self, url, cookie, save_dir) -> FeatureResult:
        return FeatureResult(True, "评论采集已注册，逻辑待完善", log=["评论采集需要额外 API 调用"])

    async def _do_user(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        try:
            from re import compile
            m = compile(r"bilibili\.com/space/([0-9]+)").search(url)
            mid = m.group(1) if m else url.strip()
            log = [f"用户 MID: {mid}", "用户资料采集需要额外 API 调用"]
            return FeatureResult(True, f"用户 MID: {mid}", log=log)
        finally:
            await adapter.close()
