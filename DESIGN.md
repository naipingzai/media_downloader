# MediaDownloader - 功能清单与工程流程

基于三个原工程 (TikTokDownloader V5.8 / KS-Downloader V1.7 / XHS-Downloader V2.8) 的实际代码梳理。

---

## 一、功能清单

### 1. 输入方式

每个功能都支持以下 3 种输入来源：

| 输入方式 | 说明 |
|---------|------|
| **手动输入** | 用户在终端/界面粘贴链接，支持多个空格分隔 |
| **文本文档** | 用户提供 .txt 文件路径，程序逐行读取链接 |
| **配置文件** | 在 settings.json / config.yaml 中预设链接列表，程序启动后自动读取 |

### 1.1 抖音/TikTok 功能 (15个)

| # | 功能 | 说明 |
|---|------|------|
| 1 | 批量下载账号作品 | 输入账号主页链接 -> 遍历下载该账号全部发布的作品 |
| 2 | 批量下载链接作品 | 输入一个或多个作品链接 -> 批量下载 |
| 3 | 获取直播拉流地址 | 输入直播间链接 -> 获取 FLV/HLS 拉流地址 |
| 4 | 采集作品评论数据 | 输入作品链接 -> 采集评论 -> 存储为数据文件 |
| 5 | 批量下载合集作品 | 输入合集/播放列表链接 -> 遍历下载全部作品 |
| 6 | 采集账号详细数据 | 输入账号链接 -> 采集账号资料(头像/签名/作品数等) -> 存储 |
| 7 | 采集搜索结果数据 | 输入关键词 -> 支持4种搜索类型：综合/视频/用户/直播 |
| 8 | 采集抖音热榜数据 | 一键采集当前抖音热榜(热搜/视频榜/音乐榜等) |
| 9 | 批量下载收藏作品 | 需登录Cookie -> 下载当前账号收藏的作品 |
| 10 | 批量下载收藏音乐 | 需登录Cookie -> 下载收藏的音乐文件 |
| 11 | 批量下载收藏夹作品 | 需登录Cookie -> 下载自定义收藏夹内作品 |
| 12 | 批量下载账号作品(TikTok) | 与抖音相同，面向TikTok国际版 |
| 13 | 批量下载链接作品(TikTok) | 与抖音相同，面向TikTok国际版 |
| 14 | 批量下载合集作品(TikTok) | 与抖音相同，面向TikTok国际版 |
| 15 | 获取直播拉流地址(TikTok) | 与抖音相同，面向TikTok国际版 |

### 1.2 快手功能 (2个)

| # | 功能 | 说明 |
|---|------|------|
| 1 | 批量下载账号作品 | 输入快手账号链接 -> 遍历下载全部作品 |
| 2 | 批量下载链接作品 | 输入一个或多个作品链接 -> 批量下载 |

### 1.3 小红书/RedNote 功能 (2个)

| # | 功能 | 说明 |
|---|------|------|
| 1 | 下载作品文件 | 输入作品链接 -> 下载视频/图文/livePhoto |
| 2 | 剪贴板监听下载 | 后台监听剪贴板 -> 自动识别小红书链接并下载 |

### 1.4 通用功能 (三平台共享, 14个)

| # | 功能 | 说明 |
|---|------|------|
| 1 | Cookie 管理 | 手动输入 / 从剪贴板读取 / 自动更新 |
| 2 | 短链接解析 | 短链(v.douyin.com等) -> HTTP重定向 -> 长链 -> 提取ID |
| 3 | 跳过已下载 | 记录已下载作品ID -> 重复运行时自动跳过 |
| 4 | 多线程下载 | asyncio.Semaphore 控制并发数(默认4) |
| 5 | 断点续传 | HTTP Range 请求，支持中断后继续下载 |
| 6 | 文件完整性校验 | 文件头签名检测(JPEG/PNG/MP4等14种格式) |
| 7 | 代理支持 | HTTP代理，自动测试代理可用性 |
| 8 | 文件夹归档 | 按作者昵称/作品类型归档保存 |
| 9 | 自定义文件名 | 支持变量：create_time / type / nickname / desc / mark 等 |
| 10 | 数据持久化 | 采集数据存储为 CSV / XLSX / SQLite / JSON |
| 11 | 国际化 | 中文 / English (gettext) |
| 12 | 剪贴板监听 | 后台自动检测剪贴板中的链接 -> 自动下载 |
| 13 | 版本检查 | 检查GitHub Releases是否有新版本 |
| 14 | 免责声明 | 首次运行显示免责声明，需确认后继续 |

---

## 二、工程流程

### 2.1 核心 Pipeline

所有平台共享同一条处理流水线，差异仅在各平台适配器中实现：

```
用户输入 (URL / 文本 / 配置文件)
    |
    v
+----------------------------------+
| Step 1: LINK EXTRACTION          | shared/flow/link.py
|   短链 -> HTTP 302重定向 -> 长链  |
|   正则匹配(各平台不同)           |
|   输出: ExtractedLink            |
|     {url, link_type, platform,   |
|      work_id, user_id, mix_id}  |
+----------------+-----------------+
                 |
                 v
+----------------------------------+
| Step 2: API REQUEST              | shared/flow/request.py
|   构建请求参数(device_id等)       |
|   加密签名(aBogus/X-Bogus等)     |
|   curl_cffi发送 + 自动重试       |
|   输出: 原始 JSON 响应           |
+----------------+-----------------+
                 |
                 v
+----------------------------------+
| Step 3: DATA EXTRACTION          | shared/flow/extract.py
|   字段映射(各平台不同)           |
|   数据清洗 + 格式化              |
|   输出: WorkData                 |
|     {platform, work_id, title,   |
|      author, video_url, ...}    |
+----------------+-----------------+
                 |
                 v
+----------------------------------+
| Step 4: FILE DOWNLOAD            | shared/flow/download.py
|   检查已下载(跳过)               |
|   多线程并发 + 流式写入          |
|   进度条(Rich Progress)          |
|   完整性校验 + 失败重试          |
|   输出: 下载文件路径             |
+----------------+-----------------+
                 |
                 v
+----------------------------------+
| Step 5: DATA STORAGE             | shared/flow/storage.py
|   保存元数据(CSV/XLSX/SQL/JSON)  |
|   记录已下载ID(防重复)           |
|   输出: 持久化文件               |
+----------------+-----------------+
                 |
                 v
           输出到 UI
```

