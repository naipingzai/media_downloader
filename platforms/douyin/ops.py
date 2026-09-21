"""抖音平台操作表 —— 完全自包含。"""
import asyncio
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

    async def _do_account(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("douyin")
        try:
            sec_uid = await self._resolve_sec_uid(adapter, url)
            if not sec_uid:
                return FeatureResult(False, "无法获取用户信息，请输入用户主页链接")
            # 分页获取所有作品
            all_awemes = []
            max_cursor = "0"
            for _ in range(50):  # 最多50页
                data = await adapter.fetch_user_posts(sec_uid, count=20, max_cursor=max_cursor)
                if not data:
                    break
                awemes = data.get("aweme_list", [])
                if not awemes:
                    break
                all_awemes.extend(awemes)
                if not data.get("has_more", False):
                    break
                max_cursor = str(data.get("max_cursor", ""))
            if not all_awemes:
                return FeatureResult(False, "获取作品列表失败或为空")
            return await self._batch_download(adapter, all_awemes, storage)
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
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url.strip())
            room_id = parsed.path.rstrip("/").split("/")[-1]
            if not room_id.isdigit():
                # fallback: 取所有数字
                from re import findall
                nums = findall(r"\d{10,}", url)
                room_id = nums[0] if nums else room_id
            log = [f"正在获取直播间信息 (room_id={room_id})..."]
            data = await adapter.fetch_live(room_id)
            if not data:
                log.append("  ✗ 获取直播信息失败")
                return FeatureResult(False, "获取直播信息失败", log=log)
            room_list = data.get("data", {}).get("data", [])
            room = room_list[0] if room_list else {}
            title = room.get("title", "")
            owner = room.get("owner", {}).get("nickname", "")
            status = room.get("status", 0)
            stream = room.get("stream_url", {})
            log.append(f"  主播: {owner}")
            log.append(f"  标题: {title}")
            log.append(f"  状态: {'直播中' if status == 2 else '未开播'}")

            # 选择最佳流地址
            stream_url = ""
            stream_type = ""
            hls_map = stream.get("hls_pull_url_map", {})
            flv_map = stream.get("flv_pull_url_map", {})
            for q in ["origin", "uhd", "hd", "sd"]:
                if q in hls_map:
                    stream_url = hls_map[q]
                    stream_type = "HLS"
                    break
            if not stream_url:
                for q in ["origin", "uhd", "hd", "sd"]:
                    if q in flv_map:
                        stream_url = flv_map[q]
                        stream_type = "FLV"
                        break
            if not stream_url and hls_map:
                stream_url = list(hls_map.values())[0]
                stream_type = "HLS"
            if not stream_url and flv_map:
                stream_url = list(flv_map.values())[0]
                stream_type = "FLV"
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
                "-headers", f"User-Agent: Mozilla/5.0\\r\\nReferer: https://www.douyin.com/\\r\\n",
                "-i", stream_url,
                "-c", "copy",
                "-f", "mpegts",
                output_path,
            ]
            log.append(f"  录制中... (Ctrl+C 可停止)")

            try:
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                # 等待一段时间录制 (30秒用于测试，实际可设更长)
                import time
                start = time.time()
                record_seconds = 30
                while process.poll() is None and (time.time() - start) < record_seconds:
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
                author = aw.get("author", {}).get("nickname", "unknown")
                work = {
                    "platform": "douyin", "work_id": aweme_id,
                    "title": desc or "untitled", "author_name": author,
                }
                msg = f"  [{i}/{len(aweme_list)}] {author}: {desc}"
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
