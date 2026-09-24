"""小红书平台操作表。"""
from pathlib import Path
from shared.core.ops import PlatformOps, FeatureMeta, FeatureResult
from shared.core.config import ConfigManager


class XiaohongshuOps(PlatformOps):
    platform_id = "xiaohongshu"
    display_name = "Xiaohongshu / RedNote"
    cookie_hint = ""

    features = [
        FeatureMeta("download",    "下载单个作品",         True),
        FeatureMeta("account",     "批量下载用户作品",     True),
        FeatureMeta("collection",  "批量下载收藏作品",     False),
        FeatureMeta("user",        "采集账号详细数据",     True),
        FeatureMeta("following",   "采集关注列表",         True),
    ]

    async def _get_adapter(self, cookie: str):
        from .adapter import XiaohongshuAdapter
        from shared.core.adapter import PlatformConfig
        return XiaohongshuAdapter(config=PlatformConfig(
            name="xiaohongshu", display_name=self.display_name,
            domains=["xiaohongshu.com", "rednote.com"], cookie=cookie))

    # ---- 缓存 (预览→选择→下载 两阶段避免重复请求) ----
    _CACHE_TTL = 1800

    def _cache_get(self, key: str):
        import time
        ent = getattr(self, "_list_cache", {}).get(key)
        if ent and time.time() - ent[0] < self._CACHE_TTL:
            return ent[1]
        return None

    def _cache_put(self, key: str, items: list):
        import time
        if not hasattr(self, "_list_cache"):
            self._list_cache = {}
        self._list_cache[key] = (time.time(), items)

    def _extract_user_id(self, url: str) -> str:
        """从 user/profile/<id> 或纯 ID 中提取小红书 user_id。"""
        from re import compile
        m = compile(r"xiaohongshu\.com/user/profile/([a-zA-Z0-9]+)").search(url)
        if m: return m.group(1)
        m = compile(r"xhslink\.com/[a-zA-Z0-9]+").search(url)
        if m: return m.group(0)  # 短链需要展开, 暂返原值
        s = url.strip().split("/")[-1].split("?")[0]
        return s if s else ""

    async def _do_account(self, url, cookie, save_dir, selected=None) -> FeatureResult:
        """批量下载小红书用户作品。链接形如 xiaohongshu.com/user/profile/<user_id>。"""
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("xiaohongshu")
        try:
            user_id = self._extract_user_id(url)
            if not user_id:
                return FeatureResult(False,
                    "无法提取用户ID，需要 xiaohongshu.com/user/profile/<id> 格式链接")
            cache_key = f"xhs_account:{user_id}"
            notes = self._cache_get(cache_key)
            if notes is None:
                log = [f"用户 ID: {user_id}"]
                self.log(f"▸ 拉取用户作品 (小红书) {user_id}...")
                notes = await adapter.fetch_user_posts(user_id, count=30)
                if not notes:
                    return FeatureResult(False,
                        "未拉取到作品 (可能需登录 Cookie, 或账号无作品)",
                        log=log)
                self._cache_put(cache_key, notes)
                log.append(f"共 {len(notes)} 个作品")
            else:
                log = [f"使用缓存 (共 {len(notes)} 个作品)"]
            # 阶段 1: 预览
            if selected is None:
                items = [self._work_preview(n) for n in notes]
                return FeatureResult(True,
                    f"共 {len(items)} 个作品，待选择下载",
                    data=items, preview="batch", log=log)
            # 阶段 2: 下载勾选
            sel = {str(s) for s in selected}
            targets = [n for n in notes if str(n.get("note_id") or n.get("work_id") or "") in sel]
            if not targets:
                return FeatureResult(False,
                    "未匹配到勾选的作品（列表可能已过期, 请重新执行）",
                    log=log)
            return await self._batch_download(adapter, targets, storage, log)
        finally:
            await adapter.close()

    async def _batch_download(self, adapter, notes: list, storage, log: list):
        """下载选中的小红书作品 (复用 _do_download 单作品下载逻辑)。"""
        from shared.flow.download import FileDownloader
        from shared.core.session import create_async_client
        files = []
        for i, n in enumerate(notes, 1):
            work = self._to_work(n)
            if not work:
                log.append(f"[{i}/{len(notes)}] 解析失败, 跳过")
                continue
            title = work.get("title", "")[:40]
            note_id = work.get("work_id", "?")
            log.append(f"[{i}/{len(notes)}] {work.get('author_name', '?')}: {title}")
            urls = adapter.get_download_urls(work)
            if not urls:
                log.append("  无下载地址"); continue
            target = storage.resolve(work)
            dlc = create_async_client()
            try:
                dl = FileDownloader(client=dlc, save_dir=target.parent)
                is_video = work.get("is_video", False)
                for j, file_url in enumerate(urls):
                    ext = "mp4" if (is_video and j == 0) else "jpg"
                    fname = (f"{target.stem}_{j+1}.{ext}" if len(urls) > 1
                             else f"{target.stem}.{ext}")
                    result = await dl.download_file(file_url, fname)
                    if result:
                        log.append(f"  ✓ {result}")
                        files.append(str(result))
                    else:
                        log.append(f"  ✗ 文件 {j+1} 下载失败")
            finally:
                await dlc.close()
        return FeatureResult(True,
            f"下载 {len(files)}/{len(notes)} 个作品",
            log=log, files=files)

    @staticmethod
    def _to_work(n: dict) -> dict:
        """把 fetch_user_posts 的原始 note 转换为 parse_detail 同样的 schema。"""
        note_id = n.get("note_id") or n.get("work_id", "")
        title = n.get("title", "")
        ntype = n.get("type", "normal")
        images = [img if isinstance(img, str) else (img.get("url_default") or img.get("url"))
                  for img in (n.get("image_list") or [])]
        images = [u for u in images if u]
        video_url = ""
        video = n.get("video") or {}
        if isinstance(video, dict):
            media = video.get("media") or {}
            stream = (media.get("stream") or {}).get("h264", [])
            if stream:
                video_url = stream[0].get("master_url") or stream[0].get("masterUrl", "")
            if not video_url:
                video_url = media.get("consumer", {}).get("origin_video_key", "")
        user = n.get("user") or {}
        return {
            "platform": "xiaohongshu",
            "work_id": note_id,
            "type": ntype,
            "title": title,
            "author_name": user.get("nickname", ""),
            "author_id": user.get("userId") or user.get("user_id", ""),
            "video_url": video_url,
            "image_urls": images,
            "is_video": ntype == "video" or bool(video_url),
            "is_live": ntype == "normal" and not video_url and len(images) > 0,
            "digg_count": (n.get("interact_info") or {}).get("liked_count", 0),
            "comment_count": (n.get("interact_info") or {}).get("comment_count", 0),
            "cover_url": n.get("cover_url") or "",
        }

    @staticmethod
    def _work_preview(n: dict) -> dict:
        """列表项 → 预览条目 (封面/标题/作者/类型)。"""
        cover = n.get("cover_url") or n.get("cover") or ""
        return {
            "platform": "xiaohongshu",
            "work_id": n.get("note_id") or n.get("work_id", ""),
            "title": n.get("title", ""),
            "author_name": (n.get("user") or {}).get("nickname", ""),
            "cover_url": cover,
            "digg_count": (n.get("interact_info") or {}).get("liked_count", 0),
            "comment_count": (n.get("interact_info") or {}).get("comment_count", 0),
            "type": n.get("type", "normal"),
        }

    async def _do_collection(self, url, cookie, save_dir, selected=None) -> FeatureResult:
        """批量下载小红书收藏作品 (需要登录 Cookie)。"""
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("xiaohongshu")
        try:
            cache_key = "xhs_collection"
            notes = self._cache_get(cache_key)
            if notes is None:
                notes = await adapter.fetch_collection(count=50)
                if not notes:
                    return FeatureResult(False,
                        "未拉到收藏作品 (可能未登录 / 接口变化)",
                        log=["提示: 请先在设置里登录小红书账号"])
                self._cache_put(cache_key, notes)
            log = [f"共 {len(notes)} 个收藏作品"]
            if selected is None:
                items = [self._work_preview(n) for n in notes]
                return FeatureResult(True,
                    f"共 {len(items)} 个收藏作品，待选择下载",
                    data=items, preview="batch", log=log)
            sel = {str(s) for s in selected}
            targets = [n for n in notes if str(n.get("note_id") or n.get("work_id") or "") in sel]
            if not targets:
                return FeatureResult(False,
                    "未匹配到勾选的作品（列表可能已过期, 请重新执行）",
                    log=log)
            return await self._batch_download(adapter, targets, storage, log)
        finally:
            await adapter.close()

    async def _do_user(self, url, cookie, save_dir) -> FeatureResult:
        """采集小红书作者详细资料。"""
        adapter = await self._get_adapter(cookie)
        try:
            user_id = self._extract_user_id(url) if url else ""
            if not user_id:
                return FeatureResult(False,
                    "需要 xiaohongshu.com/user/profile/<id> 链接")
            profile = await adapter.fetch_user_profile(user_id)
            if not profile:
                return FeatureResult(False, "未拉到用户资料", log=[f"用户: {user_id}"])
            log = [f"用户 ID: {user_id}"]
            data = [
                {"field": "昵称",   "value": profile.get("nickname", "")},
                {"field": "UID",    "value": profile.get("user_id", user_id)},
                {"field": "粉丝",   "value": profile.get("follower_count", 0)},
                {"field": "关注",   "value": profile.get("following_count", 0)},
                {"field": "作品",   "value": profile.get("aweme_count", 0)},
                {"field": "签名",   "value": profile.get("signature", "")},
            ]
            return FeatureResult(True,
                f"用户: {profile.get('nickname', user_id)}",
                log=log, data=data)
        finally:
            await adapter.close()

    async def _do_following(self, url, cookie, save_dir) -> FeatureResult:
        """采集小红书关注列表。"""
        adapter = await self._get_adapter(cookie)
        try:
            user_id = self._extract_user_id(url) if url else ""
            if not user_id:
                return FeatureResult(False,
                    "需要 xiaohongshu.com/user/profile/<id> 链接")
            payload = await adapter.fetch_user_following(user_id, count=100)
            if not payload:
                return FeatureResult(False,
                    "未拉到关注列表 (可能未登录 / 接口变化)",
                    log=["提示: 请先在设置里登录小红书账号"])
            users = (payload.get("followings", []) if isinstance(payload, dict) else payload) or []
            log = [f"共 {len(users)} 个关注"]
            data = [[u.get("nickname", ""),
                     u.get("follower_count", 0),
                     (u.get("signature") or "")[:40]]
                    for u in users]
            return FeatureResult(True,
                f"采集 {len(users)} 个关注",
                log=log, data=data)
        finally:
            await adapter.close()

    async def _do_download(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("xiaohongshu")
        try:
            from shared.flow.link import LinkExtractor
            from shared.flow.download import FileDownloader
            from shared.core.session import create_async_client
            client = create_async_client()
            try:
                links = await LinkExtractor(client).run(url, "xiaohongshu")
            finally:
                await client.close()
            if not links:
                return FeatureResult(False, "未提取到有效链接")
            log, files = [], []
            def _log(msg):
                log.append(msg)
                self.log(msg)
            for i, link in enumerate(links, 1):
                _log(f"[{i}/{len(links)}] {link.url[:60]}")
                raw = await adapter.request_detail(link)
                if not raw:
                    _log("  获取详情失败"); continue
                work = adapter.parse_detail(raw)
                if not work:
                    _log("  解析失败"); continue
                log.append(f"  {work.get('author_name', '?')}: {work.get('title', '')[:40]}")
                urls = adapter.get_download_urls(work)
                if not urls:
                    _log("  无下载地址"); continue
                target = storage.resolve(work)
                dlc = create_async_client()
                try:
                    dl = FileDownloader(client=dlc, save_dir=target.parent)
                    is_video = work.get("is_video", False)
                    for j, file_url in enumerate(urls):
                        if is_video and j == 0:
                            ext = "mp4"
                        else:
                            ext = "jpg"
                        fname = f"{target.stem}_{j+1}.{ext}" if len(urls) > 1 else f"{target.stem}.{ext}"
                        result = await dl.download_file(file_url, fname)
                        if result:
                            _log(f"  ✓ {result}")
                            files.append(str(result))
                        else:
                            _log(f"  ✗ 文件 {j+1} 下载失败")
                finally:
                    await dlc.close()
            return FeatureResult(True, f"处理 {len(links)} 个链接", log=log, files=files)
        finally:
            await adapter.close()
