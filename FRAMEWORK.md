# MediaDownloader 框架设计文档

## 一、设计目标

1. **平台完全隔离** — douyin / kuaishou / xiaohongshu 各自独立目录，互不引用
2. **OPS 操作表** — 功能、存储、Cookie 全部抽象为操作表，注册后由总线调度
3. **UI 无知化** — UI 只读 OPS 注册信息 + 调总线，零业务逻辑
4. **存储可配置** — 用户选择存储模式，框架按模式组织目录和文件
5. **插件化扩展** — 新增平台只需创建目录 + 实现 OPS + 注册，不改任何已有代码

---

## 二、目录结构

```
MediaDownloader/
│
├── shared/                          # 公共内核
│   ├── core/
│   │   ├── ops.py                   # ★ 平台总线 + PlatformOps + FeatureResult
│   │   ├── storage.py               # ★ 存储 OPS + StorageConfig
│   │   ├── config.py                # ★ 全局配置
│   │   ├── adapter.py               #   PlatformAdapter ABC
│   │   ├── session.py               #   HTTP 客户端工厂
│   │   ├── constants.py             #   常量
│   │   ├── cookies.py               #   CookieManager
│   │   └── format.py                #   格式化工具
│   └── flow/
│       ├── link.py                  #   链接提取
│       ├── download.py              #   文件下载器
│       └── request.py               #   API 请求基类
│
├── platforms/                       # ★ 平台层（完全隔离）
│   ├── douyin/
│   │   ├── __init__.py              #   register(DouyinOps())
│   │   ├── ops.py                   #   ★ 9 个功能实现
│   │   ├── adapter.py               #   底层 API
│   │   ├── encrypt/                 #   加密模块
│   │   └── api.py                   #   API 客户端
│   ├── kuaishou/
│   │   ├── __init__.py              #   register(KuaishouOps())
│   │   ├── ops.py                   #   ★ 功能实现
│   │   └── adapter.py               #   底层 API
│   └── xiaohongshu/
│       ├── __init__.py              #   register(XiaohongshuOps())
│       ├── ops.py                   #   ★ 功能实现
│       └── adapter.py               #   底层 API
│
├── ui/                              # UI 层（只调总线，零业务逻辑）
│   ├── tui/screens/index.py
│   ├── gui/backend.py
│   ├── web/app.py
│   └── cli/main.py
│
├── Volume/                          # 用户数据
│   ├── config.json                  #   全局配置
│   ├── cookies.json                 #   Cookie
│   ├── douyin/
│   ├── kuaishou/
│   └── xiaohongshu/
└── main.py
```

---

## 三、核心接口

### 3.1 FeatureResult — 统一结果

```python
@dataclass
class FeatureResult:
    success: bool
    message: str
    data: list[dict] | None = None
    log: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
```

### 3.2 FeatureMeta — 功能元数据

```python
@dataclass(frozen=True)
class FeatureMeta:
    id: str           # "download" / "hot"
    name: str         # "下载单个作品"
    need_url: bool    # 是否需要输入
```

### 3.3 PlatformOps — 平台操作表接口

```python
class PlatformOps(ABC):
    platform_id: str = ""
    display_name: str = ""
    cookie_hint: str = ""        # 空字符串 = 不显示 cookie 输入
    features: list[FeatureMeta] = []

    async def execute(self, feature_id, url, cookie, save_dir) -> FeatureResult:
        method = getattr(self, f"_do_{feature_id}", None)
        if method is None:
            return FeatureResult(False, f"功能 {feature_id} 未实现")
        return await method(url, cookie, save_dir)

    # 子类实现: _do_download / _do_hot / _do_account / ...
```

### 3.4 StorageOps — 存储操作表

