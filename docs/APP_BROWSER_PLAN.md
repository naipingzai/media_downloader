# "App 式浏览" 功能流程评估报告

> 目标：用已登录 Cookie 直接展现"我的 → 关注 → 用户 → 作品"四级层级，像 App 一样操作后批量下载；本报告基于四个参考工程（`TikTokDownloader` / `KS-Downloader` / `XHS-Downloader` / `bilibili-downloader`）+ `MediaDownloader` 实际代码梳理，结论为：**整体方案可行，但四平台的支持矩阵差异较大，本期可在 B 站/抖音两平台完整实现，其它平台分批落地**。

---

## 一、四平台现状能力矩阵（基于实际代码）

| 能力\平台 | 抖音 douyin | 快手 kuaishou | 小红书 xiaohongshu | B 站 bilibili |
|---|---|---|---|---|
| **作品详情** | ✅ `aweme/v1/web/aweme/detail/` | ✅ `live_api/profile/feedbyid` | ✅ HTML+`__INITIAL_STATE__` | ✅ `/x/web-interface/view` |
| **用户资料** | ✅ `aweme/v1/web/user/profile/other/` | ✅ `rest/v/profile/feed` | ⚠️ HTML 解析（profile 路由） | ✅ `/x/web-interface/space`（需 WBI） |
| **用户作品列表** | ✅ `aweme/v1/web/aweme/post/` | ⚠️ 仅 profile.feed 单页 | ⚠️ HTML 解析 noteList | ✅ `/x/series/archives`、`space/seasons_archives_list` |
| **账号批量下载** | ✅ `_do_account` 已实现 | ✅ `_do_account` 已实现 | ❌ `get_account_works` 占位返回 [] | ✅ `fetch_user_videos` 已实现 |
| **关注/粉丝列表** | ❌ 无 `aweme/v1/web/user/follower/following` 实现 | ❌ 无 | ❌ 无 | ❌ 无 `/x/relation/followers` 实现 |
| **收藏作品** | ✅ `aweme/v1/web/aweme/favorite/` + `listcollection/` + `favorite_folder/*` | ❌ 无 | ❌ 无 | ✅ `/x/v3/fav/resource/list` |
| **合集/系列** | ✅ `mix/aweme/`、`mix/listcollection/`、`series/collections/` | ❌ 无 | ❌ 无 | ✅ `series/archives`、`seasons_archives_list` |
| **直播拉流** | ✅ `webcast/room/web/enter/` | ✅ `live_api/profile/feedbyid` | ❌ 无 | ❌ 无 |
| **搜索** | ✅ `search/item/` 4 种 | ❌ 无 | ❌ 无 | ❌ 无 |
| **当前登录用户信息** | ❌ 无 `aweme/v1/web/im/user/info/`（参考 TikTokDownloader `interface/info.py` 已实现） | ❌ 无 | ❌ 无 | ⚠️ 有 `/x/web-interface/nav`（bilibili-downloader `endpoints.py`，可读取 SESSDATA 拿登录态，但未接入） |
| **Cookie 登录态** | ✅ `DouyinLoginManager` 已有 | ❌ 仅有 hint，无 QR | ❌ 无 | ✅ `login.py` QR 登录实现完整 |

**总结**：
- **核心基础能力**（作品/用户资料/合集/收藏/账号作品列表）抖音、B 站基本齐全，快手/小红书仅"详情"层级可用。
- **关键缺口**：
  - 四平台**均未实现"我的"页面与"关注列表"**（这是 App 式浏览的核心入口）。
  - **快手 / 小红书 整条链路缺失**：当前只支持粘贴作品链接；没法"看用户、看关注、看收藏"。
  - **当前登录用户**接口未接入（虽然 B 站已有 nav endpoint、抖音 info endpoint 可直接调用）。

---

## 二、目标流程设计

