# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path.cwd()

datas = [
    (str(project_root / "build" / "app_bundle.zip"), "."),
    (str(project_root / "assets" / "sn_insight_terminal.ico"), "assets"),
]

a = Analysis(
    [str(project_root / "packaging" / "setup_bootstrap.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SNInsightTerminal_Setup",
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
    runtime_tmpdir="_sn_setup_runtime",
    icon=str(project_root / "assets" / "sn_insight_terminal.ico"),
    version=None,
)