```python
@dataclass
class StorageConfig:
    mode: str = "flat"         # flat / by_author / by_date / by_type
    data_format: str = "json"  # json / csv / xlsx / sql
    dedup: bool = True

class StorageOps:
    def __init__(self, platform: str, config: StorageConfig):
        self.platform = platform
        self.config = config
        self.base_dir = VOLUME / platform

    def resolve_dir(self, work: dict) -> Path:
        """根据存储模式确定文件所在目录。"""
        match self.config.mode:
            case "flat":
                return self.base_dir
            case "by_author":
                return self.base_dir / safe_name(work.get("author_name", "unknown"))
            case "by_date":
                return self.base_dir / format_date(work.get("create_time", 0))
            case "by_type":
                return self.base_dir / ("video" if work.get("video_url") else "image")

    def resolve_filename(self, work: dict) -> str:
        """生成文件名: 作者名_动态描述.格式 (参考 TikTokDownloader / XHS-Downloader)"""
        author = safe_name(work.get("author_name", "unknown"))
        desc = safe_name(work.get("title", "untitled"))
        ext = detect_extension(work)
        return f"{author}_{desc}.{ext}"

    def resolve(self, work: dict) -> Path:
        """完整路径 = 目录 + 文件名。"""
        return self.resolve_dir(work) / self.resolve_filename(work)

    async def save_data(self, data: list[dict], name: str) -> str | None: ...
    def is_downloaded(self, work_id: str) -> bool: ...
    def record_download(self, work_id: str): ...
```

文件命名规则（参考 TikTokDownloader / XHS-Downloader）:
```
格式: {作者名}_{动态描述}.{扩展名}

示例:
  张三_今天天气真好.mp4
  李四_美食探店合集.mp4
  王五_周末vlog.jpg
```

目录模式对比（以下载张三的作品 "今天天气真好.mp4" 为例）:
```
flat:       Volume/douyin/张三_今天天气真好.mp4
by_author:  Volume/douyin/张三/张三_今天天气真好.mp4
by_date:    Volume/douyin/2026-09-19/张三_今天天气真好.mp4
by_type:    Volume/douyin/video/张三_今天天气真好.mp4
```

采集类数据（热榜/评论/搜索）不走文件命名，直接保存为:
```
Volume/{platform}/hot_list.json
Volume/{platform}/comments_{aweme_id}.json
Volume/{platform}/search_results.json
```

### 3.5 PlatformBus — 平台总线

```python
class PlatformBus:
    _registry: dict[str, PlatformOps] = {}

    @classmethod
    def register(cls, ops: PlatformOps): cls._registry[ops.platform_id] = ops
    @classmethod
    def get_ops(cls, platform: str) -> PlatformOps | None: ...
    @classmethod
    def list_platforms(cls) -> list[str]: ...
    @classmethod
    def get_features(cls, platform: str) -> list[FeatureMeta]: ...
    @classmethod
    def get_all_features(cls) -> dict[str, list[FeatureMeta]]: ...
    @classmethod
    def get_cookie_hints(cls) -> dict[str, str]: ...
    @classmethod
    async def run(cls, platform, feature_id, url, cookie, save_dir) -> FeatureResult:
        """UI 唯一调用点。"""
        ops = cls._registry.get(platform)
        if ops is None: return FeatureResult(False, f"平台 {platform} 未注册")
        return await ops.execute(feature_id, url, cookie, save_dir)
```

### 3.6 ConfigManager — 全局配置

```python
@dataclass
class AppConfig:
    storage_mode: str = "flat"
    storage_format: str = "json"
    dedup: bool = True
    language: str = "zh_CN"

class ConfigManager:
    @classmethod
    def load(cls) -> AppConfig: ...    # 读 Volume/config.json
    @classmethod
    def save(cls, config: AppConfig): ...
    @classmethod
    def get_storage_ops(cls, platform: str) -> StorageOps: ...
```

---

## 四、平台注册机制

### 注册流程

```
程序启动 → load_all_platforms()
  → import platforms.douyin → __init__.py → PlatformBus.register(DouyinOps())
  → import platforms.kuaishou → __init__.py → PlatformBus.register(KuaishouOps())
  → import platforms.xiaohongshu → __init__.py → PlatformBus.register(XiaohongshuOps())
```

### 平台隔离规则

```
platforms/douyin/ops.py    → import shared.core.ops, shared.flow.*, 自己的 adapter ✓
platforms/douyin/ops.py    → import platforms.kuaishou ✗ 禁止
platforms/douyin/adapter.py → import shared.core, 自己的 encrypt/ ✓
```

---

## 五、各平台 OPS 定义

