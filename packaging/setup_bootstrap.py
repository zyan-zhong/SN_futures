from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, ttk


APP_NAME = "SN Insight Terminal"
APP_EXE = "SNInsightTerminal.exe"


def bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def install_dir() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "Programs" / APP_NAME
    return Path.home() / "AppData" / "Local" / "Programs" / APP_NAME


def bundle_zip_path() -> Path:
    return bundle_root() / "app_bundle.zip"


def create_shortcuts(exe_path: Path, uninstall_path: Path) -> None:
    escaped_exe = str(exe_path).replace("'", "''")
    escaped_uninstall = str(uninstall_path).replace("'", "''")
    escaped_workdir = str(exe_path.parent).replace("'", "''")
    script = f"""
$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$programs = [Environment]::GetFolderPath('Programs')
$folder = Join-Path $programs 'SN Insight Terminal'
if (-not (Test-Path $folder)) {{ New-Item -ItemType Directory -Path $folder | Out-Null }}

$desktopShortcut = $shell.CreateShortcut((Join-Path $desktop 'SN Insight Terminal.lnk'))
$desktopShortcut.TargetPath = '{escaped_exe}'
$desktopShortcut.WorkingDirectory = '{escaped_workdir}'
$desktopShortcut.Save()

$startShortcut = $shell.CreateShortcut((Join-Path $folder 'SN Insight Terminal.lnk'))
$startShortcut.TargetPath = '{escaped_exe}'
$startShortcut.WorkingDirectory = '{escaped_workdir}'
$startShortcut.Save()

$uninstallShortcut = $shell.CreateShortcut((Join-Path $folder 'Uninstall SN Insight Terminal.lnk'))
$uninstallShortcut.TargetPath = '{escaped_uninstall}'
$uninstallShortcut.WorkingDirectory = '{escaped_workdir}'
$uninstallShortcut.Save()
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def write_uninstall_script(target_dir: Path) -> Path:
    uninstall_path = target_dir / "uninstall.cmd"
    script = (
        "@echo off\n"
        "setlocal\n"
        f"set \"APP_DIR={target_dir}\"\n"
        "powershell -NoProfile -ExecutionPolicy Bypass -Command "
        "\"$desktop=[Environment]::GetFolderPath('Desktop');"
        " $desktopShortcut=Join-Path $desktop 'SN Insight Terminal.lnk';"
        " if (Test-Path $desktopShortcut) { Remove-Item -LiteralPath $desktopShortcut -Force };"
        " $folder=Join-Path ([Environment]::GetFolderPath('Programs')) 'SN Insight Terminal';"
        " if (Test-Path $folder) { Remove-Item -LiteralPath $folder -Recurse -Force }\" \n"
        "taskkill /IM SNInsightTerminal.exe /F >nul 2>nul\n"
        "start \"\" /min cmd /c \"timeout /t 2 /nobreak >nul & rmdir /S /Q \"\"%APP_DIR%\"\"\"\n"
        "exit /b 0\n"
    )
    uninstall_path.write_text(script, encoding="utf-8")
    return uninstall_path


def extract_bundle(zip_path: Path, target_dir: Path, status_var: tk.StringVar, progress_bar, root: tk.Tk) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as archive:
        members = archive.infolist()
        total = max(1, len(members))
        progress_bar["maximum"] = total + 2
        for idx, member in enumerate(members, start=1):
            status_var.set(f"Extracting {member.filename}")
            archive.extract(member, target_dir)
            progress_bar["value"] = idx
            root.update_idletasks()


def run_smoke_test() -> None:
    marker_path = os.environ.get("SN_SETUP_SMOKE_MARKER")
    marker = Path(marker_path) if marker_path else Path.cwd() / "setup_smoke_ok.txt"
    marker.write_text(
        f"ok {datetime.now().isoformat()} | bundle={bundle_zip_path().exists()}",
        encoding="utf-8",
    )
    os._exit(0)


def main() -> None:
    if "--smoke-test" in sys.argv:
        run_smoke_test()

    zip_path = bundle_zip_path()
    if not zip_path.exists():
        messagebox.showerror("Setup failed", f"Missing installer bundle:\n{zip_path}")
        raise SystemExit(1)

    root = tk.Tk()
    root.title(f"{APP_NAME} Setup")
    root.geometry("560x300")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text=APP_NAME, font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
    ttk.Label(
        frame,
        text=(
            "This installer is for Shanghai Futures Exchange tin futures research only. "
            "All outputs are research reference and do not constitute investment advice."
        ),
        wraplength=500,
        justify="left",
    ).pack(anchor="w", pady=(8, 12))
    ttk.Label(
        frame,
        text=f"Default install location: {install_dir()}",
        wraplength=500,
        justify="left",
    ).pack(anchor="w", pady=(0, 12))

    status_var = tk.StringVar(value="Click Install to deploy the local desktop terminal.")
    ttk.Label(frame, textvariable=status_var, wraplength=500, justify="left").pack(anchor="w", pady=(0, 10))
    progress = ttk.Progressbar(frame, mode="determinate", length=500)
    progress.pack(anchor="w", pady=(0, 12))

    button_bar = ttk.Frame(frame)
    button_bar.pack(anchor="e", fill="x")

    def do_install() -> None:
        install_btn.configure(state="disabled")
        cancel_btn.configure(state="disabled")
        try:
            target_dir = install_dir()
            extract_bundle(zip_path, target_dir, status_var, progress, root)
            progress["value"] = progress["maximum"] - 1
            status_var.set("Creating shortcuts and uninstall entry...")
            root.update_idletasks()
            uninstall_path = write_uninstall_script(target_dir)
            exe_path = target_dir / APP_EXE
            create_shortcuts(exe_path, uninstall_path)
            progress["value"] = progress["maximum"]
            status_var.set("Install complete. Launching desktop terminal...")
            root.update_idletasks()
            subprocess.Popen([str(exe_path), "--installed"])
        except Exception as exc:
            messagebox.showerror("Setup failed", f"Installer error:\n\n{exc}", parent=root)
            root.destroy()
            raise SystemExit(1)
        else:
            messagebox.showinfo("Install complete", "Desktop shortcut created. The app will start now.", parent=root)
            root.destroy()
            raise SystemExit(0)

    install_btn = ttk.Button(button_bar, text="Install", command=do_install)
    cancel_btn = ttk.Button(button_bar, text="Cancel", command=root.destroy)
    cancel_btn.pack(side="right")
    install_btn.pack(side="right", padx=(0, 8))

    root.mainloop()


if __name__ == "__main__":
    main()
