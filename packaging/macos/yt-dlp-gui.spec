# -*- mode: python ; coding: utf-8 -*-

import os

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..', '..'))
VENDOR = os.path.join(PROJECT_ROOT, 'vendor', 'mac')

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'download_app.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        (os.path.join(VENDOR, 'bin'), 'tools/bin'),
        (os.path.join(VENDOR, 'lib'), 'tools/lib'),
    ],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='yt-dlp-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='yt-dlp-gui',
)
app = BUNDLE(
    coll,
    name='yt-dlp-gui.app',
    icon=os.path.join(SPECPATH, 'icon.icns'),
    bundle_identifier=None,
)