### 5.1 抖音 — DouyinOps

```
platform_id = "douyin"
cookie_hint = "需要完整 Cookie 字符串"

features:
  download   下载单个作品       need_url=True
  account    批量下载账号作品   need_url=True
  mix        批量下载合集作品   need_url=True
  collection 批量下载收藏作品   need_url=True
  live       获取直播拉流地址   need_url=True
  comment    采集作品评论数据   need_url=True
  user       采集账号详细数据   need_url=True
  search     采集搜索结果数据   need_url=True
  hot        采集抖音热榜数据   need_url=False

实现:
  _do_download()   → LinkExtractor → Adapter.request_detail → FileDownloader
  _do_account()    → Adapter.fetch_user_posts → 批量下载
  _do_mix()        → Adapter.fetch_mix → 批量下载
  _do_collection() → Adapter.fetch_collection → 批量下载
  _do_live()       → Adapter.fetch_live → 解析流地址 → 返回
  _do_comment()    → Adapter.fetch_comments → 翻页采集 → 保存 JSON
  _do_user()       → Adapter.fetch_user_profile → 保存 JSON
  _do_search()     → Adapter.fetch_search → 解析 → 保存 JSON
  _do_hot()        → Adapter.fetch_hot_list → 保存 JSON
```

### 5.2 快手 — KuaishouOps

```
platform_id = "kuaishou"
cookie_hint = "需要 Cookie"

features:
  download   下载单个作品       need_url=True
  account    批量下载账号作品   need_url=True

实现:
  _do_download() → LinkExtractor → Adapter.request_detail → FileDownloader
  _do_account()  → 待实现（返回 FeatureResult(False, "待实现")）
```

### 5.3 小红书 — XiaohongshuOps

```
platform_id = "xiaohongshu"
cookie_hint = ""  (留空 = 不显示 cookie 输入框)

features:
  download   下载单个作品   need_url=True

实现:
  _do_download() → LinkExtractor → Adapter.request_detail → FileDownloader
```

---

## 六、数据流

```
UI ── PlatformBus.run("douyin", "download", url, cookie, path)
  │
  ▼
PlatformBus._registry["douyin"] → DouyinOps
  │
  ▼
DouyinOps.execute("download", ...) → getattr(self, "_do_download")
  │
  ├─① LinkExtractor.run(url)           # shared/flow/
  ├─② DouyinAdapter.request_detail()    # platforms/douyin/adapter.py
  ├─③ DouyinAdapter.parse_detail()      # platforms/douyin/adapter.py
  ├─④ DouyinAdapter.get_download_urls() # platforms/douyin/adapter.py
  ├─⑤ storage_ops.resolve(work)    # shared/core/storage.py
  ├─⑥ FileDownloader.download_file()    # shared/flow/download.py
  ├─⑦ DataStorage.save_works()          # shared/flow/storage.py
  └─⑧ return FeatureResult(...)
  │
  ▼
UI ── 遍历 result.log 显示
```

---

## 七、UI 层

### TUI

```python
from shared.core.ops import PlatformBus

class IndexScreen(Screen):
    def compose(self):
        yield Select([(pid, pid) for pid in PlatformBus.list_platforms()], id="plat")
        yield Select([], id="fn")
        yield Input(placeholder="Cookie", id="ci")
        yield Input(placeholder="链接", id="url")
        yield Button("执行", id="go")
        yield RichLog(id="lg")

    @on(Select.Changed, "#plat")
    def on_plat(self, e):
        features = PlatformBus.get_features(e.value)
        self.fn_w.set_options([(f.name, f.id) for f in features])
        ops = PlatformBus.get_ops(e.value)
        self.query_one("#ci").display = bool(ops.cookie_hint)

    @on(Button.Pressed, "#go")
    async def on_execute(self):
        result = await PlatformBus.run(platform, feature_id, url, cookie, save_dir)
        for line in result.log: self._log(line)
```

### GUI

```python
class GuiBackend:
    def get_features(self, p):
        return [{"id": f.id, "name": f.name, "need_url": f.need_url}
                for f in PlatformBus.get_features(p)]
    async def execute(self, p, f, url, cookie, path):
        return await PlatformBus.run(p, f, url, cookie, path)
```

