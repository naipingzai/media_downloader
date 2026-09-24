# MediaDownloader - 设计与功能规划（v2 重写）

基于参考项目 TikTokDownloader V5.8 / KS-Downloader V1.7 / XHS-Downloader V2.8 / bilibili-downloader 的能力整合而成。

> **项目定调**：聚焦 PySide6 GUI 桌面端。
> **不做**：命令行参数解析 / TUI / Web / API。

---

## 一、整体架构

```
   ┌────────────────────────────────────────────────────────┐
   │        ui/gui  (PySide6 + QWebEngine + QSS)            │
   │                                                          │
   │  ┌── 侧栏 ──┐  ┌── 主区 ─────────────────────────────┐ │
   │  │  平台切换 │  │ ① 顶部: 当前作者卡 (蓝色昵称)       │ │
   │  │  登录状态 │  │ ② 中部: Tab 切换 (关注 / 收藏 /     │ │
   │  │  快捷功能 │  │    搜索 / 作品 / 设置)              │ │
   │  │  主题切换 │  │ ③ 底部: 功能菜单 + 日志            │ │
   │  └─────────┘  └──────────────────────────────────────┘ │
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
       └─ adapter.py ─────┴──── adapter.py ┴─ adapter.py ──┘
              curl_cffi / X-Bogus / X-Gnarly / WBI / H5
```

---

## 二、页面布局（重新设计）

### 2.1 当前问题

- 用户经常找不到「关注列表」「收藏列表」的结果窗口 → 散弹式弹窗
- 单窗口右侧日志看不到（默认隐藏）→ 用户不知在哪看输出
- 平台切换无 Tab 视图，按钮重复堆叠
- 主题无法切换

### 2.2 新设计：主窗口 3 区 + 1 个侧栏

```
┌──────────────────────────────────────────────────────────────────────┐
│  ⬢ MediaDownloader                          [☀/🌙 主题] [设置]      │
├──────────────┬───────────────────────────────────────────────────────┤
│              │ ╭─ 顶部: 当前作者信息卡 (蓝色昵称) ─────────────────╮│
│  侧栏        │ │ 头像  昵称(蓝/白)   签名                            ││
│              │ │  粉丝/关注/获赞/作品                              ││
│ ◆ 平台列表   │ │  [获取作品] [关注列表] [收藏列表] [头像] [主页]   ││
│  ● 抖音      │ ╰────────────────────────────────────────────────────╯│
│  ● B站       │                                                       │
│  ● 快手      │ ╭─ 中部: TAB 视图 (QTabWidget) ───────────────────╮ │
│  ● 小红书    │ │ [📋关注] [⭐收藏] [🔍搜索] [🎬作品] [💬评论]     │ │
│              │ │  + 视图内容区 (列表 / 卡片 / 表格)                │ │
│ ◆ 账号状态   │ ╰─────────────────────────────────────────────────╯  │
│  已登录 XX   │                                                       │
│              │ ╭─ 底部: 功能菜单 (单行: 下拉 + 按钮) ────────────╮  │
│ ◆ 设置       │ │  功能:[下载单个作品 ▾]   [▶ 执行]  [■ 停止]   │   │
│  · 保存目录  │ │  实时进度条 / 当前动作                              ││
│  · 主题      │ ╰─────────────────────────────────────────────────╯   │
│  · 并发数    │                                                       │
│              │ [📋 实时日志] (常驻显示区, 不再隐藏)                    │
│ ◆ 快捷       │                                                       │
│  ☀ 主题切换  │                                                       │
│  📁 打开目录 │                                                       │
└──────────────┴───────────────────────────────────────────────────────┘
```

### 2.3 关键改进点

| # | 改进 | 实现要点 |
|---|------|---------|
| 1 | **Tab 视图**取代 5 个独立弹窗 | `QTabWidget` 在中部，关注/收藏/搜索/作品/评论共用同一视图区，每个 Tab 持有一份数据缓存 |
| 2 | **常驻日志区** | 底部固定 LogPanel，不再藏到弹窗 |
| 3 | **主题切换按钮**侧栏 + 顶部 | `theme.py` 加 Light 配色，`main_window` 切换 + 持久化到设置 |
| 4 | **国际化全量迁移** | GUI 中散落的硬编码中文字符串全部迁入 i18n (`zh_CN.po` / `en_US.po`) |
| 5 | **关注列表显示更丰富** | 不只 "昵称 + 粉丝数"，改成 `UserCard`：头像 / 昵称 / 签名 / 粉丝 / 作品数 / "查看 TA 的作品" 按钮 |
| 6 | **收藏列表显示作品卡** | 复用 `WorkCard`（已实现），勾选后批量下载 |

