<div align="center">
<h1>📥 MediaDownloader</h1>
<p>支持 抖音/TikTok、快手、小红书 的统一媒体下载工具</p>
<p><b>TUI | GUI | Web UI | CLI | API</b></p>
</div>
<hr>

## 📑 功能特性

- ✅ **多平台支持**: 抖音/TikTok、快手、小红书/RedNote
- ✅ **统一 TUI 界面** (Textual)
- ✅ **统一 GUI 界面** (PyWebView)
- ✅ **统一 Web UI** (FastAPI + HTML)
- ✅ **CLI 命令行** (Click)
- ✅ **REST API** (FastAPI)
- ✅ **插件式平台架构** —— 轻松扩展新平台
- ✅ 下载视频、图片、音频文件
- ✅ 批量下载作品
- ✅ 获取账号作品列表
- ✅ 自动跳过已下载文件
- ✅ 多种数据存储格式 (CSV/XLSX/SQLite/JSON)
- ✅ 国际化支持 (中文/English)

## 📸 架构设计

```
MediaDownloader/
├── shared/                    # 公共核心库
│   ├── core/                  # 平台无关的核心逻辑
│   │   ├── adapter.py         # 平台适配器抽象基类
│   │   ├── constants.py       # 共用常量/颜色/签名
│   │   ├── console.py         # 统一 Rich Console
│   │   ├── cleaner.py         # 文件名清理
│   │   ├── retry.py           # 重试机制
│   │   ├── progress.py        # 进度条
│   │   ├── session.py         # HTTP 客户端工厂
│   │   └── ...
│   ├── storage/               # 统一存储层
│   └── translation/           # 国际化
├── platforms/                 # 平台适配器（各自独立）
│   ├── douyin/                # 抖音/TikTok
│   ├── kuaishou/              # 快手
│   └── xiaohongshu/           # 小红书
├── ui/                        # 统一 UI 层
│   ├── tui/                   # Textual TUI
│   ├── gui/                   # PyWebView GUI
│   ├── web/                   # FastAPI Web UI
│   └── cli/                   # Click CLI
├── main.py                    # 统一入口
└── pyproject.toml
```

## 🚀 快速开始

### 源码运行

```bash
# 安装依赖
pip install -r requirements.txt

# GUI 模式 (默认)
python main.py

# TUI 模式
python main.py tui

# Web UI 模式
python main.py web

# CLI 模式
python main.py cli -p douyin -u "https://www.douyin.com/..."
```

### Docker

```bash
# 构建
docker build -t media-downloader .

# 运行 Web 模式
docker run -p 5555:5555 -v media_volume:/app/Volume media-downloader web
```

## 🔧 开发指南

### 添加新平台

1. 在 `platforms/` 下创建新目录
2. 实现 `PlatformAdapter` 抽象接口
3. 使用 `@register_platform("name")` 装饰器注册
4. 完成！

```python
from shared.core import PlatformAdapter, PlatformConfig, DownloadResult
from platforms import register_platform

@register_platform("new_platform")
class NewPlatformAdapter(PlatformAdapter):
    DISPLAY_NAME = "新平台"
    DOMAINS = ["example.com"]

    async def extract_links(self, url: str) -> list[str]: ...
    async def get_detail(self, link: str) -> dict | None: ...
    async def download(self, url: str) -> DownloadResult: ...
    async def download_batch(self, urls: list[str]) -> list[DownloadResult]: ...
    async def get_account_works(self, account_url: str, pages: int = 0) -> list[dict]: ...
    async def close(self): ...
```

## 📋 技术栈

| 组件 | 技术 |
|------|------|
| **TUI** | Textual (基于 Rich) |
| **GUI** | PyWebView + HTML/CSS/JS |
| **Web UI** | FastAPI + Jinja2/SPA |
| **CLI** | Click |
| **HTTP** | curl_cffi (反指纹检测) |
| **数据模型** | Pydantic |
| **异步** | asyncio |
| **存储** | aiosqlite / openpyxl / CSV |
| **国际化** | gettext |

## 📄 开源协议

GNU General Public License v3.0
