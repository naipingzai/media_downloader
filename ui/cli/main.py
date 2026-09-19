"""统一 CLI 入口 —— 支持真实下载。"""
import asyncio
import time

from click import Choice, command, option, pass_context, echo, style

from shared.core import __VERSION__, PROJECT_NAME, REPOSITORY, VOLUME
from shared.core.format import cookie_str_to_dict
from shared.flow.link import LinkExtractor
from shared.flow.download import FileDownloader
from shared.flow.storage import DataStorage
from shared.core.session import create_async_client
from shared.translation import _, switch_language
from platforms import load_all_platforms, list_platforms, get_platform

__all__ = ["cli"]


def read_cookie(path: str = "") -> str:
    import os
    paths = [path, "cookie.txt", os.path.expanduser("~/Project/cookie.txt")]
    for p in paths:
        if p and os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                return f.read().strip()
    return ""


@command(name="MediaDownloader", help=f"{PROJECT_NAME}\n{REPOSITORY}")
@option("--url", "-u", help=_("作品链接"))
@option("--platform", "-p", type=Choice(["douyin", "kuaishou", "xiaohongshu"]), help=_("平台名称"))
@option("--feature", "-f", default="", help=_("功能: dy_hot, dy_detail, dy_account..."))
@option("--cookie", "-ck", default="", help=_("Cookie 文件路径"))
@option("--language", "-l", type=Choice(["zh_CN", "en_US"]), help=_("界面语言"))
@option("--version", "-v", is_flag=True, help=_("显示版本信息"))
@pass_context
def cli(ctx, url, platform, feature, cookie, language, version):
    if version:
        echo(f"{PROJECT_NAME}")
        echo(f"Repository: {REPOSITORY}")
        return
    if language:
        switch_language(language)
    load_all_platforms()
    if platform:
        if feature == "dy_hot":
            asyncio.run(_hot_list(platform, cookie))
        elif url:
            asyncio.run(_download(url, platform, cookie))
        else:
            echo(style("请指定链接: -u <URL>", fg="yellow"))
    elif url:
        echo(style("请指定平台: -p <douyin|kuaishou|xiaohongshu>", fg="yellow"))
    else:
        echo(f"{PROJECT_NAME}")
        echo(f"Repository: {REPOSITORY}")
        echo()
        echo("Usage:")
        echo('  python main.py cli -p douyin -u "https://v.douyin.com/xxx"')
        echo('  python main.py cli -p douyin -f dy_hot')
        echo('  python main.py cli -p kuaishou -u "https://www.kuaishou.com/..."')
        echo('  python main.py cli -p xiaohongshu -u "https://www.xiaohongshu.com/..."')
        echo()
        echo("Features:")
        echo("  dy_hot       采集抖音热榜数据 (无需链接)")
        echo("  dy_detail    批量下载链接作品")
        echo("  dy_account   批量下载账号作品")
        echo()


async def _download(url: str, platform_name: str, cookie_path: str = ""):
    adapter_cls = get_platform(platform_name)
    if not adapter_cls:
        echo(style(f"平台 {platform_name} 未注册", fg="red"))
        return

    cookie = read_cookie(cookie_path)
    adapter = adapter_cls(cookie=cookie)
    save_dir = VOLUME / "Download"
    save_dir.mkdir(parents=True, exist_ok=True)

    echo(style(f"平台: {adapter.DISPLAY_NAME}", fg="green"))
    echo(f"链接: {url}")

    # Step 1: 提取链接
    client = create_async_client(cookie=cookie, impersonate="chrome146")
    try:
        extractor = LinkExtractor(client)
        links = await extractor.run(url, platform=platform_name)
    finally:
        await client.close()

    if not links:
        echo(style("未找到有效链接", fg="red"))
        return

    echo(f"提取到 {len(links)} 个链接")

    # Step 2-3: API 获取详情 + 解析
    results = []
    for link in links:
        echo(f"  处理: {link.link_type.value} id={link.work_id}")
        raw = await adapter.request_detail(link)
        if raw:
            work = adapter.parse_detail(raw)
            if work:
                results.append(work)
                echo(f"    作者: {work['author_name']}, 标题: {work['title'][:40]}")

    if not results:
        echo(style("未获取到任何作品数据", fg="red"))
        return

    # Step 4: 下载文件
    dl_client = create_async_client(cookie=cookie, impersonate="chrome146")
    try:
        dl = FileDownloader(client=dl_client, save_dir=save_dir, max_retry=3)
        for work in results:
            urls = adapter.get_download_urls(work)
            if not urls:
                echo(f"  跳过 {work['work_id']}: 无下载地址")
                continue
            fname = f"{work['work_id']}.mp4"
            echo(f"  下载: {fname}")
            t0 = time.time()
            result = await dl.download_file(urls[0], fname)
            elapsed = time.time() - t0
            if result:
                size = result.stat().st_size
                speed = size / elapsed / 1024 / 1024 if elapsed > 0 else 0
                echo(style(f"    成功: {size/1024/1024:.2f} MB, {elapsed:.1f}s, {speed:.1f} MB/s", fg="green"))
            else:
                echo(style("    失败", fg="red"))
    finally:
        await dl_client.close()

    # Step 5: 保存数据
    storage = DataStorage(save_dir, storage_format="json")
    saved = await storage.save_works(results, "works")
    if saved:
        echo(f"数据已保存: {saved}")

    echo(style("完成!", fg="green"))


