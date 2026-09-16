from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


DEFAULT_INCLUDE = (
    ("assets", "dir"),
    ("launcher", "dir"),
    ("core", "dir"),
    ("ui", "dir"),
    ("modules", "dir"),
    ("voices", "dir"),
    ("schemas", "dir"),
    ("scripts", "dir"),
)


def build_payload_manifest(project_root: Path) -> dict[str, object]:
    include: list[dict[str, str]] = []
    for relative, kind in DEFAULT_INCLUDE:
        target = project_root / relative
        if target.exists():
            include.append({"path": relative, "kind": kind})
    return {"include": include}


def build_release_manifest(
    source_commit: str,
    artifact_name: str,
    *,
    version: str = "0.1.3",
    build_id: str | None = None,
    artifact_path: str | None = None,
) -> dict[str, object]:
    stamp = datetime.now().astimezone()
    build_token = build_id or stamp.strftime("%Y%m%d-%H%M%S")
    return {
        "product": "BossForgeOS",
        "artifactName": artifact_name,
        "version": version,
        "buildId": build_token,
        "builtAt": stamp.isoformat(),
        "sourceCommit": source_commit,
        "artifact": artifact_path or artifact_name,
    }


def create_payload_archive(
    *,
    project_root: Path,
    launcher_exe: Path,
    output_dir: Path,
    version: str,
    build_id: str,
    source_commit: str,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload_zip = output_dir / "bossforge_payload.zip"
    payload_root = output_dir / "payload_root"
    if payload_root.exists():
        shutil.rmtree(payload_root)
    payload_root.mkdir(parents=True, exist_ok=True)

    if not launcher_exe.exists():
        raise FileNotFoundError(f"BossForgeOS launcher executable not found: {launcher_exe}")

    install_root = payload_root / "BossForgeOS"
    install_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(launcher_exe, install_root / "BossForgeOS.exe")

    tray_icon = project_root / "assets" / "images" / "BossCrafts_Tray.ico"
    if tray_icon.exists():
        icon_dir = install_root / "assets" / "images"
        icon_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tray_icon, icon_dir / tray_icon.name)

    readme_path = install_root / "README_INSTALLED.txt"
    readme_path.write_text(
        "\n".join(
            [
                "BossForgeOS Installed Payload",
                "",
                f"Version: {version}",
                f"Build ID: {build_id}",
                f"Source Commit: {source_commit}",
                "",
                "Launch BossForgeOS.exe to open the forge.",
            ]
        ),
        encoding="utf-8",
    )

    payload_manifest = build_payload_manifest(project_root)
    (output_dir / "payload_manifest.json").write_text(
        json.dumps(payload_manifest, indent=2),
        encoding="utf-8",
    )

    with zipfile.ZipFile(payload_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in install_root.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(payload_root))

    release_manifest = build_release_manifest(
        source_commit,
        "Install BossForge_OS.exe",
        version=version,
        build_id=build_id,
    )
    manifest_path = output_dir / "release_manifest.json"
    manifest_path.write_text(json.dumps(release_manifest, indent=2), encoding="utf-8")
    return {
        "payload_zip": payload_zip,
        "payload_manifest": output_dir / "payload_manifest.json",
        "release_manifest": manifest_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build BossForgeOS installer payload files.")
    parser.add_argument("--project-root", default=".", help="BossForgeOS project root")
    parser.add_argument("--launcher-exe", required=True, help="Built BossForgeOS.exe path")
    parser.add_argument("--output-dir", default="installer/payload", help="Payload output directory")
    parser.add_argument("--version", default="0.1.3", help="Release version")
    parser.add_argument("--build-id", required=True, help="Build identifier")
    parser.add_argument("--source-commit", required=True, help="Source git commit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = create_payload_archive(
        project_root=Path(args.project_root).resolve(),
        launcher_exe=Path(args.launcher_exe).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        version=str(args.version),
        build_id=str(args.build_id),
        source_commit=str(args.source_commit),
    )
    for label, value in outputs.items():
        print(f"{label}: {value}")


if __name__ == "__main__":
    main()