---

## 八、新增平台指南

```
1. mkdir platforms/bilibili/
2. 创建 adapter.py   — HTTP/API 调用
3. 创建 ops.py       — 继承 PlatformOps，实现 _do_xxx
4. 创建 __init__.py  — PlatformBus.register(BilibiliOps())
5. 在 platforms/__init__.py 加一行: import_module("platforms.bilibili")

完成。TUI/GUI/Web/CLI 自动支持，无需改任何已有代码。
```

---

## 九、配置文件

```json
// Volume/config.json
{
  "storage": { "mode": "flat", "format": "json", "dedup": true },
  "download": { "max_workers": 4, "timeout": 30 },
  "language": "zh_CN"
}
```

---

## 十、改动清单

| 文件 | 操作 |
|------|------|
| `shared/core/ops.py` | **新增** 总线 + PlatformOps + FeatureResult |
| `shared/core/storage.py` | **新增** StorageOps + StorageConfig |
| `shared/core/config.py` | **新增** ConfigManager |
| `shared/core/features.py` | **删除** |
| `platforms/douyin/ops.py` | **新增** 9 个功能 |
| `platforms/kuaishou/ops.py` | **新增** 2 个功能 |
| `platforms/xiaohongshu/ops.py` | **新增** 1 个功能 |
| `platforms/*/adapter.py` | **不动** |
| `platforms/douyin/encrypt/` | **不动** |
| `platforms/*/__init__.py` | **改** 加 register |
| `shared/flow/*.py` | **不动** |
| `ui/tui/screens/index.py` | **重写** 380→80 行 |
| `ui/gui/backend.py` | **重写** 220→40 行 |
| `ui/web/app.py` | **简化** |
| `ui/cli/main.py` | **简化** |


---

## 十一、工程优化记录 (2026-10)

### 11.1 核心机制升级

| 机制 | 变更 |
|------|------|
| **FeatureMeta 扩展** | 新增 `emits_work_info` (单作品结果标志) 与 `group` (work/user/platform 分组) 字段。UI 据此动态渲染分组按钮并决定是否更新作品资料卡, **删除了 UI 侧硬编码功能名单** |
| **PlatformBus 新 API** | `get_feature(platform, feature_id)` 按 id 查元数据; `display_name_of(platform)` 取显示名 |
| **日志体系** | 新增 `shared/core/logger.py`: 控制台 + Volume/logs/ 滚动文件双输出, `attach_gui_handler()` 可将日志桥接到 GUI 面板 |
| **异常分层** | `error.py` 定义 `RetryableError / RateLimitedError / AuthError / FatalError`; `Retry` 按异常分级退避, Auth/Fatal 不再重试 |
| **去重索引** | `StorageOps` 内置 `_DedupIndex` 内存 set 缓存, 下载记录 O(1) 查询, 消除每次全量读文件 |
| **Cookie 原子写** | `CookieManager` 全操作加 `threading.Lock`, JSON 落盘改为 临时文件 + `os.replace` 原子替换, 防崩溃丢数据 |
| **断点续传修复** | `FileDownloader` 补发 `Range: bytes={n}-` 请求头; 服务器返回 200 (不支持 Range) 时全量重写, 杜绝文件拼接损坏 |
| **SSL 验证** | `session.py` 默认 `verify=True`; 仅环境变量 `MD_SSL_VERIFY=0` 时关闭 (调试用) |
| **CSV 规范化** | `StorageOps._save_csv` 改用标准库 `csv.DictWriter`, 正确处理逗号/引号/换行 |

### 11.2 参考工程动态 (2026-09 调研)

| 参考项目 | 最新状态 | 可跟进能力 |
|---------|---------|-----------|
| TikTokDownloader → **DouK-Downloader** V5.8 (2026-09-13) | 更名并持续维护 | TikTok 双平台参数、aBogus 新版签名 |
| XHS-Downloader V2.8 (2026-09-12) | 活跃 | x-s 签名更新、图集评论增强 |
| KS-Downloader | 低频维护 | H5 API 基本稳定 |
| bilibili-downloader | 社区分散 | WBI 签名、DASH 音视频合并 (已实现) |

### 11.3 已知待办

