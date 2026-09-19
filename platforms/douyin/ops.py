"""抖音平台操作表 —— 完全自包含。"""
from pathlib import Path
from shared.core.ops import PlatformOps, FeatureMeta, FeatureResult
from shared.core.storage import StorageOps, safe_name
from shared.core.config import ConfigManager


class DouyinOps(PlatformOps):
    platform_id = "douyin"
    display_name = "Douyin / TikTok"
    cookie_hint = "需要完整 Cookie 字符串"

    features = [
        FeatureMeta("download",   "下载单个作品",       True),
        FeatureMeta("account",    "批量下载账号作品",   True),
        FeatureMeta("mix",        "批量下载合集作品",   True),
        FeatureMeta("collection", "批量下载收藏作品",   True),
        FeatureMeta("live",       "获取直播拉流地址",   True),
        FeatureMeta("comment",    "采集作品评论数据",   True),
        FeatureMeta("user",       "采集账号详细数据",   True),
        FeatureMeta("search",     "采集搜索结果数据",   True),
        FeatureMeta("hot",        "采集抖音热榜数据",   False),
    ]

    async def _get_adapter(self, cookie: str):
        from .adapter import DouyinAdapter
        from shared.core.adapter import PlatformConfig
        return DouyinAdapter(config=PlatformConfig(
            name="douyin", display_name=self.display_name,
            domains=["douyin.com"], cookie=cookie))

    async def _do_download(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            from shared.flow.link import LinkExtractor
            from shared.flow.download import FileDownloader
            from shared.core.session import create_async_client
            client = create_async_client()
            try:
                links = await LinkExtractor(client).run(url, "douyin")
            finally:
                await client.close()
            if not links:
                return FeatureResult(False, "未提取到有效链接")
            log, files = [], []
            for i, link in enumerate(links, 1):
                log.append(f"[{i}/{len(links)}] {link.url[:60]}")
                raw = await adapter.request_detail(link)
                if not raw:
                    log.append("  获取详情失败"); continue
                work = adapter.parse_detail(raw)
                if not work:
                    log.append("  解析失败"); continue
                log.append(f"  {work['author_name']}: {work['title'][:40]}")
                urls = adapter.get_download_urls(work)
                if not urls:
                    log.append("  无下载地址"); continue
                target = storage.resolve(work)
                dlc = create_async_client()
                try:
                    dl = FileDownloader(client=dlc, save_dir=target.parent)
                    result = await dl.download_file(urls[0], target.name)
                finally:
                    await dlc.close()
                if result:
                    log.append(f"  ✓ {result}")
                    storage.record_download(link.work_id)
                    files.append(str(result))
                else:
                    log.append("  ✗ 下载失败")
            return FeatureResult(True, f"处理 {len(links)} 个链接", log=log, files=files)
        finally:
            await adapter.close()

    async def _do_account(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            sec_uid = await self._resolve_sec_uid(adapter, url)
            if not sec_uid:
                return FeatureResult(False, "无法获取用户信息，请输入用户主页链接")
            data = await adapter.fetch_user_posts(sec_uid)
            if not data:
                return FeatureResult(False, "获取作品列表失败")
            aweme_list = data.get("aweme_list", [])
            return await self._batch_download(adapter, aweme_list, storage)
        finally:
            await adapter.close()

    async def _do_mix(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            mix_id = url.strip().rstrip("/").split("/")[-1]
            data = await adapter.fetch_mix(mix_id)
            if not data:
                return FeatureResult(False, "获取合集失败")
            return await self._batch_download(adapter, data.get("aweme_list", []), storage)
        finally:
            await adapter.close()

    async def _do_collection(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            data = await adapter.fetch_collection()
            if not data:
                return FeatureResult(False, "获取收藏失败")
            return await self._batch_download(adapter, data.get("aweme_list", []), storage)
        finally:
            await adapter.close()

    async def _do_live(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            room_id = url.strip().rstrip("/").split("/")[-1]
            data = await adapter.fetch_live(room_id)
            if not data:
                return FeatureResult(False, "获取直播信息失败")
            room_list = data.get("data", {}).get("data", [])
            room = room_list[0] if room_list else {}
            title = room.get("title", "")
            owner = room.get("owner", {}).get("nickname", "")
            stream = room.get("stream_url", {})
            log = [f"主播: {owner}  标题: {title}"]
            for q, u in stream.get("hls_pull_url_map", {}).items():
                log.append(f"HLS [{q}]: {u[:120]}")
            for q, u in list(stream.get("flv_pull_url_map", {}).items())[:3]:
                log.append(f"FLV [{q}]: {u[:120]}")
            if len(log) == 1:
                return FeatureResult(False, "未获取到直播流")
            await storage.save_data([{"room_id": room_id, "owner": owner, "title": title,
                "hls": dict(stream.get("hls_pull_url_map", {})),
                "flv": dict(stream.get("flv_pull_url_map", {}))}], f"live_{room_id}")
            return FeatureResult(True, f"直播流: {owner}", log=log)
        finally:
            await adapter.close()

    async def _do_comment(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            aweme_id = url.strip().rstrip("/").split("/")[-1]
            all_c, cursor = [], 0
            for _ in range(5):
                data = await adapter.fetch_comments(aweme_id, cursor=cursor)
                if not data: break
                cs = data.get("comments", [])
                if not cs: break
                all_c.extend(cs)
                if not data.get("has_more", False): break
                cursor = data.get("cursor", 0)
            parsed = [{"user": c.get("user", {}).get("nickname", ""), "text": c.get("text", ""),
                       "digg_count": c.get("digg_count", 0)} for c in all_c]
            await storage.save_data(parsed, f"comments_{aweme_id}")
            log = [f"[{c['user']}] {c['text'][:50]}" for c in parsed[:20]]
            return FeatureResult(True, f"共 {len(parsed)} 条评论", data=parsed, log=log)
        finally:
            await adapter.close()

    async def _do_user(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            sec_uid = await self._resolve_sec_uid(adapter, url)
            if not sec_uid:
                return FeatureResult(False, "无法获取用户信息")
            data = await adapter.fetch_user_profile(sec_uid)
            if not data:
                return FeatureResult(False, "获取账号数据失败")
            user = data.get("user", {})
            await storage.save_data([user], f"user_{user.get('uid', 'x')}")
            log = [
                f"昵称: {user.get('nickname', '?')}",
                f"粉丝: {user.get('follower_count', 0)}  关注: {user.get('following_count', 0)}  获赞: {user.get('total_favorited', 0)}",
                f"作品: {user.get('aweme_count', 0)}  签名: {user.get('signature', '')[:60]}",
            ]
            return FeatureResult(True, f"账号: {user.get('nickname', '?')}", data=[user], log=log)
        finally:
            await adapter.close()

    async def _do_search(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            keyword = url.strip()
            if not keyword:
                return FeatureResult(False, "请输入搜索关键词")
            data = await adapter.fetch_search(keyword)
            if not data:
                return FeatureResult(False, "搜索失败")
            parsed = []
            for item in data.get("data", []):
                aw = item.get("aweme_info", {})
                if not aw: continue
                a = aw.get("author", {})
                parsed.append({"title": aw.get("desc", ""), "author": a.get("nickname", ""),
                               "digg_count": aw.get("statistics", {}).get("digg_count", 0),
                               "aweme_id": aw.get("aweme_id", "")})
            await storage.save_data(parsed, "search_results")
            log = [f"[{i}] {p['author']}: {p['title'][:40]}" for i, p in enumerate(parsed[:20], 1)]
            return FeatureResult(True, f"搜索到 {len(parsed)} 条结果", data=parsed, log=log)
        finally:
            await adapter.close()

    async def _do_hot(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            results = await adapter.fetch_hot_list()
            if not results:
                return FeatureResult(False, "热榜数据为空")
            await storage.save_data(results, "hot_list")
            log = [f"#{it['rank']} {it['word']} ({it['hot_value']})" for it in results]
            return FeatureResult(True, f"获取到 {len(results)} 条热榜", data=results, log=log)
        finally:
            await adapter.close()

    async def _batch_download(self, adapter, aweme_list, storage):
        from shared.flow.download import FileDownloader
        from shared.core.session import create_async_client
        log, files = [], []
        dlc = create_async_client()
        try:
            dl = FileDownloader(client=dlc, save_dir=storage.base_dir)
            for i, aw in enumerate(aweme_list, 1):
                aweme_id = aw.get("aweme_id", "")
                desc = aw.get("desc", "")[:40]
                log.append(f"  [{i}] {desc}")
                video = aw.get("video", {})
                play = video.get("play_addr", {}).get("url_list", [])
                bit_rate = video.get("bit_rate", [])
                if bit_rate:
                    best = max(bit_rate, key=lambda x: x.get("bit_rate", 0))
                    play = best.get("play_addr", {}).get("url_list", []) or play
                if not play:
                    log.append("    无下载地址"); continue
                target = storage.resolve(aw)
                result = await dl.download_file(play[0], target.name)
                if result:
                    log.append(f"    ✓ 完成")
                    storage.record_download(aweme_id)
                    files.append(str(result))
                else:
                    log.append(f"    ✗ 失败")
        finally:
            await dlc.close()
        return FeatureResult(True, f"批量下载 {len(files)}/{len(aweme_list)} 个", log=log, files=files)

    async def _resolve_sec_uid(self, adapter, url: str) -> str:
        if "sec_user_id=" in url:
            return url.split("sec_user_id=")[-1].split("&")[0]
        if "/user/" in url:
            return url.strip().split("/user/")[-1].split("?")[0]
        from shared.flow.link import LinkExtractor
        from shared.core.session import create_async_client
        client = create_async_client()
        try:
            links = await LinkExtractor(client).run(url, "douyin")
        finally:
            await client.close()
        if links:
            raw = await adapter.request_detail(links[0])
            if raw:
                work = adapter.parse_detail(raw)
                if work:
                    return work.get("sec_user_id", "")
        return ""