### 2.2 各层职责

| 层 | 文件 | 职责 | 关键类 |
|----|------|------|--------|
| 1. 链接提取 | shared/flow/link.py | 短链解析 + 正则匹配 + ID提取 + 类型分类 | LinkExtractor / ExtractedLink / LinkType |
| 2. API请求 | shared/flow/request.py | HTTP请求 + 加密签名 + 重试 | APIRequester |
| 3. 数据提取 | shared/flow/extract.py | JSON解析 + 字段映射 + 数据清洗 | DataExtractor / WorkData |
| 4. 文件下载 | shared/flow/download.py | 并发控制 + 流式下载 + 进度条 + 校验 | FileDownloader |
| 5. 数据存储 | shared/flow/storage.py | 格式化输出 + 持久化 + 下载记录 | DataStorage |
| 控制台 | shared/core/console.py | 彩色终端输出 + 用户输入 | ColorfulConsole |
| 重试 | shared/core/retry.py | 指数退避异步重试 | Retry |
| 清理 | shared/core/cleaner.py | 文件名非法字符清理 | Cleaner |
| HTTP客户端 | shared/core/session.py | curl_cffi 客户端工厂 | create_async_client |
| 文件签名 | shared/core/file_signature.py | 文件头字节检测(14种格式) | FileSignature |
| 平台适配器 | platforms/{name}/adapter.py | 平台特定的链接/API/数据逻辑 | XxxAdapter |

### 2.3 平台适配器接口

```python
class PlatformAdapter(ABC):
    async def extract_links(self, text: str) -> list[ExtractedLink]: ...
    async def request_detail(self, link: ExtractedLink) -> dict: ...
    def parse_detail(self, raw: dict) -> WorkData: ...
    def get_download_urls(self, work: WorkData) -> list[str]: ...
    async def get_account_works(self, user_id: str, pages: int) -> list[WorkData]: ...
    async def close(self): ...
```

### 2.4 界面模式

| 模式 | 入口 | 技术栈 | 适合场景 |
|------|------|--------|----------|
| GUI | python main.py | PyWebView + HTML | 普通用户，桌面环境 |
| TUI | python main.py tui | Textual | SSH/远程终端 |
| Web | python main.py web | FastAPI + HTML | 局域网/远程浏览器 |
| API | python main.py api | FastAPI | 程序调用/自动化 |
| CLI | python main.py cli | Click | 脚本/命令行 |

---

## 三、文件结构

```
MediaDownloader/
+-- shared/
|   +-- core/
|   |   +-- constants.py      # 版本/路径/颜色/签名
|   |   +-- console.py        # Rich 彩色控制台
|   |   +-- cleaner.py        # 文件名清理
|   |   +-- retry.py          # 异步重试
|   |   +-- session.py        # HTTP 客户端工厂
|   |   +-- format.py         # Cookie转换/文件大小
|   |   +-- error.py          # 自定义异常
|   |   +-- progress.py       # 进度条封装
|   |   +-- file_signature.py # 文件头签名检测
|   +-- flow/
|       +-- link.py           # Step1: 链接提取
|       +-- request.py        # Step2: API请求
|       +-- extract.py        # Step3: 数据提取
|       +-- download.py       # Step4: 文件下载
|       +-- storage.py        # Step5: 数据存储
+-- platforms/
|   +-- douyin/adapter.py     # 抖音/TikTok (15个功能)
|   +-- kuaishou/adapter.py   # 快手 (2个功能)
|   +-- xiaohongshu/adapter.py# 小红书 (2个功能)
+-- ui/
|   +-- tui/                  # Textual TUI
|   +-- gui/                  # PyWebView GUI
|   +-- web/                  # FastAPI Web
|   +-- cli/                  # Click CLI
+-- main.py                   # 统一入口
+-- DESIGN.md                 # 本文档
+-- pyproject.toml
```

---

## 四、配置参数 (通用)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| root | str | "" | 作品文件保存根路径 |
| folder_name | str | "Download" | 文件夹名称 |
| name_format | str | "create_time type nickname desc" | 文件名格式 |
| desc_length | int | 64 | 描述最大长度 |
| name_length | int | 128 | 文件名最大长度 |
| date_format | str | "%Y-%m-%d %H:%M:%S" | 日期格式 |
| split | str | "-" | 文件名分隔符 |
| folder_mode | bool | False | 是否按作品类型分文件夹 |
| music | bool | False | 是否下载背景音乐 |
| storage_format | str | "" | 数据存储格式: csv/xlsx/sql/json |
| download | bool | True | 是否下载文件 |
| chunk | int | 2097152 | 下载分块大小 |
| timeout | int | 10 | 请求超时(秒) |
| max_retry | int | 5 | 最大重试次数 |
| proxy | str | "" | HTTP代理地址 |
| impersonate | str | "chrome146" | 浏览器模拟目标 |
| cookie | str | "" | 平台Cookie |
