from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
import hashlib
import time
from io import BytesIO
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = REPO_ROOT / "core"

SOUNDFORGE_CONFIG_PATH = CORE_DIR / "soundforge_config.json"
LEGACY_SOUNDSTAGE_CONFIG_PATH = CORE_DIR / "soundstage_config.json"
SOUNDFORGE_SCHEMES_DIR = CORE_DIR / "soundforge_schemes"
LEGACY_SOUNDSTAGE_SCHEMES_DIR = CORE_DIR / "soundstage_schemes"
SOUNDFORGE_SOUNDS_DIR = SOUNDFORGE_SCHEMES_DIR / "sounds"
LEGACY_SOUNDSTAGE_SOUNDS_DIR = LEGACY_SOUNDSTAGE_SCHEMES_DIR / "sounds"
_SCHEME_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")
_RESERVED_SCHEME_DIRS = {"sounds", "__pycache__"}
_LEGACY_EVENT_ALIASES = {
    "open_app": "open_program",
    "close_app": "close_program",
    "app_open": "open_program",
    "app_close": "close_program",
}


def ensure_layout() -> None:
    SOUNDFORGE_SCHEMES_DIR.mkdir(parents=True, exist_ok=True)
    SOUNDFORGE_SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_SOUNDSTAGE_SCHEMES_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_SOUNDSTAGE_SOUNDS_DIR.mkdir(parents=True, exist_ok=True)


def source_config_path() -> Path:
    return SOUNDFORGE_CONFIG_PATH if SOUNDFORGE_CONFIG_PATH.exists() else LEGACY_SOUNDSTAGE_CONFIG_PATH


def load_active_config() -> dict[str, Any]:
    path = source_config_path()
    if not path.exists():
        return {"global": {}, "per_app": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"global": {}, "per_app": {}}
    if not isinstance(payload, dict):
        return {"global": {}, "per_app": {}}
    payload.setdefault("global", {})
    payload.setdefault("per_app", {})
    return normalize_config(payload)


def save_active_config(config: dict[str, Any]) -> None:
    ensure_layout()
    config = normalize_config(config)
    body = json.dumps(config, indent=2)
    SOUNDFORGE_CONFIG_PATH.write_text(body, encoding="utf-8")
    LEGACY_SOUNDSTAGE_CONFIG_PATH.write_text(body, encoding="utf-8")


def list_schemes() -> list[str]:
    ensure_layout()
    names: list[str] = []
    for root in (SOUNDFORGE_SCHEMES_DIR, LEGACY_SOUNDSTAGE_SCHEMES_DIR):
        if not root.exists():
            continue
        for item in sorted(root.iterdir()):
            if item.is_dir() and item.name not in _RESERVED_SCHEME_DIRS:
                names.append(item.name)
    return sorted(set(names))


def _normalize_scheme_name(value: str) -> str:
    raw = (value or "").strip()
    clean = _SCHEME_NAME_RE.sub("_", raw).strip("._-")
    return clean or "imported_scheme"


def rewrite_config_paths(config: dict[str, Any], sound_dir: str = "sounds") -> dict[str, Any]:
    def rewrite_entry(entry: Any) -> Any:
        if not isinstance(entry, dict):
            return entry
        files = entry.get("files", [])
        if isinstance(files, list):
            entry["files"] = [os.path.join(sound_dir, os.path.basename(str(f))) for f in files]
        return entry

    if isinstance(config.get("global"), dict):
        for k, v in list(config["global"].items()):
            config["global"][k] = rewrite_entry(v)
    if isinstance(config.get("per_app"), dict):
        for app, events in list(config["per_app"].items()):
            if not isinstance(events, dict):
                continue
            for k, v in list(events.items()):
                config["per_app"][app][k] = rewrite_entry(v)
    return normalize_config(config)


def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {"global": {}, "per_app": {}}
    config.setdefault("global", {})
    config.setdefault("per_app", {})
    if not isinstance(config["global"], dict):
        config["global"] = {}
    if not isinstance(config["per_app"], dict):
        config["per_app"] = {}

    # Normalize legacy event names at global scope.
    for legacy_name, canonical_name in _LEGACY_EVENT_ALIASES.items():
        if legacy_name in config["global"] and canonical_name not in config["global"]:
            config["global"][canonical_name] = config["global"][legacy_name]

    # Normalize legacy event names in per-app mappings.
    for app_name, events in list(config["per_app"].items()):
        if not isinstance(events, dict):
            config["per_app"][app_name] = {}
            continue
        for legacy_name, canonical_name in _LEGACY_EVENT_ALIASES.items():
            if legacy_name in events and canonical_name not in events:
                events[canonical_name] = events[legacy_name]
    return config


