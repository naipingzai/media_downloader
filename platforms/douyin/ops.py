"""抖音平台操作表 —— 完全自包含。"""
import asyncio
import time
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
        FeatureMeta("collection_album", "批量下载收藏专辑", True),
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

    # ---- 批量列表缓存：预览→选择→下载 两阶段避免重复翻页 ----
    _CACHE_TTL = 1800  # 秒

    def _cache_get(self, key: str):
        ent = getattr(self, "_list_cache", {}).get(key)
        if ent and time.time() - ent[0] < self._CACHE_TTL:
            return ent[1]
        return None

    def _cache_put(self, key: str, items: list):
        if not hasattr(self, "_list_cache"):
            self._list_cache = {}
        self._list_cache[key] = (time.time(), items)

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
                _log(f"  {work['author_name']}: {work['title'][:40]}")
                urls = adapter.get_download_urls(work)
                if not urls:
                    _log("  无下载地址"); continue
                target = storage.resolve(work)
                dlc = create_async_client()
                try:
                    dl = FileDownloader(client=dlc, save_dir=target.parent)
                    result = await dl.download_file(urls[0], target.name)
                finally:
                    await dlc.close()
                if result:
                    _log(f"  ✓ {result}")
                    storage.record_download(link.work_id)
                    files.append(str(result))
                else:
                    _log("  ✗ 下载失败")
            return FeatureResult(True, f"处理 {len(links)} 个链接", log=log, files=files)
        finally:
            await adapter.close()

    async def _do_account(self, url, cookie, save_dir, selected=None) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            sec_uid = await self._resolve_sec_uid(adapter, url)
            if not sec_uid:
                return FeatureResult(False, "无法获取用户信息，请输入用户主页链接")
            cache_key = f"dy_account:{sec_uid}"
            all_awemes = self._cache_get(cache_key)
            if all_awemes is None:
                # 分页获取所有作品
                all_awemes = []
                max_cursor = "0"
                for _ in range(50):  # 最多50页
                    data = await adapter.fetch_user_posts(sec_uid, count=20, max_cursor=max_cursor)
                    if not data:
                        break
                    awemes = data.get("aweme_list") or []
                    if not awemes:
                        break
                    all_awemes.extend(awemes)
                    if not data.get("has_more", False):
                        break
                    max_cursor = str(data.get("max_cursor") or "")
                    if not max_cursor:
                        break
                if not all_awemes:
                    return FeatureResult(False, "获取作品列表失败或为空")
                self._cache_put(cache_key, all_awemes)
            return await self._batch_download(adapter, all_awemes, storage,
                                              selected=selected)
        finally:
            await adapter.close()

    async def _do_mix(self, url, cookie, save_dir, selected=None) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            mix_id = self._extract_mix_id(url)
            if not mix_id:
                return FeatureResult(False, "无法提取合集 ID，请输入合集链接")
            aweme_list = self._cache_get(f"dy_mix:{mix_id}")
            if aweme_list is None:
                aweme_list = await self._fetch_mix_awemes(adapter, mix_id)
                if not aweme_list:
                    return FeatureResult(False, "获取合集失败或合集为空")
                self._cache_put(f"dy_mix:{mix_id}", aweme_list)
            return await self._batch_download(adapter, aweme_list, storage,
                                              selected=selected)
        finally:
            await adapter.close()

    async def _do_collection(self, url, cookie, save_dir, selected=None) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            aweme_list = self._cache_get("dy_collection:me")
            if aweme_list is None:
                aweme_list = []
                cursor = "0"
                for _ in range(50):
                    data = await adapter.fetch_collection(cursor=cursor, count=20)
                    if not data:
                        break
                    awemes = data.get("aweme_list") or []
                    if not awemes:
                        break
                    aweme_list.extend(awemes)
                    if not data.get("has_more"):
                        break
                    cursor = str(data.get("cursor") or "0")
                    if cursor == "0":
                        break
                if not aweme_list:
                    if not cookie:
                        return FeatureResult(False, "获取收藏失败：收藏功能需要登录，请先配置抖音 Cookie")
                    return FeatureResult(False, "获取收藏失败或收藏为空（Cookie 可能已失效）")
                self._cache_put("dy_collection:me", aweme_list)
            return await self._batch_download(adapter, aweme_list, storage,
                                              selected=selected)
        finally:
            await adapter.close()

    async def _do_collection_album(self, url, cookie, save_dir, selected=None) -> FeatureResult:
        """批量下载收藏专辑（「我的收藏 → 专辑」里的合集）。

        url 留空 = 全部收藏专辑；填合集链接或 mix_id = 只下载该专辑。
        """
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            # 指定了单个专辑 → 直接按合集处理
            direct_mix = self._extract_mix_id(url) if url.strip() else ""
            if direct_mix:
                aweme_list = await self._fetch_mix_awemes(adapter, direct_mix)
                if not aweme_list:
                    return FeatureResult(False, "获取专辑作品失败或专辑为空")
                items = [self._aweme_preview(aw) for aw in aweme_list]
                return await self._batch_download(adapter, aweme_list, storage,
                                                  selected=selected,
                                                  preview_items=items)
            cache_key = "dy_collection_album:me"
            aweme_list = self._cache_get(cache_key)
            preview_items = None
            if aweme_list is None:
                # 1) 拉收藏的专辑列表
                albums, cursor = [], "0"
                for _ in range(10):
                    data = await adapter.fetch_collection_albums(cursor=cursor, count=20)
                    if not data:
                        break
                    mix_list = (data.get("mix_list")
                                or (data.get("data") or {}).get("mix_list")
                                or data.get("medias") or [])
                    if not mix_list:
                        break
                    albums.extend(mix_list)
                    if not data.get("has_more"):
                        break
                    cursor = str(data.get("cursor") or "0")
                    if cursor == "0":
                        break
                if not albums:
                    if not cookie:
                        return FeatureResult(False, "获取收藏专辑失败：需要登录，请先配置抖音 Cookie")
                    return FeatureResult(False, "获取收藏专辑失败或为空（Cookie 可能已失效）")
                # 2) 逐专辑拉作品（flatten），带上所属专辑名
                aweme_list, preview_items = [], []
                for al in albums[:30]:
                    mix_id = str(al.get("mix_id") or al.get("id") or "")
                    name = str(al.get("name") or al.get("mix_name") or "")
                    if not mix_id:
                        continue
                    aws = await self._fetch_mix_awemes(adapter, mix_id, max_pages=20)
                    for aw in aws:
                        aw["_mix_name"] = name
                        aweme_list.append(aw)
                        preview_items.append(self._aweme_preview(aw, extra=name))
                    if len(aweme_list) >= 3000:  # 上限保护
                        break
                if not aweme_list:
                    return FeatureResult(False, "收藏专辑中没有作品")
                self._cache_put(cache_key, aweme_list)
            return await self._batch_download(adapter, aweme_list, storage,
                                              selected=selected,
                                              preview_items=preview_items)
        finally:
            await adapter.close()

    async def _do_live(self, url, cookie, save_dir, stop_event=None) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url.strip())
            room_id = parsed.path.rstrip("/").split("/")[-1]
            if room_id.isdigit() and len(room_id) <= 14:
                pass  # web_rid 短号
            elif room_id and any(c.isalpha() for c in room_id) and len(room_id) >= 15:
                pass  # 混合长 ID（feed 接口的 id_str），直接作为 room_id_str
            else:
                # fallback: 取所有数字
                from re import findall
                nums = findall(r"\d{10,}", url)
                room_id = nums[0] if nums else room_id
            if not room_id:
                return FeatureResult(False, "无法从链接提取房间号")
            # 纯数字短号走 web_rid；混合长 ID（如 feed 接口的 id_str）走 room_id_str
            is_web_rid = room_id.isdigit() and len(room_id) <= 14
            log = [f"正在获取直播间信息 ({'web_rid' if is_web_rid else 'room_id_str'}={room_id})..."]
            data = await adapter.fetch_live(
                room_id if is_web_rid else "",
                room_id_str="" if is_web_rid else room_id)
            if not data:
                log.append("  ✗ 获取直播信息失败")
                return FeatureResult(False, "获取直播信息失败", log=log)
            room_list = data.get("data", {}).get("data", [])
            if not room_list:
                log.append("  ✗ 房间不存在或查询结果为空")
                return FeatureResult(False, "房间不存在", log=log)
            room = room_list[0]
            title = room.get("title", "")
            owner = room.get("owner", {}).get("nickname", "")
            status = room.get("status", 0)
            stream = room.get("stream_url", {})
            log.append(f"  主播: {owner}")
            log.append(f"  标题: {title}")
            log.append(f"  状态: {'直播中' if status == 2 else '未开播'}")

            # 选择最佳流地址（FLV 优先，录制更稳定）
            stream_url = ""
            stream_type = ""
            # 实际字段: flv_pull_url 本身就是 dict；hls_pull_url_map 为 dict
            flv_map = stream.get("flv_pull_url_map") or stream.get("flv_pull_url") or {}
            hls_map = stream.get("hls_pull_url_map") or {}
            if isinstance(flv_map, str):
                flv_map = {"origin": flv_map} if flv_map else {}
            if isinstance(hls_map, str):
                hls_map = {"origin": hls_map} if hls_map else {}
            qualitys = ["origin", "uhd", "full_hd", "FULL_HD1", "hd", "HD1", "sd", "SD1"]
            for q in qualitys:
                if q in flv_map:
                    stream_url, stream_type = flv_map[q], "FLV"
                    break
            if not stream_url:
                for q in qualitys:
                    if q in hls_map:
                        stream_url, stream_type = hls_map[q], "HLS"
                        break
            if not stream_url and flv_map:
                stream_url, stream_type = next(iter(flv_map.values())), "FLV"
            if not stream_url and hls_map:
                stream_url, stream_type = next(iter(hls_map.values())), "HLS"
            if not stream_url:
                log.append("  ✗ 未获取到直播流地址")
                return FeatureResult(False, "未获取到直播流", log=log)

            log.append(f"  流类型: {stream_type}")
            log.append(f"  流地址: {stream_url[:100]}...")

            # 保存流信息
            await storage.save_data([{"room_id": room_id, "owner": owner, "title": title,
                "status": status, "stream_type": stream_type, "stream_url": stream_url,
                "hls": dict(hls_map), "flv": dict(flv_map)}], f"live_{room_id}")

            # 使用 FFmpeg 录制
            from shared.core.ffmpeg import FFmpegManager
            exe = FFmpegManager.find_executable()
            if not exe:
                log.append("  ✗ FFmpeg 未安装，仅保存流地址")
                return FeatureResult(True, f"直播流已保存: {owner}", log=log,
                    data=[{"room_id": room_id, "owner": owner, "title": title, "stream_url": stream_url}])

            target = storage.resolve({"platform": "douyin", "work_id": room_id,
                                       "title": f"直播_{owner}_{title}"[:60], "author_name": owner})
            output_path = str(target.with_suffix(".ts"))
            log.append(f"  开始录制 → {target.name}")
            log.append(f"  FFmpeg: {exe}")

            import subprocess
            cmd = [
                str(exe), "-y",
                "-headers", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\nReferer: https://live.douyin.com/\r\n",
                "-i", stream_url,
                "-c", "copy",
                "-f", "mpegts",
                output_path,
            ]
            log.append(f"  录制中... (点击「停止录制」结束)")

            try:
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                # 无时长上限，持续录制直到 stop_event 被设置
                import time
                start = time.time()
                while process.poll() is None:
                    if stop_event is not None and stop_event.is_set():
                        process.terminate()
                        break
                    await asyncio.sleep(1)

                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)

                elapsed = int(time.time() - start)
                from pathlib import Path as P
                fsize = P(output_path).stat().st_size if P(output_path).exists() else 0
                fsize_mb = fsize / (1024 * 1024)
                log.append(f"  ✓ 录制完成: {elapsed}秒, {fsize_mb:.1f}MB")
                log.append(f"  文件: {output_path}")
                return FeatureResult(True, f"直播录制完成: {owner} ({elapsed}秒, {fsize_mb:.1f}MB)",
                    log=log, files=[output_path])
            except Exception as e:
                log.append(f"  ✗ 录制异常: {e}")
                return FeatureResult(False, f"录制失败: {e}", log=log)

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

    async def _batch_download(self, adapter, aweme_list, storage,
                              selected=None, preview_items=None):
        """批量下载入口。selected=None → 第一阶段只返回预览；否则下载勾选项。"""
        if selected is None:
            items = preview_items if preview_items is not None else [
                self._aweme_preview(aw) for aw in aweme_list]
            if not items:
                return FeatureResult(False, "作品列表为空")
            return FeatureResult(True, f"共 {len(items)} 个作品，待选择下载",
                                 data=items, preview="batch")
        # 第二阶段：按勾选的 work_id 过滤下载
        sel = {str(s) for s in selected}
        targets = [aw for aw in aweme_list
                   if str(aw.get("aweme_id", "")) in sel]
        if not targets:
            return FeatureResult(False, "未匹配到勾选的作品（列表可能已过期，请重新执行）")
        from shared.flow.download import FileDownloader
        from shared.core.session import create_async_client
        log, files = [], []
        for i, aw in enumerate(targets, 1):
            aweme_id = aw.get("aweme_id", "")
            desc = aw.get("desc", "")[:40]
            author = aw.get("author", {}).get("nickname", "unknown")
            work = {
                "platform": "douyin", "work_id": aweme_id,
                "title": desc or "untitled", "author_name": author,
            }
            msg = f"  [{i}/{len(targets)}] {author}: {desc}"
            log.append(msg); self.log(msg)
            video = aw.get("video", {})
            play = video.get("play_addr", {}).get("url_list", [])
            bit_rate = video.get("bit_rate", [])
            if bit_rate:
                best = max(bit_rate, key=lambda x: x.get("bit_rate", 0))
                play = best.get("play_addr", {}).get("url_list", []) or play
            if not play:
                msg = "    无下载地址"; log.append(msg); self.log(msg); continue
            target = storage.resolve(work)
            dlc = create_async_client()
            try:
                dl = FileDownloader(client=dlc, save_dir=target.parent)
                result = await dl.download_file(play[0], target.name)
                if result:
                    msg = f"    ✓ {target.name}"
                    log.append(msg); self.log(msg)
                    storage.record_download(aweme_id)
                    files.append(str(result))
                else:
                    msg = "    ✗ 下载失败"; log.append(msg); self.log(msg)
            finally:
                await dlc.close()
        return FeatureResult(True, f"批量下载 {len(files)}/{len(targets)} 个",
                             log=log, files=files)

    @staticmethod
    def _aweme_preview(aw: dict, extra: str = "") -> dict:
        """aweme dict → 预览条目（封面/标题/作者/时长/点赞）。"""
        author = aw.get("author") or {}
        video = aw.get("video") or {}
        cover = ""
        for key in ("cover", "origin_cover", "dynamic_cover"):
            c = video.get(key)
            if isinstance(c, dict):
                urls = c.get("url_list") or []
                if urls:
                    cover = urls[0]
                    break
        try:
            duration = int(video.get("duration") or 0) // 1000
        except (TypeError, ValueError):
            duration = 0
        return {
            "platform": "douyin",
            "work_id": str(aw.get("aweme_id") or ""),
            "title": aw.get("desc") or "",
            "author_name": author.get("nickname", ""),
            "cover": cover,
            "duration": duration,
            "digg_count": (aw.get("statistics") or {}).get("digg_count", 0),
            "extra": extra or aw.get("_mix_name", ""),
        }

    @staticmethod
    def _extract_mix_id(url: str) -> str:
        """从合集链接/纯 ID 提取 mix_id。"""
        url = (url or "").strip()
        if not url:
            return ""
        if "mix_id=" in url:
            return url.split("mix_id=")[-1].split("&")[0].split("?")[0]
        s = url.rstrip("/").split("/")[-1].split("?")[0]
        if s.isdigit():
            return s
        from re import search
        m = search(r"mix/(\d+)", url)
        return m.group(1) if m else ""

    async def _fetch_mix_awemes(self, adapter, mix_id: str, max_pages: int = 50) -> list:
        """分页抓取单个合集的全部作品。"""
        aweme_list, cursor = [], 0
        for _ in range(max_pages):
            data = await adapter.fetch_mix(mix_id, count=20, cursor=cursor)
            if not data:
                break
            awemes = data.get("aweme_list") or []
            if not awemes:
                break
            aweme_list.extend(awemes)
            if not data.get("has_more"):
                break
            cursor = int(data.get("cursor") or 0)
            if not cursor:
                break
        return aweme_list

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
