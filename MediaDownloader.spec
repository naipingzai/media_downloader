# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/home/npznnz/Project/MediaDownloader/main.py'],
    pathex=[],
    binaries=[],
    datas=[('/home/npznnz/Project/MediaDownloader/build/ffmpeg', '.'), ('/home/npznnz/Project/MediaDownloader/ui/gui/resources/styles.qss', 'ui/gui/resources')],
    hiddenimports=['curl_cffi', 'curl_cffi._curl_cffi', 'PySide6', 'PySide6.QtWidgets', 'PySide6.QtCore', 'PySide6.QtGui', 'qrcode', 'PIL', 'PIL.Image', 'platforms', 'platforms.douyin', 'platforms.douyin.adapter', 'platforms.douyin.ops', 'platforms.douyin.login', 'platforms.douyin.encrypt', 'platforms.douyin.encrypt.douyin_params', 'platforms.douyin.encrypt.websign', 'platforms.kuaishou', 'platforms.kuaishou.adapter', 'platforms.kuaishou.ops', 'platforms.kuaishou.login', 'platforms.xiaohongshu', 'platforms.xiaohongshu.adapter', 'platforms.xiaohongshu.ops', 'platforms.xiaohongshu.login', 'platforms.bilibili', 'platforms.bilibili.adapter', 'platforms.bilibili.ops', 'platforms.bilibili.login', 'shared.core.ops', 'shared.core.adapter', 'shared.core.config', 'shared.core.ffmpeg', 'shared.core.cookies', 'shared.core.session', 'shared.core.storage', 'shared.core.i18n', 'shared.core.constants', 'shared.core.format', 'shared.flow.link', 'shared.flow.download'],
    hookspath=['/home/npznnz/Project/MediaDownloader/hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MediaDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
