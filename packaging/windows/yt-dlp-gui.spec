# -*- mode: python ; coding: utf-8 -*-

import os

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..', '..'))
VENDOR = os.path.join(PROJECT_ROOT, 'vendor', 'win')

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'download_app.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
    # Windows ffmpeg/deno builds are statically linked, so unlike macOS there is
    # no companion lib/ directory to ship.
    datas=[
        (os.path.join(VENDOR, 'bin'), 'tools/bin'),
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
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(SPECPATH, 'icon.ico'),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='yt-dlp-gui',
)
