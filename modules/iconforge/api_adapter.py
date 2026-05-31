from __future__ import annotations

from pathlib import Path
from typing import Any

from modules.iconforge import service as iconforge_service


def list_backups(project_root: Path) -> tuple[dict[str, Any], int]:
    try:
        forge = iconforge_service.get_forge(project_root)
        return {"ok": True, "items": forge.list_backups()}, 200
    except Exception as exc:
        return {"ok": False, "message": str(exc), "items": {}}, 500


def resolve_preview_path(project_root: Path, raw_path: str) -> tuple[Path | None, dict[str, Any] | None, int]:
    raw = str(raw_path or "").strip()
    if not raw:
        return None, {"ok": False, "message": "path is required"}, 400

    candidate = Path(raw).expanduser()
    candidate = (project_root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()

    allowed = {".ico", ".png", ".gif", ".jpg", ".jpeg", ".webp", ".bmp", ".svg"}
    if candidate.suffix.lower() not in allowed:
        return None, {"ok": False, "message": "unsupported preview extension"}, 400
    if not candidate.exists() or not candidate.is_file():
        return None, {"ok": False, "message": "preview file not found"}, 404
    return candidate, None, 200


def apply_icon(project_root: Path, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    target_type = str(payload.get("target_type", "folder")).strip().lower()
    target = str(payload.get("target", "")).strip()
    icon = str(payload.get("icon", "")).strip()
    if not target or not icon:
        return {"ok": False, "message": "target and icon are required"}, 400

    icon_path = Path(icon)
    if not icon_path.is_absolute():
        icon_path = (project_root / icon_path).resolve()

    forge = iconforge_service.get_forge(project_root)
    if target_type == "folder":
        result = forge.set_folder_icon(target, str(icon_path))
    elif target_type == "shortcut":
        result = forge.set_shortcut_icon(target, str(icon_path))
    elif target_type == "file_extension":
        result = forge.set_file_extension_icon(target, str(icon_path))
    elif target_type == "application":
        result = forge.set_application_icon(target, str(icon_path))
    elif target_type == "drive":
        result = forge.set_drive_icon(target, str(icon_path))
    else:
        return {"ok": False, "message": f"unsupported target_type: {target_type}"}, 400

    return result, (200 if result.get("ok") else 400)


def refresh_icon_cache(project_root: Path) -> tuple[dict[str, Any], int]:
    result = iconforge_service.get_forge(project_root).refresh_icon_cache()
    return result, (200 if result.get("ok") else 400)


def restore_backup(project_root: Path, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    backup_key = str(payload.get("backup_key", "")).strip()
    if not backup_key:
        return {"ok": False, "message": "backup_key is required"}, 400
    result = iconforge_service.get_forge(project_root).restore(backup_key)
    return result, (200 if result.get("ok") else 400)


def export_pack(project_root: Path, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    output_dir = str(payload.get("output_dir", "")).strip()
    if not output_dir:
        return {"ok": False, "message": "output_dir is required"}, 400
    result = iconforge_service.get_forge(project_root).export_icon_set(output_dir)
    return result, (200 if result.get("ok") else 400)


def import_pack(project_root: Path, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    source = str(payload.get("source", "")).strip()
    apply_changes = bool(payload.get("apply_changes", True))
    refresh_cache = bool(payload.get("refresh_cache", False))
    if not source:
        return {"ok": False, "message": "source is required"}, 400
    result = iconforge_service.get_forge(project_root).import_icon_set(
        source=source,
        apply_changes=apply_changes,
        refresh_cache=refresh_cache,
    )
    return result, (200 if result.get("ok") else 400)
