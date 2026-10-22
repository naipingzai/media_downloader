# MediaDownloader — 设计与布局说明

> **项目定调**：聚焦 PySide6 GUI 桌面端。整合 TikTokDownloader / KS-Downloader / XHS-Downloader / bilibili-downloader 的能力。
> **不做**：复杂命令行参数解析 / Web / API。
> **新增**：TUI (Textual) — 布局与功能完全同步 GUI 设计。

---

## 一、整体架构

```
   ┌────────────────────────────────────────────────────────┐
   │        ui/gui  (PySide6 + QSS 暗/亮主题)                │
   │                                                        │
   │  ┌── 顶部横排栏 ──────────────────────────────────┐   │
   │  │ 品牌 | 平台按钮组 | 设置/暗色/登录/下载目录       │   │
   │  └─────────────────────────────────────────────────┘   │
   │  ┌── 中部 (左 3 : 右 2) ──────────────────────────┐   │
   │  │ 左侧外框      │ 链接 + 功能按钮 + 执行日志         │   │
   │  └─────────────────────────────────────────────────┘   │
   │  独立非模态窗口 (ToolWindow): 登录 / 设置 / 数据          │
   └─────────────────────┬──────────────────────────────────┘
                         │  feature_id, url, opts
                         ▼
   ┌────────────────────────────────────────────────────────┐
   │    shared/core/ops.py   (PlatformBus / FeatureMeta)    │
   │    execute() 反射查找 _do_<feature_id>                  │
   └─────────────────────┬──────────────────────────────────┘
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
   douyin/ops.py    bilibili/ops.py    kuaishou/ops.py    xiaohongshu/ops.py
       │                 │                 │                 │
       └─ adapter.py ─────┴─ adapter.py ──┴─ adapter.py ──┘
              curl_cffi / X-Bogus / X-Gnarly / WBI / H5
```

---

## 二、主窗口布局（当前实现）

```
┌───────────────────────────────────────────────────────────┐
│ 顶部横排栏: 品牌 | 平台按钮组 | 设置/暗色/登录/下载目录       │
├─────────────────────────┬─────────────────────────────────┤
│ ┌ 左侧外框 (统框) ────┐ │ ┌ 链接 ──────────────────────┐  │
│ │ [作者资料]  (顶部)   │ │ │ 粘贴链接 + [解析预览]        │  │
│ │ 头像 昵称 签名       │ │ ├ 功能 ──────────────────────┤  │
│ │ 粉丝/关注/获赞/作品  │ │ │ 作品操作                     │  │
│ ├─────────────────────┤ │ │  获取链接/查看评论/下载封面    │  │
│ │ 作品资料             │ │ │ 作者操作                     │  │
│ │ (无页签, 占满)       │ │ │  获取作品/关注列表/收藏列表…  │  │
│ │  · 封面 + 详情       │ │ │ 平台功能                     │  │
│ │  · 只显示作品资料    │ │ │  下载/批量/直播… (随平台)     │  │
│ │                     │ │ ├ 执行日志 (可折叠) ─────────┤  │
│ └─────────────────────┘ │ │ 实时日志 + 复制粘贴          │  │
└─────────────────────────┴─┴─────────────────────────────┘  │
  独立非模态窗口: [登录] / [设置] / [数据页]                    │
  底部状态栏: Cookie + 版本 + FFmpeg                           │
└───────────────────────────────────────────────────────────┘
```

### 2.1 布局要点

| 区域 | 组件 | 说明 |
|------|------|------|
| 顶部横排栏 | `_build_topbar` | 品牌 / 平台切换按钮组 / 设置 / 暗色 / 登录 / 下载目录 |
| 左侧外框 | `_build_left_panel` → `#LeftPanel` | 一个边框包住「作者资料」+「作品资料」，完整覆盖左侧上到下 |
| 作者资料 | `AuthorProfilePanel` | 顶部固定高度，显示头像/昵称/签名/统计 |
| 作品资料区 | `VideoInfoWidget` | 占满剩余高度；左上角固定标题「作品资料」；无页签 |
| 链接 | `_build_link_panel` | 粘贴链接 + 解析预览 |
| 功能 | `FeaturePanel` | 作品操作 / 作者操作 / 平台功能 三组按钮网格 |
| 执行日志 | `LogPanel` | 可折叠，支持复制粘贴 |
| 登录 / 设置 | `ToolWindow` | 独立非模态窗口，可拖动/缩放，关闭仅隐藏 |

### 2.2 作品资料区（无页签）设计

