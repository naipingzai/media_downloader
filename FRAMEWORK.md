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
