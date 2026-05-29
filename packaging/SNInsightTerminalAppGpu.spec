# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules


project_root = Path.cwd()

datas = [
    (str(project_root / "config"), "config"),
    (str(project_root / "docs"), "docs"),
    (str(project_root / "ui_web"), "ui_web"),
    (str(project_root / "README.md"), "."),
    (str(project_root / "RELEASE_NOTES.md"), "."),
]
binaries = []
hiddenimports = []

for package in ("torch", "sklearn", "scipy", "xgboost", "lightgbm"):
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hiddenimports
    except Exception:
        try:
            hiddenimports += collect_submodules(package)
            binaries += collect_dynamic_libs(package)
        except Exception:
            pass

excludes = [
    "torchaudio",
    "torchvision",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    "qtpy",
    "tensorflow",
    "keras",
    "jax",
    "jaxlib",
    "cupy",
    "cupyx",
    "cupy_backends",
    "numba",
    "llvmlite",
    "pyproj",
    "pyarrow",
    "shapely",
    "geopandas",
    "matplotlib",
    "plotly",
    "panel",
    "bokeh",
    "IPython",
    "ipykernel",
    "ipywidgets",
    "jupyter",
    "jupyter_client",
    "jupyter_core",
    "jupyter_server",
    "jupyterlab",
    "notebook",
    "traitlets",
    "zmq",
    "dask",
    "distributed",
    "h5py",
    "tables",
    "skimage",
    "networkx",
    "sympy",
    "fsspec",
    "pytest",
]

a = Analysis(
    [str(project_root / "app_launcher.py")],
    pathex=[str(project_root), str(project_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(project_root / "packaging" / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SNInsightTerminal",
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
    icon=str(project_root / "assets" / "sn_insight_terminal.ico"),
    version=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SNInsightTerminal",
)