```
┌─────────────────────────────────────────────────────────────────┐
│ 侧边栏                                                       │
│  - 抖音  快手  小红书  B 站                                 │
└─────────────────────────────────────────────────────────────────┘
                          ↓ 选中平台（Cookie 已登录）
┌─────────────────────────────────────────────────────────────────┐
│ 【① 我的主页】                              （顶部固定面板）  │
│  [头像] 昵称  UID  粉丝  关注  获赞                       │
│  ┌─────────┬─────────┬─────────┬─────────┐              │
│  │ 我发布 │ 我的收藏 │ 关注的人 │ 我的合集 │   ← 标签页切换 │
│  └─────────┴─────────┴─────────┴─────────┘              │
└─────────────────────────────────────────────────────────────────┘
                          ↓ 选"关注的人"（示例）
┌─────────────────────────────────────────────────────────────────┐
│ 【② 关注列表】                                                 │
│  ▢  头像 昵称  UID  签名  粉丝数  [查看作品]                │
│  ▢  头像 昵称  UID  签名  粉丝数  [查看作品]                │
│  ...                                                          │
│  顶栏: [全选] [下载选中主页] [搜索用户]                    │
└─────────────────────────────────────────────────────────────────┘
                          ↓ 点"查看作品"或直接点用户卡片
┌─────────────────────────────────────────────────────────────────┐
│ 【③ 用户作品列表】（面包屑：我的 / 关注 / 张三）               │
│  ▢  封面 标题 作者 时长 点赞  发布时间                     │
│  ▢  封面 标题 作者 时长 点赞  发布时间                     │
│  ...                                                          │
│  顶栏: [全选] [下载选中] 筛选: ▾全部/置顶/最新            │
└─────────────────────────────────────────────────────────────────┘
                          ↓ 点击单作品 或 多选 → 下载
┌─────────────────────────────────────────────────────────────────┐
│ 【④ 作品资料卡】                                               │
│  ┌──────────┬────────────────────────────────────┐           │
│  │          │ 标题: ...                           │           │
│  │  封面     │ 作者: 张三  UID: ...               │           │
│  │  视频预览 │ 点赞 N 评论 N 播放 N 时长 N      │           │
│  │  进度条   │ 视频直链 / 图片: 9 张              │           │
│  └──────────┴────────────────────────────────────┘           │
│  操作: [⬇下载] [打开原链接] [复制文案]                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、页面/组件拆分（在现有项目上增量）

### 3.1 现有组件（已具备，本次改造几乎不动）
- `ui/gui/widgets/video_info.py`：作品资料卡（**本次刚改造**：封面占左半、卡片式布局）
- `ui/gui/widgets/work_card.py`：通用作品卡片（**本次新建**：左封面+右资料、点击切换选中）
- `ui/gui/widgets/batch_preview.py`：批量预览选择框（**本次刚改造**：复用卡片、点击卡片切换选中）
- `ui/gui/widgets/cover_label.py`：自适应封面控件（**本次新建**：随窗口缩放）
- `ui/gui/cover_loader.py`：curl_cffi 后台封面下载（已带缓存+safe-emit）

### 3.2 新增组件（本期需新写）

| 新组件 | 路径 | 职责 |
|---|---|---|
| `MyHomePanel` | `ui/gui/widgets/my_home_panel.py` | "我的"主页：当前用户信息卡片 + 4 个标签页（作品/收藏/关注/合集） |
| `FollowListView` | `ui/gui/widgets/follow_list_view.py` | 关注列表，用户卡片 + 多选 |
| `UserListView` | `ui/gui/widgets/user_list_view.py` | 任意用户作品列表（被"关注列表→查看作品"复用） |
| `UserCardWidget` | `ui/gui/widgets/user_card.py` | 用户卡片：头像 + 昵称 + UID + 签名 + 粉丝数 + 关注数 |
| `MyCookieGuard` | `ui/gui/widgets/cookie_guard.py` | 顶部提示：未登录时禁用浏览入口并引导"扫码登录" |

### 3.3 主窗口布局升级
`ui/gui/main_window.py` 当前是 2×2 网格（资料卡/输出/功能/日志）。改造为**左侧多页签 + 右侧日志面板**：

```
┌──────────┬─────────────────────────────────────────────┐
│  Sidebar  │ TabBar: [我的] [关注的人] [收藏] [合集]    │
│  212px   ├─────────────────────────────────────────────┤
│           │                                             │
│  平台     │      MyHomePanel / FollowListView /        │
│  列表     │      CollectionView ...                    │
│           │      （带 CookieGuard 防呆）               │
│           ├─────────────────────────────────────────────┤
│           │   日志（仅一个底部面板）                    │
└──────────┴─────────────────────────────────────────────┘
```

数据流：
- `MyHomePanel` → 用户卡 → 点击作品 → 复用 `WorkCardWidget`
- `FollowListView` → 用户卡 → 跳转用户作品列表 → `WorkCardWidget`
- 任意卡片多选 → 底部统一"下载已选 N 项"按钮，复用 `BatchPreviewDialog` 二次确认
- 单击 `WorkCardWidget` → 切换资料卡（`VideoInfoWidget`）显示详情（已有）

---

## 四、新增适配器 API（按平台增量实现）

> 全部统一在 `shared/core/ops.py` 增加新 FeatureMeta，不破坏现有功能。

### 4.1 新 FeatureMeta（新增，不改旧 id）

```python
FeatureMeta("my_profile",     "我的主页",          False),  # 抖音/B站
FeatureMeta("my_posts",       "我的发布",          False),
FeatureMeta("my_favorites",   "我的收藏",          False),
FeatureMeta("follow_list",    "我的关注",          False),
FeatureMeta("user_works",     "指定用户作品",       True),   # 给一个用户主页链接
FeatureMeta("user_profile",   "指定用户资料",       True),
```

### 4.2 各平台接口实现清单

#### 抖音 douyin（参考 TikTokDownloader `interface/info.py`、`account.py`、`collection.py`）
| 新接口 | 端点 | 状态 |
|---|---|---|
| `fetch_my_profile()` | `aweme/v1/web/im/user/info/` | **新增**（参考工程已有完整签名函数） |
| `fetch_my_posts(cursor)` | `aweme/v1/web/aweme/post/` + sec_user_id=自己 | **复用** `fetch_user_posts()` |
| `fetch_my_favorites(cursor)` | `aweme/v1/web/aweme/favorite/` | **已有** `fetch_favorites` |
| `fetch_my_collects(cursor)` | `aweme/v1/web/aweme/listcollection/` | **已有** `fetch_collection` |
| `fetch_following_list(cursor)` | `aweme/v1/web/user/following/list/`（web 端） | **新增** |
| `fetch_follower_list(cursor)` | `aweme/v1/web/user/follower/list/` | **新增**（本期可不做） |
| `fetch_mix_list()` | `aweme/v1/web/mix/listcollection/` | **已有** `fetch_collection_albums` |

#### B 站 bilibili（参考 bilibili-downloader `endpoints.py`、`api/client.py`，需 WBI 签名）
| 新接口 | 端点 | 状态 |
|---|---|---|
| `fetch_my_nav()` | `/x/web-interface/nav`（解 SESSDATA） | **新增**（已有 endpoint，未用） |
| `fetch_my_videos(mid, pages)` | `/x/space/wbi/arc/search` 或 `/x/series/archives` | **已有** `fetch_user_videos` |
| `fetch_my_favorites(fid)` | `/x/v3/fav/resource/list` | **已有** `fetch_favorite_list` |
| `fetch_my_collections()` | `/x/polymer/web-space/seasons_archives_list` | **已有** |
| `fetch_my_followings(mid, pn)` | `/x/relation/followings` | **新增**（需 WBI） |
| `fetch_my_followers(mid, pn)` | `/x/relation/followers` | **新增**（本期可不做） |
| `wbi_sign(params)` | 公共方法 | **新增**（bilibili-downloader 已完整实现 `api/wbi.py`） |

#### 快手 kuaishou（参考 KS-Downloader `source/request/user.py`、`detail.py`）
- 当前仅 `live_api/profile/feedbyid` + `rest/v/profile/feed`（用户作品主页 HTML）
- 缺失：登录态验证、收藏列表、关注列表、用户作品分页
- **本期不实现"我的/关注"，只保留"指定用户作品列表"**（用 HTML 解析，参考工程已有 `extractor.py` 第 338 行 `followCount`）

#### 小红书 xiaohongshu（参考 XHS-Downloader `source/application/app.py`、`explore.py`）
- 当前仅 HTML 解析 `__INITIAL_STATE__`，无 API 封装
- 缺失：登录态、用户作品分页、收藏、关注
- **本期不实现"我的/关注"，先做"用户主页链接 → 解析个人主页"作为预研**

---

## 五、用户操作流程（端到端）

### 场景 A：抖音/B 站，"我 → 关注 → 用户作品 → 批量下载"

1. 侧栏选「抖音」→ CookieGuard 检查已登录？
2. 进入「我的主页」→ 自动调用 `fetch_my_profile()` 渲染顶部信息卡
3. 切换「关注」标签 → `fetch_following_list()` 分页加载 → 用户卡列表
4. **两种入口**：
   - **入口1**：点用户卡片 → 跳转用户作品列表（面包屑）→ `fetch_user_posts()` 分页 → `WorkCardWidget` 列表 → 多选 → 下载
   - **入口2**：勾选多个用户卡 → 「下载选中主页」按钮 → **批量并发抓取**所有用户的作品并弹出 `BatchPreviewDialog` 二次勾选 → 二次执行 → 进入下载
5. 下载：复用 `Ops.execute("account", url)`，传入 `selected=[work_id1, work_id2, ...]`

### 场景 B：任意平台，"用户主页链接 → 浏览 → 下载"

1. 顶栏粘贴 `https://www.douyin.com/user/xxx`（链接模式）
2. 调用 `extract_links()` 识别为用户主页 → `fetch_user_profile()` 拉资料 → `fetch_user_posts()` 拉作品
3. 进入 `UserListView`（直接复用关注→用户作品视图，零额外代码）