def resolve_sound_path(path: str | None) -> str | None:
    if not path:
        return None
    candidate = Path(path)
    if candidate.is_absolute() and candidate.exists():
        return str(candidate)
    for root in (SOUNDFORGE_SOUNDS_DIR, LEGACY_SOUNDSTAGE_SOUNDS_DIR):
        maybe = root / os.path.basename(path)
        if maybe.exists():
            return str(maybe)
    return str(candidate) if candidate.exists() else None


def _gather_sound_files(config: dict[str, Any]) -> set[str]:
    out: set[str] = set()

    def gather_entry(entry: Any) -> None:
        if not isinstance(entry, dict):
            return
        files = entry.get("files", [])
        if not isinstance(files, list):
            return
        for f in files:
            if not f:
                continue
            resolved = resolve_sound_path(str(f))
            if resolved:
                out.add(resolved)

    global_map = config.get("global", {})
    if isinstance(global_map, dict):
        for value in global_map.values():
            gather_entry(value)

    per_app = config.get("per_app", {})
    if isinstance(per_app, dict):
        for events in per_app.values():
            if isinstance(events, dict):
                for value in events.values():
                    gather_entry(value)

    return out


def _iter_config_entries(config: dict[str, Any]):
    global_map = config.get("global", {})
    if isinstance(global_map, dict):
        for event_name, value in global_map.items():
            yield ("global", None, str(event_name), value)
    per_app = config.get("per_app", {})
    if isinstance(per_app, dict):
        for app_name, events in per_app.items():
            if not isinstance(events, dict):
                continue
            for event_name, value in events.items():
                yield ("per_app", str(app_name), str(event_name), value)


def diagnose_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_layout()
    cfg = config if isinstance(config, dict) else load_active_config()
    problems: list[dict[str, Any]] = []
    total_entries = 0
    total_files = 0
    resolved_files = 0

    for scope, app, event_name, entry in _iter_config_entries(cfg):
        total_entries += 1
        if not isinstance(entry, dict):
            problems.append({"scope": scope, "app": app, "event": event_name, "issue": "entry_not_object"})
            continue
        files = entry.get("files", [])
        if not isinstance(files, list):
            problems.append({"scope": scope, "app": app, "event": event_name, "issue": "files_not_list"})
            continue
        for f in files:
            total_files += 1
            resolved = resolve_sound_path(str(f))
            if resolved:
                resolved_files += 1
            else:
                problems.append(
                    {
                        "scope": scope,
                        "app": app,
                        "event": event_name,
                        "issue": "missing_sound_file",
                        "path": str(f),
                    }
                )

    return {
        "ok": len(problems) == 0,
        "summary": {
            "entries": total_entries,
            "files_referenced": total_files,
            "files_resolved": resolved_files,
            "files_missing": max(0, total_files - resolved_files),
        },
        "problems": problems,
    }


def _checksum_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_bundle(bundle_stream: Any) -> dict[str, Any]:
    raw = bundle_stream.read() if hasattr(bundle_stream, "read") else b""
    if hasattr(bundle_stream, "seek"):
        bundle_stream.seek(0)
    if not raw:
        return {"ok": False, "message": "empty bundle stream"}
    problems: list[str] = []
    checksums: dict[str, str] = {}
    config = None
    try:
        with zipfile.ZipFile(BytesIO(raw), "r") as archive:
            names = archive.namelist()
            config_name = "soundforge_config.json" if "soundforge_config.json" in names else "soundstage_config.json"
            if config_name not in names:
                problems.append("bundle missing soundforge_config.json/soundstage_config.json")
            else:
                try:
                    config = json.loads(archive.read(config_name).decode("utf-8", errors="replace"))
                    if not isinstance(config, dict):
                        problems.append("bundle config is not a JSON object")
                except Exception as ex:
                    problems.append(f"bundle config parse failed: {ex}")
            for info in archive.infolist():
                if info.is_dir():
                    continue
                p = info.filename.replace("\\", "/")
                if p.startswith("sounds/"):
                    data = archive.read(info.filename)
                    checksums[p] = hashlib.sha256(data).hexdigest()
    except zipfile.BadZipFile:
        return {"ok": False, "message": "invalid zip bundle"}

    diag = diagnose_config(config) if isinstance(config, dict) else {"ok": False, "summary": {}, "problems": []}
    return {
        "ok": len(problems) == 0 and bool(diag.get("ok", False)),
        "problems": problems,
        "config_diagnostics": diag,
        "checksums": checksums,
    }