async def _hot_list(platform_name: str, cookie_path: str = ""):
    from curl_cffi.requests import AsyncSession
    from shared.core.constants import USERAGENT, IMPERSONATE, PARAMS_HEADERS
    from shared.core.adapter import PlatformConfig
    from platforms.douyin.encrypt import DouYinParams

    adapter_cls = get_platform(platform_name)
    if not adapter_cls:
        echo(style(f"平台 {platform_name} 未注册", fg="red"))
        return

    cookie = read_cookie(cookie_path)
    echo(style(f"平台: {adapter_cls.DISPLAY_NAME}", fg="green"))
    echo("正在获取热榜数据...")

    p = DouYinParams()
    q = {
        "device_platform": "webapp", "aid": "6383", "channel": "channel_pc_web",
        "update_version_code": "170400", "pc_client_type": "1", "pc_libra_divert": "Mac",
        "support_h265": "1", "support_dash": "1", "version_code": "290100",
        "version_name": "29.1.0", "cookie_enabled": "true", "screen_width": "1536",
        "screen_height": "864", "browser_language": "zh-CN", "browser_platform": "MacIntel",
        "browser_name": "Chrome", "browser_version": "146.0.0.0", "browser_online": "true",
        "engine_name": "Blink", "engine_version": "146.0.0.0", "os_name": "Mac OS",
        "os_version": "10.15.7", "cpu_core_num": "16", "device_memory": "8",
        "platform": "PC", "downlink": "10", "effective_type": "4g",
        "round_trip_time": "200", "uifid": "", "msToken": "",
    }
    signed = p.sign_url(
        "https://www.douyin.com/aweme/v1/web/hot/search/list/",
        q, method="GET", user_agent=USERAGENT,
    )
    h = PARAMS_HEADERS.copy()
    h["Cookie"] = cookie

    async with AsyncSession(impersonate=IMPERSONATE) as c:
        r = await c.get(
            f"https://www.douyin.com/aweme/v1/web/hot/search/list/?{signed}",
            headers=h,
        )
        if r.status_code != 200:
            echo(style(f"API 错误: {r.status_code}", fg="red"))
            return
        data = r.json()

    wl = data.get("data", {}).get("word_list", [])
    if not wl:
        echo(style("热榜数据为空", fg="yellow"))
        return

    echo(style("=== 抖音热榜 TOP 20 ===", fg="green"))
    results = []
    for i, it in enumerate(wl[:20]):
        rank = i + 1
        word = it.get("word", "")
        hot_value = it.get("hot_value", 0)
        results.append({"rank": rank, "word": word, "hot_value": hot_value})
        echo(f"  #{rank} {word} (热度: {hot_value})")

    save_dir = VOLUME / platform_name
    save_dir.mkdir(parents=True, exist_ok=True)
    st = DataStorage(save_dir, storage_format="json")
    saved = await st.save_works(results, "hot_list")
    if saved:
        echo(f"数据已保存: {saved}")

    echo(style("完成!", fg="green"))
