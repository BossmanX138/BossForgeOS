# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path.cwd()
block_cipher = None

datas = []
for relative in ("assets", "voices", "schemas"):
    candidate = project_root / relative
    if candidate.exists():
        datas.append((str(candidate), relative))

a = Analysis(
    [str(project_root / "launcher" / "bossforge_launcher.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "win32api",
        "win32con",
        "win32gui",
        "pywintypes",
        "pythoncom",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "matplotlib",
        "pytest",
        "IPython",
        "sphinx",
        "notebook",
        "nbformat",
        "jupyter_client",
        "jupyter_core",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BossForgeOS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon=str(project_root / "assets" / "images" / "BossCrafts_Tray.ico"),
)