def export_bundle(bundle_path: Path) -> Path:
    ensure_layout()
    config = normalize_config(load_active_config())
    sound_files = _gather_sound_files(config)
    config_for_bundle = rewrite_config_paths(json.loads(json.dumps(config)), sound_dir="sounds")

    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("soundforge_config.json", json.dumps(config_for_bundle, indent=2))
        for file_path in sorted(sound_files):
            path = Path(file_path)
            if path.exists() and path.is_file():
                archive.write(path, arcname=str(Path("sounds") / path.name))
    return bundle_path


def import_bundle(bundle_stream: Any, scheme_name: str, collision_policy: str = "rename") -> dict[str, Any]:
    ensure_layout()
    safe_name = _normalize_scheme_name(str(scheme_name or "imported_scheme"))
    scheme_dir = SOUNDFORGE_SCHEMES_DIR / safe_name
    if scheme_dir.exists():
        policy = str(collision_policy or "rename").strip().lower()
        if policy == "fail":
            raise FileExistsError(f"scheme already exists: {safe_name}")
        if policy == "replace":
            shutil.rmtree(scheme_dir, ignore_errors=True)
            scheme_dir.mkdir(parents=True, exist_ok=True)
        else:
            idx = 2
            while scheme_dir.exists():
                scheme_dir = SOUNDFORGE_SCHEMES_DIR / f"{safe_name}_{idx}"
                idx += 1
            safe_name = scheme_dir.name
    scheme_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(bundle_stream, "r") as archive:
        archive.extractall(scheme_dir)

    sounds_src = scheme_dir / "sounds"
    imported_files: list[dict[str, Any]] = []
    if sounds_src.exists() and sounds_src.is_dir():
        for item in sounds_src.iterdir():
            if item.is_file():
                dst = SOUNDFORGE_SOUNDS_DIR / item.name
                if dst.exists():
                    stem = dst.stem
                    suf = dst.suffix
                    j = 2
                    while dst.exists():
                        dst = SOUNDFORGE_SOUNDS_DIR / f"{stem}_{j}{suf}"
                        j += 1
                shutil.copy2(item, dst)
                imported_files.append({"source": item.name, "stored_as": dst.name, "sha256": _checksum_file(dst)})

    config_path = scheme_dir / "soundforge_config.json"
    if not config_path.exists():
        config_path = scheme_dir / "soundstage_config.json"
    if not config_path.exists():
        raise FileNotFoundError("bundle missing soundforge_config.json/soundstage_config.json")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("bundle config is not a JSON object")
    config = normalize_config(rewrite_config_paths(config, sound_dir="core/soundforge_schemes/sounds"))
    save_active_config(config)
    return {"ok": True, "scheme_name": safe_name, "imported_files": imported_files, "diagnostics": diagnose_config(config)}


def load_scheme_config(scheme_name: str) -> dict[str, Any]:
    safe_name = _normalize_scheme_name(str(scheme_name or ""))
    if not safe_name:
        raise ValueError("scheme_name is required")
    scheme_dir = SOUNDFORGE_SCHEMES_DIR / safe_name
    config_path = scheme_dir / "soundforge_config.json"
    if not config_path.exists():
        config_path = scheme_dir / "soundstage_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"scheme config not found for {safe_name}")
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError("scheme config is not a JSON object")
    return normalize_config(cfg)


def activate_scheme(scheme_name: str) -> dict[str, Any]:
    cfg = load_scheme_config(scheme_name)
    cfg = normalize_config(rewrite_config_paths(cfg, sound_dir="core/soundforge_schemes/sounds"))
    save_active_config(cfg)
    return {"ok": True, "scheme_name": _normalize_scheme_name(scheme_name), "diagnostics": diagnose_config(cfg)}


