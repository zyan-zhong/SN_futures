from PyInstaller import compat
from PyInstaller.utils.hooks import collect_delvewheel_libs_directory, collect_submodules, get_installer

from packaging.version import Version


pandas_version = Version(compat.importlib_metadata.version("pandas")).release
pandas_installer = get_installer("pandas")

datas = []
binaries = []
hiddenimports = collect_submodules("pandas._libs") + ["cmath"]
excludedimports = [
    "pyarrow",
    "openpyxl",
    "jinja2",
    "lxml",
    "matplotlib",
]

if compat.is_win and pandas_version >= (2, 1, 0) and pandas_installer != "conda":
    datas, binaries = collect_delvewheel_libs_directory("pandas", datas=datas, binaries=binaries)
