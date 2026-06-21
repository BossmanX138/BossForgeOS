from pathlib import Path

from installer.build_release_payload import build_payload_manifest, build_release_manifest


def test_build_payload_manifest_includes_launcher_and_assets(tmp_path: Path) -> None:
    for relative in ("assets", "launcher", "core", "ui"):
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)
    manifest = build_payload_manifest(project_root=tmp_path)
    include_roots = {entry["path"] for entry in manifest["include"]}
    assert "assets" in include_roots
    assert "launcher" in include_roots


def test_release_manifest_uses_bossforgeos_installer_name() -> None:
    manifest = build_release_manifest("abc123", "Install BossForge_OS.exe")
    assert manifest["artifactName"] == "Install BossForge_OS.exe"
    assert manifest["product"] == "BossForgeOS"
