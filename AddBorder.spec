# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['d:/Users/John/OneDrive/Apps/AddWhiteBorder/AddBorder.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('graphics/addBorderIcon32.png', 'graphics'),
        ('graphics/addBorderIcon64.png', 'graphics'),
        ('graphics/addBorderIcon72.png', 'graphics'),
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
    a.binaries,
    a.datas,
    [],
    name='AddBorder',
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