---

## 三、关注 / 收藏 功能（用户重点需求）

> 用户要求「希望获取到关注列表和收藏数据」。下面是按平台逐一列出现状 + 目标。

### 3.1 抖音（Douyin）

| 功能 | 现状 | 数据源 | 实现状态 |
|------|------|--------|---------|
| 获取当前登录用户 | ✅ | `adapter.fetch_current_user()` | 已实现 |
| 获取作者所有作品 | ✅ | `adapter.fetch_user_posts(sec_uid, count, max_cursor)` | 已实现 + 批量下载 |
| **关注列表** | ✅ | `adapter.fetch_user_following(sec_uid, count, max_time)` | **已实现**，弹窗显示 |
| **收藏作品** | ✅ | `adapter.fetch_collection(cursor, count)` | **已实现**，作品卡 + 勾选下载 |
| **收藏合集** | ✅ | `adapter.fetch_collection_albums(cursor, count)` | **已实现** |
| **收藏夹** | ✅ | `adapter.fetch_favorite_folder_list` + `fetch_favorite_folder_awemes` | **已实现** |
| **目标** | — | — | **完善 UI**：在 TAB 视图里显示关注列表（带头像），点击关注人可直接跳转到 TA 的作品 Tab |

### 3.2 B 站（Bilibili）

| 功能 | 现状 | 数据源 | 实现状态 |
|------|------|--------|---------|
| 获取当前登录用户 | ✅ | `adapter.fetch_user_info(mid)` | 已实现 |
| 获取 UP 主所有作品 | ✅ | `adapter.fetch_user_videos(mid, max_count)` | 已实现 + 批量下载 |
| 关注列表 | ⚠️ **未实现** | 需 `nav.get_followings()` → B 站 Web API | adapter 没有 fetch 方法 |
| 收藏夹 | ✅ | `adapter.fetch_favorite_list(fid)` | 已实现（**仅当前用户自己的收藏夹**,fid=默认收藏夹 0） |
| **目标** | — | — | **新增** `fetch_user_following(mid)` + `fetch_user_favorite_folders(mid)`；UI 添加 Tab |

### 3.3 快手（Kuaishou）

| 功能 | 现状 | 数据源 | 实现状态 |
|------|------|--------|---------|
| 获取当前登录用户 | ⚠️ stub | `adapter.fetch_current_user()` | 返回 `None` |
| 获取作者作品 | ✅ | `adapter.fetch_user_videos(user_id, max_count)` | 已实现 + 批量下载 |
| 关注列表 | ⚠️ **未实现** | adapter 无 fetch 方法 | 待补 |
| 收藏作品 | ⚠️ **未实现** | adapter 无 fetch 方法 | 待补 |
| **目标** | — | — | **新增** `fetch_user_following(user_id)` + `fetch_user_collection(user_id)`；UI 添加 Tab |

### 3.4 小红书（Xiaohongshu）

| 功能 | 现状 | 数据源 | 实现状态 |
|------|------|--------|---------|
| 获取当前登录用户 | ⚠️ stub | `adapter.fetch_current_user()` | 返回 `None` |
| 下载单个作品 | ✅ | `adapter.request_detail()` + parse | 已实现 |
| **批量下载用户作品** | ⚠️ **未实现** | adapter 有 `fetch_user_posts(sec_uid)`（stub-like） | **本次迭代实现 `_do_account`** |
| 关注列表 | ⚠️ **未实现** | adapter 无 fetch 方法 | 待补 |
| 收藏 | ⚠️ **未实现** | adapter 无 fetch 方法 | 待补 |
| **目标** | — | — | **本次迭代实现**：`fetch_user_profile` + `_do_account`；新增关注/收藏 Tab；详情页支持小红书特色（图文/livePhoto 多文件） |

### 3.5 共同目标

| 项 | 说明 |
|----|------|
| **统一 UserCard** | 关注列表里每人是 `UserCard`（头像 / 昵称 / 签名 / 粉丝 / 作品数），点击进入其详情页 |
| **统一 WorkCard** | 收藏列表/作品列表复用 `WorkCard`，支持勾选 + 批量下载 |
| **统一 TAB 容器** | `QTabWidget` 渲染 [📋关注 / ⭐收藏 / 🎬作品 / 💬评论 / 🔍搜索]，每次切换从缓存拿数据 |
| **下载导流** | 任何列表页都有"下载全部" / "下载选中"按钮 |

---

