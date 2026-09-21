"""PyInstaller hook: 收集所有平台模块。"""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = (
    collect_submodules('platforms') +
    collect_submodules('shared.core') +
    collect_submodules('shared.flow') +
    collect_submodules('shared.translation') +
    [
        'platforms.douyin.encrypt.douyin_params',
        'platforms.douyin.encrypt.websign',
        'shared.core.ops',
        'shared.core.adapter',
        'shared.core.config',
        'shared.core.ffmpeg',
        'shared.core.cookies',
        'shared.core.session',
        'shared.core.storage',
        'shared.core.i18n',
        'shared.core.constants',
        'shared.core.format',
        'shared.flow.link',
        'shared.flow.download',
    ]
)
