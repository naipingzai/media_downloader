<div align="center">
<h1>📥 MediaDownloader</h1>
<p>多平台统一媒体下载工具 — 抖音 · B站 · 快手 · 小红书</p>
<p><b>GUI (PySide6) | TUI (Textual)</b> · 插件式平台框架 · 统一数据规范</p>
</div>

---

## 🎯 项目定位（AI 阅读入口）

**一句话**: 把 TikTokDownloader / XHS-Downloader / KS-Downloader / bilibili-downloader 四个独立项目的能力，
整合为**一套插件式框架**，四平台共享核心代码，双前端（GUI/TUI）统一交互。

**设计方向**:
1. **平台插件化** — 每个平台是独立插件包，自注册到框架总线，新增平台零侵入
2. **核心零耦合** — `shared/core` 不 import 任何 `platforms/*`，框架可复用到任意下载场景
3. **数据统一规范** — 所有平台数据经 `norm_work`/`norm_user`/`norm_comment` 归一化后才进 UI
4. **UI 无知化** — UI 只读 `PlatformBus` 注册的 FeatureMeta 渲染按钮，零业务逻辑
5. **双前端同功能** — GUI 与 TUI 功能完全一致（页面形态不同是特性而非缺陷）

**明确不做**: Web UI / REST API / 复杂 CLI（聚焦桌面 GUI + 终端 TUI）。

---

## 🏗️ 框架架构

```
┌─────────────────────────────────────────────────────────┐
│  ui/gui (PySide6)          ui/tui (Textual)              │
│  主窗口+弹窗页+主题QSS      单列菜单+模态弹窗              │
│              │  只读 FeatureMeta + 调 PlatformBus.run    │
└──────────────┼──────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────┐
│  shared/core/ — 框架内核 (平台无关)                       │
│  ops.py      PlatformBus 总线 / PlatformOps 基类 /        │
│              FeatureMeta 功能声明 / FeatureResult 返回     │
│  adapter.py  PlatformAdapter 抽象基类 + norm_* 归一化     │
│  storage.py  存储 OPS (flat/by_date/by_author)            │
│  config.py   全局配置 ConfigManager                       │
│  cookies.py  CookieManager (加密存储/完整性检测)          │
│  login.py    LoginBus (扫码登录管理器注册)                 │
│  session.py  curl_cffi HTTP 工厂 (浏览器指纹)             │
├─────────────────────────────────────────────────────────┤
│  shared/flow/ — 通用流程                                 │
│  link.py 链接提取 · download.py 文件下载 · storage.py     │
└──────────────┬──────────────────────────────────────────┘
               │  PlatformBus.register(Ops) 自注册
   ┌───────────┼───────────┬───────────────┐
   ▼           ▼           ▼               ▼
┌────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐
│ douyin │ │bilibili│ │ kuaishou│ │xiaohongshu│  ← 平台插件
└────────┘ └────────┘ └─────────┘ └──────────┘
  X-Bogus     WBI签名     H5 API       签名算法
  msToken     buvid      ksToken     x-s/x-t
```

**关键机制**:
- `PlatformBus.register(Ops)` → `execute(feature_id)` 反射查找 `_do_<feature_id>` 执行
- FeatureResult 三态返回: 成功/失败 + `preview="batch"`（批量预览 → UI 弹勾选窗）+ `log` 实时日志
- UI 按钮完全由 FeatureMeta 动态生成（名称/是否需要URL），UI 零硬编码功能

---

## 📁 目录结构

```
MediaDownloader/
├── shared/                  # 框架内核 (平台无关, 可复用)
│   ├── core/                # ops/adapter/storage/config/cookies/login/session
│   └── flow/                # link/download/storage 通用流程
├── platforms/               # 平台插件 (完全隔离, 自注册)
│   ├── __init__.py          # ★ 自动发现式加载 (扫描子包, 无需名单)
│   ├── douyin/              # 抖音: __init__/ops/adapter/login/encrypt/
│   ├── bilibili/            # B站: WBI签名
│   ├── kuaishou/            # 快手: H5 API
│   └── xiaohongshu/         # 小红书: x-s/x-t 签名
├── ui/
│   ├── gui/                 # PySide6 GUI
│   │   ├── main_window.py   # 主窗口 (平台切换/链接解析/功能区/日志)
│   │   ├── pages/           # base_page(ListPageBase) + work_grid/users/data_table
│   │   ├── widgets/         # video_info/work_card/feature_panel/cover_label...
│   │   ├── threads/         # FeatureWorker (后台执行 PlatformBus.run)
│   │   └── resources/       # styles_dark.qss / styles_light.qss
│   └── tui/                 # Textual TUI (终端原生单列设计)
│       ├── app.py           # TuiApp 主界面
│       └── screens.py       # Login/Settings/BatchSelect/DataTable/Task 弹窗
├── main.py                  # 入口: python main.py [gui|tui]
├── scripts/build.py         # PyInstaller 打包
├── DESIGN.md                # GUI 布局设计文档
├── FRAMEWORK.md             # 框架详细设计文档
└── docs/APP_BROWSER_PLAN.md # 内嵌浏览器规划 (未来)
```

---

## 🔌 平台插件约定（新增平台两步走）