## 四、当前已实现功能（实测 19 项）

### 4.1 平台与功能矩阵

| 平台 | 功能 ID | 显示名 | 状态 |
|------|---------|--------|------|
| **douyin** | download | 下载单个作品 | ✅ |
| | account | 批量下载账号作品 | ✅ |
| | mix | 批量下载合集作品 | ✅ |
| | collection | 批量下载收藏视频 | ✅ |
| | collection_album | 批量下载收藏合集 | ✅ |
| | favorite_folder | 批量下载收藏夹 | ✅ |
| | live | 获取直播拉流地址 | ✅ |
| | comment | 采集作品评论数据 | ✅ |
| | user | 采集账号详细数据 | ✅ |
| | search | 采集搜索结果数据 | ✅ |
| **bilibili** | download | 下载单个视频 | ✅ |
| | account | 批量下载用户作品 | ✅ |
| | series | 批量下载合集/系列 | ✅ |
| | collection | 批量下载收藏夹 | ✅ |
| | comment | 采集视频评论 | ✅ |
| | user | 采集用户资料 | ✅ |
| **kuaishou** | download | 下载单个作品 | ✅ |
| | account | 批量下载账号作品 | ✅ |
| **xiaohongshu** | download | 下载作品文件 | ✅ |

> 抖音 10 项 + B 站 6 项 + 快手 2 项 + 小红书 1 项 = **19 项可执行功能**

### 4.2 顶部作者卡 5 个按钮

| 按钮 | 状态 | 改进方向 |
|------|------|---------|
| 👤 获取作品 | ✅ | 点击后切换到「作品 Tab」并开始加载 |
| 📋 关注列表 | ✅ | 点击后切换到「关注 Tab」并开始加载 |
| ⭐ 收藏列表 | ✅ | 点击后切换到「收藏 Tab」并开始加载 |
| 🖼 下载头像 | ✅ | - |
| 🔗 主页链接 | ✅ | - |

### 4.3 通用能力（已实现）

| 能力 | 说明 |
|------|------|
| Cookie 管理 | 登录对话框（扫码 / 手动粘贴 / 剪贴板） |
| 短链接解析 | v.douyin.com 等短链 → 302 → 长链 |
| 跳过已下载 | SQLite 记录 work_id |
| 多线程下载 | asyncio.Semaphore(4) |
| 断点续传 | HTTP Range |
| 文件签名校验 | 14 种格式 |
| 封面/头像缓存 | `CoverLoader` 单例 |
| 文件夹归档 | 按作者 / 类型 |
| 自定义文件名 | `create_time type nickname desc` |
| 数据持久化 | CSV/XLSX/SQLite/JSON |
| **当前登录用户昵称蓝色** `#3b82f6` | ✅ |
| 进度日志 | LogPanel |

### 4.4 需要补全的通用能力

| 项 | 状态 | 工作量 |
|----|------|--------|
| **国际化全量迁移** | ⚠️ 框架就位，字符串硬编码多 | 1~2 天（grep 中文 → i18n） |
| **暗/亮主题切换** | ❌ 当前固定暗色 | 1 天（加 light.qss + 切换按钮） |
| **系统托盘** | ❌ 未实现 | 半天（QSystemTrayIcon） |
| **进度条 UI 化** | ⚠️ 仅文字 | 1 天（QProgressBar） |
| **代理设置 UI 化** | ❌ 仅 adapter 内部 | 半天 |
| **剪贴板监听** | ❌ 未实现 | 半天 |

---

## 五、本次迭代任务清单（不含用户已显式排除的：抖音热榜 / TikTok 国际版）

### Phase 1：页面重设计 + 用户重点需求（3~5 天）

1. **新主窗口布局：Tab 视图 + 常驻日志**
   - `main_window.py`：原 `QSplitter(VideoInfo, FeaturePanel)` → 改为 `QTabWidget` 持有 `关注/收藏/作品/评论/搜索` 五个 `QWidget`
   - 底部常驻 `LogPanel`（不再弹窗）
   - 顶部右侧加主题切换按钮

2. **统一 `UserCard`** （`widgets/user_card.py`）
   - 头像 / 昵称 / 签名 / 粉丝 / 作品 / "查看作品" 按钮
   - 点击 "查看作品" 切换到作品 Tab

3. **统一 `WorkCard`** 已有，扩展勾选行为

4. **新增 `CollectListView` / `FollowingListView`** 容器

5. **国际化字符串补全** （`shared/translation/` + 各 widget）
   - grep 所有硬编码中文 → `_()` 包起来
   - 完善 `zh_CN.po` 和 `en_US.po`