### 场景 C：单作品直链
- 当前主流程保持不变（粘贴作品链接 → `request_detail` → 资料卡 → 下载）

---

## 六、可行性结论与分期建议

### 6.1 可行性结论
- ✅ **可做**：抖音、B 站两个平台完整实现"我的→关注→用户→作品→批量下载"完整链路
- ⚠️ **可做但本期不全**：
  - 快手：仅实现"用户主页链接 → 作品列表"（HTML 解析）
  - 小红书：仅实现"作品详情"（HTML 解析），用户主页链路不实现
- ❌ **不建议做**：小红书的"关注/收藏"列表（无公开 Web API，反爬严格，收益低）

### 6.2 工期估算（新增代码量，含联调）

| 模块 | 工作量 | 说明 |
|---|---|---|
| 新增 ops FeatureMeta + 调度 | 1d | `shared/core/ops.py` + `PlatformBus` 路由 |
| douyin 关注列表 + 我的主页 | 1.5d | 复用现有 `fetch_user_posts`，新增 `fetch_my_profile/following_list` |
| bilibili 关注列表 + 我的主页 | 2d | 需移植 WBI 签名（参考工程已有完整实现） |
| kuaishou / xiaohongshu HTML 用户主页 | 1d | 用户主页 HTML 解析（参考工程已有部分实现） |
| UI 组件：MyHomePanel / FollowListView / UserCardWidget / UserListView | 3d | Qt 页面 + 标签页 + 面包屑 |
| 主窗口布局重构（多页签 + 单一日志） | 1d | 改 `main_window.py` 2×2 网格为左多页签 + 右日志 |
| CookieGuard / 多选 → 下载联动 | 0.5d | 已登录态探测 + 重新执行 `execute(feature_id, url, selected=...)` |
| 联调、PyInstaller 打包验证 | 1d | `scripts/build.py` 补充新模块 hidden-import |

