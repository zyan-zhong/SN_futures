# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None
spec_path = Path(SPECPATH).resolve()
if (spec_path / "frontend").exists():
    project_root = spec_path
elif (spec_path.parent / "frontend").exists():
    project_root = spec_path.parent.resolve()
else:
    project_root = spec_path.parent.parent.resolve()
frontend_dist = project_root / "frontend" / "dist"
private_bundle_seed = project_root / "build" / "private_bundle_seed.json"

if not frontend_dist.exists():
    raise SystemExit("正式发行需要先构建 frontend/dist：请运行 packaging/build_release.ps1")

datas = [
    (str(project_root / "ui_web"), "ui_web"),
    (str(frontend_dist), "frontend/dist"),
    (str(project_root / ".env.example"), "."),
    (str(project_root / "README.md"), "."),
    (str(project_root / "docs" / "RELEASE_GUIDE.md"), "docs"),
    (str(project_root / "docs" / "TERMINAL_VALIDATION_REPORT.md"), "docs"),
    (str(project_root / "docs" / "RELEASE_PRECHECKLIST.md"), "docs"),
]

if private_bundle_seed.exists():
    datas.append((str(private_bundle_seed), "private"))

excluded = [
    "tests",
    "frontend.src",
    "frontend.node_modules",
    "node_modules",
    "release_archive",
    "torch",
    "torchaudio",
    "torchvision",
    "xgboost",
    "lightgbm",
    "catboost",
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
    "scipy",
    "sklearn",
    "hmmlearn",
    "joblib",
    "threadpoolctl",
]

a = Analysis(
    [str(project_root / "src" / "sn_futures" / "desktop_launcher.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "sn_futures.api_server",
        "sn_futures.api.terminal_api",
        "sn_futures.services.terminal_service",
    ],
    hookspath=[str(project_root / "packaging" / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SNInsightTerminal",
)