- [ ] Cookie 加密存储 (keyring / Fernet)
- [ ] 下载队列管理 (暂停/续传/限速)
- [ ] 搜索功能全平台覆盖 (当前仅快手)
- [ ] 内嵌浏览器免抓 Cookie (docs/APP_BROWSER_PLAN.md)
- [ ] `MediaDownloader.spec` 动态生成 (当前硬编码路径已失效, 由 scripts/build.py 接管)
- [ ] i18n 接回配置项或移除死代码 (i18n.py)


---

## 十二、加密模块与代码整理 (2026-10 第二批)

### 12.1 抖音/TikTok 签名模块 (platforms/douyin/encrypt/) — 自维护

签名算法来自 DouK-Downloader 采用的逆向实现 (源头 Evil0ctal/Douyin_TikTok_Download_API,
Apache-2.0)。**平台前端 JS 更新后可能失效, 本目录需跟随上游维护**:

| 文件 | 职责 | 来源 |
|------|------|------|
| `aBogus.py` | 抖音 a_bogus 签名 (bdms.js v1.0.1.19-fix.01) | 逆向 |
| `websign.py` | x-secsdk-web-signature (secsdk runtime_bundler_34.js) | 逆向 |
| `tiktok_sign.py` | TikTok webmssdk (2.0.0.561) X-Bogus 系签名 | 逆向 |
| `sm3.py` | 国密 SM3 哈希 (aBogus 依赖) | 算法 |
| `params.py` | 参数拼装基类 | 自研 |
| `douyin_params.py` | DouYinParams 门面 (签名入口 + 保护路径表) | 自研 |
| `tiktok_params.py` | TikTokParams 门面 | 自研 |

跟进地址: 上游 releases 或 `src/dtk/signing/native/`。入口唯一:
`DouYinParams().sign_url(api, params, method, user_agent)`。

已于 2026-10 清理 7 个历史遗留死文件 (msToken/xBogus/xGnarly/ttWid/
device_id/verifyFp/webID, 旧版 V4.x 方案, 已无调用方)。

### 12.2 Cookie 加密存储 (shared/core/secret.py)

- Fernet 对称加密 (cryptography), 密钥 `Volume/.secret_key` (0600)。
- 落盘格式 `enc:<base64>`; 读取兼容旧版明文, 写入一律加密 → 平滑升级。
- 密钥损坏时解密返回空串 (引导重新登录), 不抛异常。

### 12.3 死代码清理与命名

| 项 | 处理 |
|----|------|
| `i18n.py` 翻译表 + t() | 全 UI 无调用, 移除; 保留 `platform_name()` (被 GUI/TUI 广泛使用), 留恢复说明 |
| `MediaDownloader.spec` | 删除 (硬编码 /home/npznnz 路径已失效); build.py 的 CLI 参数即唯一打包入口 |
| `build.py` hidden-import | 移除 4 个死模块声明, 补齐现役 encrypt 模块 + secret/logger/error/retry |
| 依赖 | 新增 `cryptography>=42.0` (requirements + pyproject) |

### 12.4 模块地图 (2026-10 现状)

```
shared/core/       ops(总线) adapter(ABC+norm_*) storage(存储+去重)
                   config cookies(加密) secret(Fernet) session(SSL可配)
                   retry(分级) error(异常层) logger(文件+GUI桥) login i18n(平台名)
                   ffmpeg format formats(编码预设) constants
shared/flow/       link(链接提取) download(断点续传) request extract storage
platforms/         {douyin,bilibili,kuaishou,xiaohongshu}/{ops,adapter,login}
                   douyin/encrypt/ (aBogus+websign+tiktok_sign, 自维护)
ui/gui/            main_window pages widgets threads(worker)
ui/tui/            app screens
```


---

## 十三、搜索覆盖与下载队列 (2026-10 第三批)

### 13.1 搜索功能覆盖进度

| 平台 | 状态 | 说明 |
|------|------|------|
| 抖音 | ✅ (既有) | web/search 接口 |
| 快手 | ✅ (既有) | H5 搜索 |
| **B站** | ✅ **新增** | `web-interface/wbi/search/type` (WBI 签名), ops 两阶段: 关键词→预览勾选→批量下载 |
| 小红书 | ⏸ 暂缓 | web_search 接口需 x-s 签名 (当前 encrypt 未覆盖小红书), 待签名方案补充 |