def migration_status() -> dict[str, Any]:
    ensure_layout()
    active_path = source_config_path()
    cfg = load_active_config()
    diag = diagnose_config(cfg)
    legacy_scheme_dirs = []
    if LEGACY_SOUNDSTAGE_SCHEMES_DIR.exists():
        for d in LEGACY_SOUNDSTAGE_SCHEMES_DIR.iterdir():
            if d.is_dir() and d.name not in _RESERVED_SCHEME_DIRS:
                legacy_scheme_dirs.append(d.name)
    legacy_sound_files = 0
    if LEGACY_SOUNDSTAGE_SOUNDS_DIR.exists():
        legacy_sound_files = len([p for p in LEGACY_SOUNDSTAGE_SOUNDS_DIR.glob("*") if p.is_file()])
    aliases_present = []
    global_map = cfg.get("global", {}) if isinstance(cfg.get("global"), dict) else {}
    for old_key in _LEGACY_EVENT_ALIASES:
        if old_key in global_map:
            aliases_present.append(old_key)
    safe_to_remove_soundstage = (
        active_path == SOUNDFORGE_CONFIG_PATH
        and len(legacy_scheme_dirs) == 0
        and legacy_sound_files == 0
        and len(aliases_present) == 0
        and bool(diag.get("ok"))
    )
    return {
        "active_config_path": str(active_path),
        "legacy_scheme_dirs": legacy_scheme_dirs,
        "legacy_sound_file_count": legacy_sound_files,
        "legacy_event_aliases_present": aliases_present,
        "diagnostics_ok": bool(diag.get("ok")),
        "safe_to_remove_soundstage": safe_to_remove_soundstage,
    }


def migrate_legacy_to_soundforge(collision_policy: str = "rename") -> dict[str, Any]:
    ensure_layout()
    migrated_schemes: list[str] = []
    copied_sounds: int = 0
    if LEGACY_SOUNDSTAGE_SCHEMES_DIR.exists():
        for d in sorted(LEGACY_SOUNDSTAGE_SCHEMES_DIR.iterdir()):
            if not d.is_dir() or d.name in _RESERVED_SCHEME_DIRS:
                continue
            cfg_path = d / "soundstage_config.json"
            if not cfg_path.exists():
                cfg_path = d / "soundforge_config.json"
            if cfg_path.exists():
                with cfg_path.open("rb") as f:
                    result = import_bundle(f, scheme_name=d.name, collision_policy=collision_policy)
                    migrated_schemes.append(str(result.get("scheme_name", d.name)))
    if LEGACY_SOUNDSTAGE_SOUNDS_DIR.exists():
        for f in LEGACY_SOUNDSTAGE_SOUNDS_DIR.iterdir():
            if not f.is_file():
                continue
            dst = SOUNDFORGE_SOUNDS_DIR / f.name
            if not dst.exists():
                shutil.copy2(f, dst)
                copied_sounds += 1
    cfg = normalize_config(load_active_config())
    save_active_config(cfg)
    return {
        "ok": True,
        "migrated_schemes": migrated_schemes,
        "copied_legacy_sounds": copied_sounds,
        "status": migration_status(),
    }


def finalize_soundstage_removal(collision_policy: str = "rename") -> dict[str, Any]:
    ensure_layout()
    migration = migrate_legacy_to_soundforge(collision_policy=collision_policy)

    # Force canonical save to SoundForge path.
    cfg = normalize_config(load_active_config())
    save_active_config(cfg)

    archive_root = CORE_DIR / "soundstage_legacy_archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    archived: list[str] = []

    def _archive_path(path: Path) -> None:
        if not path.exists():
            return
        target = archive_root / path.name
        if target.exists():
            stamp = str(int(time.time_ns()))
            target = archive_root / f"{path.name}_{stamp}"
        shutil.move(str(path), str(target))
        archived.append(str(target))

    # Archive legacy config and directories (but keep operation reversible).
    _archive_path(LEGACY_SOUNDSTAGE_CONFIG_PATH)
    _archive_path(LEGACY_SOUNDSTAGE_SCHEMES_DIR)

    status = migration_status()
    if not status.get("safe_to_remove_soundstage", False):
        return {
            "ok": False,
            "message": "Finalization incomplete: legacy traces still detected.",
            "migration": migration,
            "archived_paths": archived,
            "status": status,
        }
    return {
        "ok": True,
        "message": "SoundStage legacy finalized and archived safely.",
        "migration": migration,
        "archived_paths": archived,
        "status": status,
    }