**总计：约 11 工作日，2 名工程师**（前端 + 后端并行）

### 6.3 风险点
1. **WBI 签名维护成本**：B 站接口需实时更新 `img_key/Sub_key`，`bilibili-downloader/api/wbi.py` 已有完整方案可借鉴
2. **抖音签名/反爬**：`aweme/v1/web/im/user/info/` 需 X-Bogus / a-bogus 签名，已有 `platforms/douyin/encrypt/` 模块可直接复用
3. **小红书封闭生态**：本期不投入 App 式浏览，仅保留作品直链解析
4. **私有账号**：当用户关注了"私密账号"，TikTokDownloader `account.py` 已有提示文案，可复用

---

## 七、本期最小可行方案（MVP）

**第一阶段（推荐先做 1 周）**：
- ✅ **抖音** + **B 站** 完整实现
- ✅ 新增 ops 路由：`my_profile / my_posts / my_favorites / follow_list / user_works`
- ✅ 新增 UI 组件：`MyHomePanel / FollowListView / UserCardWidget / UserListView`
- ✅ 主窗口重构：多页签 + 单一日志面板
- ✅ 复用本次改造的 `WorkCardWidget`、`CoverLabel`，批量预览体验保持一致
- ⏸ 快手/小红书保留粘贴链接模式，不动

**第二阶段（视反馈再做）**：
- 快手用户主页 HTML 解析
- B 站"动态"页（`/x/polymer/web-dynamic/v1/feed/all`）
- 用户卡右键菜单（打开主页、复制 UID、关注/取关）

---

## 八、附录：与现有功能的关系

| 现有功能 | 在新流程中的角色 |
|---|---|
| `download`（粘贴链接下载） | **保留**作为场景 C 的入口，UI 上加一个"链接模式"切换 |
| `account`（账号批量下载） | **重构**：调用入口从"粘贴链接"变成"用户卡片右键 → 批量下载" |
| `collection` / `favorite_folder` | **整合**为「我的 → 收藏」标签 |
| `mix` / `series` | **整合**为「我的 → 合集」标签 |
| `live` / `comment` / `search` / `hot` / `user` | **保留**，放在侧栏"工具"分组下，不进入 App 式浏览 |

> 报告生成完毕。基于四个参考工程 + 当前 MediaDownloader 代码，给出可落地的方案与最小可行路径。
