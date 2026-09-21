# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/home/npznnz/Project/MediaDownloader/main.py'],
    pathex=[],
    binaries=[],
    datas=[('/home/npznnz/Project/MediaDownloader/build/ffmpeg', '.'), ('/home/npznnz/Project/MediaDownloader/ui/gui/resources/styles.qss', 'ui/gui/resources')],
    hiddenimports=['curl_cffi', 'PySide6', 'qrcode', 'PIL'],
    hookspath=[],
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