```python
# 1. 创建 platforms/<name>/ 包, __init__.py 自注册:
from shared.core.ops import PlatformBus
from .ops import XxxOps
PlatformBus.register(XxxOps())          # 功能注册
try:
    from shared.core.login import LoginBus
    from .login import XxxLoginManager
    LoginBus.register(XxxLoginManager())  # 扫码登录 (可选)
except ImportError:
    pass

# 2. ops.py 声明功能 + 实现 _do_<feature_id>:
class XxxOps(PlatformOps):
    features = [
        FeatureMeta("download", "下载单个作品", True),   # id, 名称, 是否需要URL
        FeatureMeta("account",  "批量下载账号作品", True),
    ]
    async def _do_download(self, adapter, url, storage, **kw) -> FeatureResult: ...
```

框架自动发现 `platforms/` 下所有子包（无需修改任何名单），UI 自动渲染新平台按钮和功能。

---

## ✨ 功能清单（四平台统一 + 平台特有）

| 功能 | 抖音 | B站 | 快手 | 小红书 |
|------|:----:|:---:|:----:|:------:|
| 下载单个作品 | ✓ | ✓ | ✓ | ✓ |
| 批量下载账号作品（勾选） | ✓ | ✓ | ✓ | ✓ |
| 批量下载合集/系列 | ✓ | ✓ | ✓ | — |
| 下载收藏 | ✓ | ✓ | ✓ | ✓ |
| 收藏夹列表 | ✓ | ✓ | ✓ | — |
| 直播拉流地址 | ✓ | — | — | — |
| 采集评论 | ✓ | ✓ | — | — |
| 采集用户资料 | ✓ | — | ✓ | ✓ |
| 关注列表 | — | — | ✓ | ✓ |
| 搜索结果 | — | — | ✓ | — |
| 扫码登录 | ✓ | ✓ | ✓ | ✓ |

**通用能力**: 链接提取(短链/分享文本) · 断点去重 · 批量预览勾选 · 多存储模式 · FFmpeg 转码 · Cookie 完整性检测 · 暗/亮主题 · 中文界面

---

## 🖥️ 双前端

### GUI (PySide6) — `python main.py`
- 主窗口: 平台切换 / 链接解析预览 / 功能按钮(动态) / 执行日志
- 列表弹窗页共用 `ListPageBase` 公共基类（统一页头+纵向滚动+页脚，禁横向滚动）
- 作品展示统一 `WorkCardWidget`（封面+标题+InfoRow 信息行），全中文固定信息项
- 独立窗口: 登录(扫码QR) / 设置(13项) / 批量勾选下载

### TUI (Textual) — `python main.py tui`
- 终端原生单列菜单设计（不模仿 GUI 排版，功能与 GUI 完全一致）
- 弹窗化交互: TaskScreen 任务弹窗(进度日志+结果) / BatchSelect 勾选 / DataTable 表格
- 快捷键: Ctrl+P 解析 · l 登录 · s 设置 · x 停止 · q 退出

---

## 📚 参考项目（能力来源）

| 参考项目 | 整合的能力 |
|---------|-----------|
| [DouK-Downloader](https://github.com/JoeanAmier/TikTokDownloader) (原 TikTokDownloader, V5.8) | 抖音 X-Bogus/msToken/aBogus 加密、批量下载、直播录制 |
| [XHS-Downloader](https://github.com/JoeanAmier/XHS-Downloader) (V2.8) | 小红书 x-s/x-t 签名、图集下载 |
| [KS-Downloader](https://github.com/MediaHarbor/KS-Downloader) | 快手 H5 API、收藏夹 |
| [bilibili-downloader](https://github.com/) | B站 WBI 签名、合集/系列、弹幕 |

整合原则: **只取算法与接口知识，代码全部重写为统一框架规范**（平台隔离、归一化数据、OPS 调度）。

---

## 🗺️ 路线规划

- [x] 四平台插件框架（自动发现 + 自注册）
- [x] GUI 主窗口 + 弹窗页统一设计
- [x] TUI 终端原生界面
- [x] 数据归一化规范（norm_work/user/comment）
- [x] 扫码登录 + Cookie 管理
- [x] **工程加固** (2026-10): 统一日志/异常分层重试/去重缓存/Cookie 原子写/断点续传修复/SSL 默认开启/单测 30 例 + CI
- [ ] **搜索功能** 全平台覆盖（当前仅快手）
- [ ] **下载队列管理**（暂停/续传/限速）
- [ ] **数据导出**（CSV/JSON/SQLite）
- [ ] **内嵌浏览器**（docs/APP_BROWSER_PLAN.md，免手动抓 Cookie）
- [ ] 自动更新 / 多语言(i18n 骨架已就位)

---

## 🚀 运行

```bash
# 安装依赖
pip install -r requirements.txt

# GUI 模式 (默认)
python3 main.py

# TUI 模式
python3 main.py tui

# 打包
python3 scripts/build.py
```

**依赖**: Python 3.10+ · PySide6 · Textual · curl_cffi · aiofiles · qrcode · pillow

---

## 📄 文档索引

| 文档 | 内容 |
|------|------|
| [DESIGN.md](DESIGN.md) | GUI 布局与交互设计 |
| [FRAMEWORK.md](FRAMEWORK.md) | 框架详细设计（OPS/存储/Cookie） |
| [docs/APP_BROWSER_PLAN.md](docs/APP_BROWSER_PLAN.md) | 内嵌浏览器规划 |
