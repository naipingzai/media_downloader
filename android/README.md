# MediaDownloader Android (Chaquopy)

使用 [Chaquopy](https://chaquo.com/chaquopy/) 将现有 Python 代码（`shared/` + `platforms/`）嵌入原生 Android 应用。

## 工程结构

```
android/
├── settings.gradle.kts          Gradle 设置
├── build.gradle.kts             根构建（AGP / Kotlin / Chaquopy 插件版本）
├── gradle.properties            Gradle 属性
└── app/
    ├── build.gradle.kts         app 模块（Chaquopy 配置 + pip 依赖）
    └── src/main/
        ├── AndroidManifest.xml  权限 + Activity 声明
        ├── java/com/mediadownloader/app/
        │   ├── App.kt           Application（初始化 Python 运行时）
        │   └── MainActivity.kt  原生 UI（平台/链接/Cookie 输入 + 解析/下载）
        ├── python/
        │   └── mediadownloader_bridge.py   Python 桥接（复用 shared/core + platforms）
        └── res/values/
            ├── styles.xml       主题
            └── strings.xml      字符串
```

## 架构说明

```
MainActivity (Kotlin UI)
    │  callAttr("parse"/"download"/"set_cookie", ...)
    ▼
mediadownloader_bridge.py
    │  import shared.core / shared.flow / platforms
    ▼
shared/ + platforms/  ← 构建时由 copyPythonSources 复制为顶层包（与桌面端 import 路径一致）
```

- **Python 依赖**（Chaquopy pip）：`aiofiles` / `curl-cffi` / `lxml` / `Pillow` / `qrcode[pil]`
- **桌面专用依赖不打包**：`PySide6`（Qt）、`pyperclip`（剪贴板）
- 图集/视频分流下载逻辑与桌面端一致（`DouyinAdapter.extract_images`）

## 构建

前置：JDK 17、Android SDK 35、Python 3.11（Chaquopy 自动下载 CPython）。

```bash
cd MediaDownloader/android
# 首次构建需下载 Gradle wrapper（或使用本机 gradle 8.9+）
gradle assembleDebug
# 输出: app/build/outputs/apk/debug/app-debug.apk
```

或用 Android Studio 打开 `MediaDownloader/android/` 目录直接构建。

## 使用

1. 启动 App → 选择平台（抖音/B站/快手/小红书）
2. （可选）粘贴 Cookie 并点「保存Cookie」（QR 登录为后续版本）
3. 粘贴作品链接 → 点「解析」查看作品信息
4. 点「下载」下载作品（图集会保存全部图片）

## 已知限制

- QR 登录暂未接入（`LoginBus` 管理器需要 UI 二维码展示，下版本）
- 批量下载（账号/合集/收藏）暂未接入（可复用 `DouyinOps._batch_download`，下版本）
- 下载目录为 App 私有存储（`~/MediaDownloader`），后续接入 MediaStore 公开存储