B站搜索入口: FeatureMeta("search", "搜索视频并下载") → `_do_search(keyword)`,
复用 `_video_preview/_batch_download` 既有管线。

### 13.2 下载队列管理 (shared/flow/queue.py)

**DownloadQueue (进程单例)** — UI/Worker 与下载器的解耦控制面:

| 能力 | API | 实现 |
|------|-----|------|
| 按任务停止 | `stop_task(task_key)` (前缀匹配) | DownloadHandle.stop_flag → chunk 循环抛 InterruptedError |
| 全局停止 | `stop_all()` | 同上 |
| 暂停/恢复 | `pause_all()/resume_all()` | chunk 间异步挂起 (`asyncio.sleep(0.2)` 轮询) |
| 全局限速 | `set_speed_limit(KB/s)` | chunk 间 `asyncio.sleep(CHUNK_SIZE/limit)` |
| 状态查询 | `status()` | 键/已下载/总量/暂停/停止 |

**链路**: FeatureWorker (生成 task_key) → PlatformBus.run(task_key=…)
→ PlatformOps.execute 反射透传 → ops._do_* → FileDownloader(task_key=…)
→ queue.register(handle) → UI 停止按钮 → worker.stop() → queue.stop_task。

断点续传保证: 停止时 .tmp 保留, 再次下载自动 Range 续传。


---

## 十四、数据导出与队列 UI 集成 (2026-10 第四批)

### 14.1 数据导出 (shared/flow/export.py)

- `export_rows(headers, rows, path)`: 按扩展名写 CSV (utf-8-sig, 标准库
  csv 转义) 或 JSON (dict 列表)。
- `export_dialog(parent, …)`: 系统保存对话框 + 结果提示。
- **DataTablePage** 页脚新增「导出 CSV/JSON」按钮, 评论/搜索/收藏等
  一切表格数据均可一键导出 (README 路线「数据导出」完成)。

### 14.2 队列控制 UI (设置页「下载队列」卡片)

- **限速**: 输入 KB/s (0=不限), 保存即持久化 (`AppConfig.speed_limit`)
  并实时应用到 DownloadQueue; 启动时 launcher 自动恢复。
- **暂停/恢复**: 按钮实时切换 `pause_all()/resume_all()`,
  文案随队列状态同步。
- `AppConfig` 新增 `speed_limit: int` 字段 (旧配置文件自动兼容缺省 0)。

### 14.3 累计待办状态

- [x] 数据导出 (CSV/JSON) — 本批完成
- [x] 下载队列管理 (暂停/续传/限速) — 第三、四批完成
- [x] 搜索全平台 (除小红书, 待 x-s 签名方案)
- [ ] 内嵌浏览器 (docs/APP_BROWSER_PLAN.md)
- [ ] 小红书搜索


---

## 十五、UI 设计修缮 (2026-10 第五批)

| 类 | 修复 | 说明 |
|----|------|------|
| A4 | LogPanel | 只读防误改 + html.escape 防渲染错乱 + 「清空/复制全部」按钮 |
| A5 | TUI 去硬编码 | `_DOWNLOAD_FEATURES` 名单删除, 改用 `FeatureMeta.emits_work_info` |
| A2 | FeaturePanel 追加泄漏 | 平台功能迁入独立 `_platform_grid`, 切平台整体重建不再堆积 |
| A3 | 启用语义 | `set_work_available` 只控制固有按钮, 平台批量按钮不再被误禁 |
| C1 | format_count 统一 | 4 处重复实现收敛到 `shared/core/format.py::format_count` |
| A1 | 内联色迁 QSS | InfoRow/UserRow/LogPanel 内联暗色删除, 双主题 QSS 接管 (亮色主题生效) |
| C2 | QSS 死代码 | 删除旧版侧栏样式段 (#Sidebar*); 补斑马纹 property 选择器与 #EmptyState |
| B3 | 空态组件 | ListPageBase `show_empty()`; 作品/用户列表空数据显示引导文案 |
