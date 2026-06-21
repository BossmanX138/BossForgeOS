# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path.cwd()
payload_dir = project_root / "installer" / "payload"
block_cipher = None

a = Analysis(
    [str(project_root / "installer" / "install_bossforge_os.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(payload_dir / "bossforge_payload.zip"), "."),
        (str(payload_dir / "release_manifest.json"), "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="Install BossForge_OS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon=str(project_root / "assets" / "images" / "BossCrafts_Tray.ico"),
)