6. **暗/亮主题切换**
   - `ui/gui/resources/theme.py`：加 `LIGHT_THEME` 配色字典
   - `styles.qss`：加 `styles_light.qss`
   - 设置按钮触发 `main_window.setStyleSheet(...)` + 持久化

### Phase 2：小红书 + B 站 + 快手 关注/收藏数据补全（3~5 天）

7. **小红书批量下载用户作品**（用户显式要求）
   - `platforms/xiaohongshu/ops.py`：补 `_do_account` + menu 项
   - 复用 `fetch_user_posts`，UI 预览 + 勾选下载

8. **小红书关注列表 + 收藏**
   - adapter 补 `fetch_user_following` + `fetch_user_collection`
   - ops 补 `_do_user_following` / `_do_collection`
   - 注册到 `features` 列表

9. **B 站关注列表**
   - adapter 补 `fetch_user_following(mid)`
   - ops 补 `_do_user_following`

10. **B 站收藏夹列表（按用户切换）**
    - adapter 已有 `fetch_favorite_list(fid)`，需补"列出用户所有收藏夹 + 进入任一"
    - ops 补 `_do_favorite_folder_list`

11. **快手关注列表 + 收藏**
    - adapter 补 `fetch_user_following` / `fetch_user_collection`
    - ops 补对应 `_do_*`

12. **小红书当前登录用户**（修复 stub）
    - `fetch_current_user` 现在返回 None，需补

### Phase 3：基础改进（按需）

13. 系统托盘
14. 进度条 UI 化
15. 代理设置 UI 化
16. 剪贴板监听（小红书强需求）

---

## 六、UI 设计备忘

### 6.1 配色（双主题）

| 用途 | Dark | Light |
|------|------|-------|
| 背景 | `#1e293b` | `#f8fafc` |
| 卡片 | `#1e293b` | `#ffffff` |
| 边框 | `#334155` | `#e2e8f0` |
| 主色（蓝） | `#3b82f6` | `#2563eb` |
| 成功（绿） | `#22c55e` | `#16a34a` |
| 失败（红） | `#ef4444` | `#dc2626` |
| 警告（橙） | `#f59e0b` | `#d97706` |
| 主文本 | `#f1f5f9` | `#0f172a` |
| 副文本 | `#94a3b8` | `#64748b` |

### 6.2 当前登录用户标记
- 用户名 **蓝色** `#3b82f6`（已改）
- 后缀 `▸ 当前登录`

### 6.3 Tab 视图规范

| Tab | 默认数据 | 刷新按钮 | 操作 |
|-----|---------|---------|------|
| 📋 关注 | 空 | ✓ | 跳转到 TA 的作品 |
| ⭐ 收藏 | 空 | ✓ | 勾选 + 批量下载 |
| 🎬 作品 | 空 | ✓ | 勾选 + 批量下载 |
| 💬 评论 | 空 | ✓ | 导出 |
| 🔍 搜索 | 空 | ✓ | 跳转作品 |

---

## 七、代码对应表（速查）

| 想要的功能 | 看哪些文件 |
|------------|----------|
| 修改某个功能的执行逻辑 | `platforms/<plat>/ops.py` 里的 `_do_xxx` |
| 新增/删除功能菜单 | `platforms/<plat>/ops.py` 里的 `features = [...]` |
| 修改作品数据提取 | `platforms/<plat>/adapter.py` 里的 `parse_detail` |
| 添加新签名 | `platforms/douyin/encrypt/` （aBogus/X-Bogus/X-Gnarly/...） |
| 修改下载流程 | `shared/flow/download.py` (`FileDownloader`) |
| 修改链接解析 | `shared/flow/link.py` (`LinkExtractor`) |
| 修改文件命名/归档 | `shared/core/storage.py` |
| 添加新平台 | 复制 `platforms/xiaohongshu/` 模板 → 注册到 `platforms/__init__.py` |
| 修改 UI 主题/颜色 | `ui/gui/resources/theme.py` + `resources/styles.qss` + 各 widget 的 `setStyleSheet` |
| 添加新的 dialog | 仿 `widgets/work_grid_dialog.py` |
| 添加 i18n 字符串 | `shared/translation/translate.py` + `locale/zh_CN.po` |

---

## 八、本次已变更

| 文件 | 变更 |
|------|------|
| `ui/gui/widgets/author_profile_panel.py:184` | "▸ 当前登录"颜色 `#22c55e` → `#3b82f6`（绿 → 蓝） |
| `DESIGN.md` | 老文档重写为新版本（本文件） |