- 左上角标题「作品资料」固定显示（`#LeftSubTitle`）。
- **无任何页签**，区域内只显示作品资料本身（封面 + 详情），内容随控件大小伸展。
- 作品相关数据（作者作品 / 收藏列表 / 关注列表 / 评论列表 / 数据表格 / 批量预览）改在**数据窗口**中显示。

### 2.3 独立窗口（ToolWindow）

登录 / 设置 / 数据均使用 `ToolWindow` 独立顶层窗口（`Qt.Window`），**非模态**，不阻塞主窗口：

- **登录** / **设置**：各自单例页，关闭仅隐藏、内容保留复用；切换平台时登录页自动刷新 Cookie。
- **数据窗口**：作品网格 / 列表 / 表格 / 评论等数据页复用同一窗口（`set_content` 替换内容），标题随内容更新。
- 首次打开自动居中于主窗口，可拖动 / 缩放 / 最小化。

---

## 三、关键设计决策

| 问题 | 决策 |
|------|------|
| 弹窗变形（登录页被压成一条线） | 移除锁死高度，页面用 `QScrollArea` + `Expanding` 尺寸策略 |
| Cookie 保存失效（切页后丢失） | `CookieManager` 单例 + `get()` 读取时刷新磁盘 |
| 登录/设置塞进作品区页签 | 移到独立非模态 `ToolWindow` |
| 作品资料区页签杂乱 | 取消页签，只显示作品资料；数据页改独立数据窗口 |
| 页签关闭按钮丑陋 | 统一用 SVG 绘制 ×（常态灰，hover 红），暗/亮主题一致 |
| 样式作用域污染 | 用 objectName 精确选择器（`#LeftPanel` / `#AuthorCard` 等），不用 `QFrame {}` 通配 |

---

## 四、模块结构

```
ui/gui/
├── main_window.py          主窗口 (布局 + 信号编排)
├── launcher.py             启动器
├── cover_loader.py         封面异步加载
├── threads/worker.py       FeatureWorker (后台执行)
├── resources/
│   ├── theme.py            主题切换 (暗/亮)
│   ├── styles_dark.qss     暗色主题
│   └── styles_light.qss    亮色主题
├── widgets/
│   ├── author_profile_panel.py   作者资料卡
│   ├── video_info.py             作品资料 (封面+详情)
│   ├── tool_window.py            登录/设置/数据 独立窗口
│   ├── feature_panel.py          功能按钮面板
│   ├── section_panel.py          带标题的边框面板
│   ├── log_panel.py              执行日志
│   └── ...                       作品卡/封面等
└── pages/
    ├── login_page.py       登录页 (QR + Cookie)
    ├── settings_page.py    设置页
    ├── work_grid_page.py   作品网格
    ├── users_page.py       用户列表
    └── data_table_page.py  数据表格
```

---

## 五、主题系统

- `resources/theme.py` 提供 `toggle_theme(app)` 在暗/亮主题间切换。
- 两份 QSS 使用相同的 objectName 选择器（`#LeftPanel` / `#AuthorCard` / `#LeftSubTitle` 等），保证布局一致。
- 主题切换时左侧外框、独立窗口内容自动适配。


---

## 六、TUI (Textual) — 与 GUI 设计同步

`ui/tui/app.py` 提供 `TuiApp`，布局/交互与 GUI 一一对应：

| GUI (PySide6) | TUI (Textual) | 说明 |
|------|------|------|
| 顶部横排栏 | `#topbar` (Header + 平台按钮) | 品牌 / 平台切换 / 快捷键 |
| 左侧外框 | `#left-panel` | 作者资料卡(顶) + 作品资料(占满) |
| 链接面板 | `#link-input` + Ctrl+P | 粘贴链接 → 解析预览 |
| FeaturePanel | `#features-box` | 作品操作/作者操作/平台功能(FeatureMeta 动态) |
| LogPanel | `#log-panel` (RichLog) | 实时彩色日志 (✓绿 ✗红 ⚠黄 ▸青) |
| 状态栏 | `#footer-status` | Cookie 完整性 / FFmpeg / 版本 |
| ToolWindow(登录) | `LoginScreen` | QR 终端字符画 + Cookie 粘贴 |
| ToolWindow(设置) | `SettingsScreen` | 存储/输出/下载选项/FFmpeg/字号 |
| ToolWindow(数据) | `DataTableScreen` | 评论/作品/关注/收藏 表格 |
| WorkGridPage | `BatchSelectScreen` | 预览 → 空格勾选 → Ctrl+D 下载 |
| FeatureWorker | `_run_bg` (线程+事件循环) | PlatformBus.run 后台执行 |

快捷键: `q`退出 · `l`登录 · `s`设置 · `d`下载目录 · `Ctrl+P`解析 · Tab 切换焦点
