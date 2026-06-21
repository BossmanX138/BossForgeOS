from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path


APP_DIR_NAME = "BossForgeOS"
INSTALLER_NAME = "Install BossForge_OS.exe"


def bundled_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def default_install_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Programs" / APP_DIR_NAME
    return Path.home() / "AppData" / "Local" / "Programs" / APP_DIR_NAME


def create_shortcut(shortcut_path: Path, target_path: Path, icon_path: Path | None = None) -> None:
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    ps_icon = f"$shortcut.IconLocation = '{icon_path}'" if icon_path and icon_path.exists() else ""
    command = f"""
$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut('{shortcut_path}')
$shortcut.TargetPath = '{target_path}'
$shortcut.WorkingDirectory = '{target_path.parent}'
{ps_icon}
$shortcut.Save()
""".strip()
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
    )


def install_payload(install_dir: Path, payload_zip: Path) -> Path:
    install_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(payload_zip, "r") as archive:
        archive.extractall(install_dir)
    bossforge_root = install_dir / APP_DIR_NAME
    if not bossforge_root.exists():
        raise FileNotFoundError(f"Expected extracted payload folder missing: {bossforge_root}")
    return bossforge_root


def write_install_manifest(install_root: Path) -> Path:
    manifest = {
        "product": APP_DIR_NAME,
        "installedAt": datetime.now().astimezone().isoformat(),
        "installer": INSTALLER_NAME,
    }
    manifest_path = install_root / "install_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install BossForgeOS into the local machine profile.")
    parser.add_argument("--install-dir", default="", help="Override installation directory")
    parser.add_argument("--no-launch", action="store_true", help="Do not launch BossForgeOS after install")
    parser.add_argument("--clean", action="store_true", help="Clear the install directory before extracting payload")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload_zip = bundled_path("bossforge_payload.zip")
    if not payload_zip.exists():
        raise SystemExit(f"Missing bundled payload archive: {payload_zip}")

    install_dir = Path(args.install_dir).expanduser().resolve() if args.install_dir else default_install_dir().resolve()
    if args.clean and install_dir.exists():
        shutil.rmtree(install_dir)

    print(f"Installing BossForgeOS into: {install_dir}")
    app_root = install_payload(install_dir, payload_zip)
    manifest_path = write_install_manifest(app_root)

    exe_path = app_root / "BossForgeOS.exe"
    icon_path = app_root / "assets" / "images" / "BossCrafts_Tray.ico"
    desktop = Path.home() / "Desktop" / "BossForgeOS.lnk"
    start_menu = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "BossForgeOS.lnk"

    try:
        create_shortcut(desktop, exe_path, icon_path)
        create_shortcut(start_menu, exe_path, icon_path)
    except subprocess.CalledProcessError as exc:
        print("Warning: shortcut creation failed")
        print(exc.stderr or exc.stdout or str(exc))

    print(f"Install manifest written: {manifest_path}")
    print(f"Installed launcher: {exe_path}")
    if not args.no_launch:
        subprocess.Popen([str(exe_path)], cwd=str(app_root))


if __name__ == "__main__":
    main()
