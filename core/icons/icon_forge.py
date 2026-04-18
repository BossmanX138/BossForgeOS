from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


class IconForge:
    """Create .ico assets and apply Windows icon overrides with backup metadata."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.state_dir = self.root / "bus" / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.backup_path = self.state_dir / "iconforge_backups.json"

    @staticmethod
    def _is_windows() -> bool:
        return os.name == "nt"

    @staticmethod
    def _require_windows() -> None:
        if not IconForge._is_windows():
            raise RuntimeError("IconForge Windows operations are only supported on Windows.")

    @staticmethod
    def _normalize_extension(ext: str) -> str:
        raw = str(ext or "").strip().lower()
        if not raw:
            raise ValueError("extension is required")
        if not raw.startswith("."):
            raw = "." + raw
        return raw

    def _load_backups(self) -> dict[str, Any]:
        if not self.backup_path.exists():
            return {"items": {}}
        try:
            payload = json.loads(self.backup_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"items": {}}
        if not isinstance(payload, dict):
            return {"items": {}}
        items = payload.get("items")
        if not isinstance(items, dict):
            payload["items"] = {}
        return payload

    def _save_backups(self, payload: dict[str, Any]) -> None:
        self.backup_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _put_backup(self, key: str, value: dict[str, Any]) -> None:
        payload = self._load_backups()
        items = payload.setdefault("items", {})
        if not isinstance(items, dict):
            payload["items"] = {}
            items = payload["items"]
        value = dict(value)
        value["updated_at"] = int(time.time())
        items[key] = value
        self._save_backups(payload)

    @staticmethod
    def _safe_name(value: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in str(value or "").strip())
        return cleaned[:120] or "icon"

    def _resolve_icon_ref(self, icon_ref: str, bundle_root: Path) -> Path:
        candidate = Path(str(icon_ref or "")).expanduser()
        if candidate.is_absolute():
            return candidate.resolve()
        return (bundle_root / candidate).resolve()

    @staticmethod
    def _normalize_drive_letter(drive: str) -> str:
        raw = str(drive or "").strip().upper()
        if not raw:
            raise ValueError("drive is required (example: C or C:)")
        if raw.endswith(":"):
            raw = raw[:-1]
        if len(raw) != 1 or not raw.isalpha():
            raise ValueError("drive must be a single letter (example: C or D)")
        return raw

    def list_backups(self) -> dict[str, Any]:
        payload = self._load_backups()
        return payload.get("items", {}) if isinstance(payload.get("items"), dict) else {}

    def export_icon_set(self, output_dir: str) -> dict[str, Any]:
        target = Path(output_dir).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        icons_dir = target / "icons"
        icons_dir.mkdir(parents=True, exist_ok=True)

        items = self.list_backups()
        manifest_entries: list[dict[str, Any]] = []
        copied = 0
        missing = 0

        for backup_key in sorted(items.keys()):
            item = items.get(backup_key)
            if not isinstance(item, dict):
                continue

            icon_ref = ""
            copied_icon_name = ""
            if isinstance(item.get("icon"), str):
                icon_ref = str(item.get("icon", "")).strip()
            source_icon = Path(icon_ref).expanduser().resolve() if icon_ref else None

            if source_icon and source_icon.exists() and source_icon.is_file():
                copied_icon_name = f"{self._safe_name(backup_key)}{source_icon.suffix.lower() or '.ico'}"
                shutil.copy2(source_icon, icons_dir / copied_icon_name)
                copied += 1
            elif icon_ref:
                missing += 1

            manifest_entries.append(
                {
                    "backup_key": backup_key,
                    "target_type": str(item.get("target_type", "")).strip(),
                    "target": str(item.get("target", "")).strip(),
                    "icon": f"icons/{copied_icon_name}" if copied_icon_name else icon_ref,
                    "meta": {
                        "progid": str(item.get("progid", "")).strip(),
                        "updated_at": int(item.get("updated_at", 0)) if isinstance(item.get("updated_at"), int) else 0,
                    },
                }
            )

        manifest = {
            "schema_version": "iconforge.set.v1",
            "exported_at": int(time.time()),
            "root": str(target),
            "count": len(manifest_entries),
            "entries": manifest_entries,
        }

        manifest_path = target / "icon_set_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {
            "ok": True,
            "message": "icon set exported",
            "output_dir": str(target),
            "manifest": str(manifest_path),
            "entries": len(manifest_entries),
            "icons_copied": copied,
            "icons_missing": missing,
        }

    def import_icon_set(self, source: str, apply_changes: bool = True, refresh_cache: bool = False) -> dict[str, Any]:
        bundle = Path(source).expanduser().resolve()
        manifest_path = bundle
        if bundle.is_dir():
            manifest_path = bundle / "icon_set_manifest.json"
        if not manifest_path.exists():
            return {"ok": False, "message": f"icon set manifest not found: {manifest_path}"}

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"ok": False, "message": f"invalid icon set manifest: {manifest_path}"}
        if not isinstance(manifest, dict):
            return {"ok": False, "message": "icon set manifest root must be an object"}

        entries = manifest.get("entries")
        if not isinstance(entries, list):
            return {"ok": False, "message": "icon set manifest entries must be an array"}

        bundle_root = manifest_path.parent
        planned: list[dict[str, Any]] = []
        applied: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            target_type = str(entry.get("target_type", "")).strip().lower()
            target = str(entry.get("target", "")).strip()
            icon_ref = str(entry.get("icon", "")).strip()
            backup_key = str(entry.get("backup_key", "")).strip()
            if not target_type or not target or not icon_ref:
                errors.append({"backup_key": backup_key, "message": "entry missing target_type/target/icon"})
                continue

            icon_path = self._resolve_icon_ref(icon_ref, bundle_root)
            planned_item = {
                "backup_key": backup_key,
                "target_type": target_type,
                "target": target,
                "icon": str(icon_path),
            }
            planned.append(planned_item)

            if not apply_changes:
                continue

            if not icon_path.exists():
                errors.append({"backup_key": backup_key, "message": f"icon not found: {icon_path}"})
                continue

            if target_type == "folder":
                result = self.set_folder_icon(target, str(icon_path))
            elif target_type == "shortcut":
                result = self.set_shortcut_icon(target, str(icon_path))
            elif target_type == "file_extension":
                result = self.set_file_extension_icon(target, str(icon_path))
            elif target_type == "application":
                result = self.set_application_icon(target, str(icon_path))
            elif target_type == "drive":
                result = self.set_drive_icon(target, str(icon_path))
            else:
                errors.append({"backup_key": backup_key, "message": f"unsupported target_type: {target_type}"})
                continue

            if result.get("ok"):
                applied.append({"backup_key": backup_key, "target_type": target_type, "target": target})
            else:
                errors.append({"backup_key": backup_key, "message": str(result.get("message", "unknown error"))})

        refreshed = None
        if apply_changes and refresh_cache and not errors:
            refreshed = self.refresh_icon_cache()

        return {
            "ok": len(errors) == 0,
            "message": "icon set imported" if apply_changes else "icon set parsed (dry run)",
            "manifest": str(manifest_path),
            "planned": planned,
            "applied": applied,
            "errors": errors,
            "refresh": refreshed,
        }

    def create_icon_from_image(self, image_path: str, output_ico: str, sizes: list[int] | None = None) -> dict[str, Any]:
        source = Path(image_path).expanduser().resolve()
        target = Path(output_ico).expanduser().resolve()
        if not source.exists():
            return {"ok": False, "message": f"source image not found: {source}"}

        try:
            from PIL import Image
        except Exception:
            return {
                "ok": False,
                "message": "Pillow is required for icon creation. Install with: pip install pillow",
            }

        icon_sizes = sorted({int(s) for s in (sizes or [16, 24, 32, 48, 64, 128, 256]) if int(s) > 0})
        if not icon_sizes:
            icon_sizes = [16, 24, 32, 48, 64, 128, 256]

        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as img:
            rgba = img.convert("RGBA")
            rgba.save(target, format="ICO", sizes=[(s, s) for s in icon_sizes])

        return {
            "ok": True,
            "message": "icon created",
            "source": str(source),
            "icon": str(target),
            "sizes": icon_sizes,
        }

    def create_icon_from_text(
        self,
        text: str,
        output_ico: str,
        background: str = "#1d3557",
        foreground: str = "#f1faee",
        size: int = 256,
    ) -> dict[str, Any]:
        label = (str(text or "").strip() or "BF")[:3]
        icon_size = max(32, int(size))

        try:
            from PIL import Image, ImageDraw, ImageFont
        except Exception:
            return {
                "ok": False,
                "message": "Pillow is required for icon creation. Install with: pip install pillow",
            }

        target = Path(output_ico).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        img = Image.new("RGBA", (icon_size, icon_size), background)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", int(icon_size * 0.42))
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), label, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (icon_size - w) // 2
        y = (icon_size - h) // 2
        draw.text((x, y), label, fill=foreground, font=font)

        sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(target, format="ICO", sizes=sizes)

        return {
            "ok": True,
            "message": "icon created",
            "label": label,
            "icon": str(target),
            "background": background,
            "foreground": foreground,
        }

    def set_folder_icon(self, folder_path: str, icon_path: str) -> dict[str, Any]:
        self._require_windows()
        folder = Path(folder_path).expanduser().resolve()
        icon = Path(icon_path).expanduser().resolve()
        if not folder.exists() or not folder.is_dir():
            return {"ok": False, "message": f"folder not found: {folder}"}
        if not icon.exists():
            return {"ok": False, "message": f"icon not found: {icon}"}

        desktop_ini = folder / "desktop.ini"
        previous = desktop_ini.read_text(encoding="utf-8", errors="ignore") if desktop_ini.exists() else ""
        desktop_ini.write_text(
            "[.ShellClassInfo]\n"
            f"IconResource={icon},0\n"
            "[ViewState]\n"
            "Mode=\n"
            "Vid=\n"
            "FolderType=Generic\n",
            encoding="utf-8",
        )

        subprocess.run(["attrib", "+s", str(folder)], check=False, capture_output=True)
        subprocess.run(["attrib", "+h", "+s", str(desktop_ini)], check=False, capture_output=True)

        key = f"folder::{str(folder).lower()}"
        self._put_backup(
            key,
            {
                "target_type": "folder",
                "target": str(folder),
                "icon": str(icon),
                "previous_desktop_ini": previous,
            },
        )
        return {"ok": True, "message": "folder icon updated", "target": str(folder), "icon": str(icon), "backup_key": key}

    def set_shortcut_icon(self, shortcut_path: str, icon_path: str) -> dict[str, Any]:
        self._require_windows()
        shortcut = Path(shortcut_path).expanduser().resolve()
        icon = Path(icon_path).expanduser().resolve()
        if not shortcut.exists() or shortcut.suffix.lower() != ".lnk":
            return {"ok": False, "message": f"shortcut (.lnk) not found: {shortcut}"}
        if not icon.exists():
            return {"ok": False, "message": f"icon not found: {icon}"}

        ps = (
            "$ws=New-Object -ComObject WScript.Shell;"
            f"$s=$ws.CreateShortcut('{str(shortcut).replace("'", "''")}');"
            "$prev=$s.IconLocation;"
            f"$s.IconLocation='{str(icon).replace("'", "''")},0';"
            "$s.Save();"
            "Write-Output $prev"
        )
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            return {"ok": False, "message": proc.stderr.strip() or "failed to set shortcut icon"}
        previous = proc.stdout.strip()

        key = f"shortcut::{str(shortcut).lower()}"
        self._put_backup(
            key,
            {
                "target_type": "shortcut",
                "target": str(shortcut),
                "icon": str(icon),
                "previous_icon_location": previous,
            },
        )
        return {"ok": True, "message": "shortcut icon updated", "target": str(shortcut), "icon": str(icon), "backup_key": key}

    def set_file_extension_icon(self, extension: str, icon_path: str) -> dict[str, Any]:
        self._require_windows()
        ext = self._normalize_extension(extension)
        icon = Path(icon_path).expanduser().resolve()
        if not icon.exists():
            return {"ok": False, "message": f"icon not found: {icon}"}

        classes = r"HKCU\Software\Classes"
        ext_key = f"{classes}\\{ext}"
        progid = f"BossForgeOS{ext.upper().replace('.', '_')}_AutoFile"

        read_proc = subprocess.run(
            ["reg", "query", ext_key, "/ve"],
            check=False,
            capture_output=True,
            text=True,
        )
        previous_assoc = ""
        if read_proc.returncode == 0:
            previous_assoc = read_proc.stdout

        subprocess.run(["reg", "add", ext_key, "/ve", "/t", "REG_SZ", "/d", progid, "/f"], check=False, capture_output=True)

        default_icon_key = f"{classes}\\{progid}\\DefaultIcon"
        subprocess.run(
            ["reg", "add", default_icon_key, "/ve", "/t", "REG_SZ", "/d", f"{icon},0", "/f"],
            check=False,
            capture_output=True,
        )

        key = f"file_extension::{ext}"
        self._put_backup(
            key,
            {
                "target_type": "file_extension",
                "target": ext,
                "icon": str(icon),
                "previous_association_query": previous_assoc,
                "progid": progid,
            },
        )
        return {"ok": True, "message": "file type icon updated", "target": ext, "icon": str(icon), "backup_key": key, "progid": progid}

    def set_application_icon(self, exe_name: str, icon_path: str) -> dict[str, Any]:
        self._require_windows()
        app = str(exe_name or "").strip()
        if not app:
            return {"ok": False, "message": "exe_name is required (example: notepad.exe)"}
        if not app.lower().endswith(".exe"):
            app = f"{app}.exe"

        icon = Path(icon_path).expanduser().resolve()
        if not icon.exists():
            return {"ok": False, "message": f"icon not found: {icon}"}

        key_path = f"HKCU\\Software\\Classes\\Applications\\{app}\\DefaultIcon"

        read_proc = subprocess.run(["reg", "query", key_path, "/ve"], check=False, capture_output=True, text=True)
        previous_icon = read_proc.stdout if read_proc.returncode == 0 else ""

        write_proc = subprocess.run(
            ["reg", "add", key_path, "/ve", "/t", "REG_SZ", "/d", f"{icon},0", "/f"],
            check=False,
            capture_output=True,
            text=True,
        )
        if write_proc.returncode != 0:
            return {"ok": False, "message": write_proc.stderr.strip() or "failed to set application icon"}

        backup_key = f"application::{app.lower()}"
        self._put_backup(
            backup_key,
            {
                "target_type": "application",
                "target": app,
                "icon": str(icon),
                "previous_default_icon_query": previous_icon,
            },
        )
        return {
            "ok": True,
            "message": "application icon override updated",
            "target": app,
            "icon": str(icon),
            "backup_key": backup_key,
            "note": "This sets a shell-level icon override and does not patch the EXE binary resource.",
        }

    def set_drive_icon(self, drive: str, icon_path: str) -> dict[str, Any]:
        self._require_windows()
        try:
            letter = self._normalize_drive_letter(drive)
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}

        icon = Path(icon_path).expanduser().resolve()
        if not icon.exists():
            return {"ok": False, "message": f"icon not found: {icon}"}

        key_path = f"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\DriveIcons\\{letter}\\DefaultIcon"
        read_proc = subprocess.run(["reg", "query", key_path, "/ve"], check=False, capture_output=True, text=True)
        previous_icon = read_proc.stdout if read_proc.returncode == 0 else ""

        write_proc = subprocess.run(
            ["reg", "add", key_path, "/ve", "/t", "REG_SZ", "/d", f"{icon},0", "/f"],
            check=False,
            capture_output=True,
            text=True,
        )
        if write_proc.returncode != 0:
            return {"ok": False, "message": write_proc.stderr.strip() or "failed to set drive icon"}

        backup_key = f"drive::{letter}"
        self._put_backup(
            backup_key,
            {
                "target_type": "drive",
                "target": letter,
                "icon": str(icon),
                "previous_default_icon_query": previous_icon,
            },
        )
        return {
            "ok": True,
            "message": "drive icon override updated",
            "target": f"{letter}:",
            "icon": str(icon),
            "backup_key": backup_key,
            "note": "This sets a shell-level icon override for the drive letter.",
        }

    def refresh_icon_cache(self) -> dict[str, Any]:
        self._require_windows()
        cmds = [
            ["ie4uinit.exe", "-ClearIconCache"],
            ["ie4uinit.exe", "-show"],
        ]
        results: list[dict[str, Any]] = []
        for cmd in cmds:
            proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
            results.append(
                {
                    "command": " ".join(cmd),
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip(),
                }
            )
        return {"ok": True, "message": "icon cache refresh attempted", "results": results}

    def restore(self, backup_key: str) -> dict[str, Any]:
        self._require_windows()
        key = str(backup_key or "").strip()
        if not key:
            return {"ok": False, "message": "backup_key is required"}

        payload = self._load_backups()
        items = payload.get("items") if isinstance(payload.get("items"), dict) else {}
        item = items.get(key) if isinstance(items, dict) else None
        if not isinstance(item, dict):
            return {"ok": False, "message": f"backup key not found: {key}"}

        kind = str(item.get("target_type", "")).strip().lower()

        if kind == "folder":
            folder = Path(str(item.get("target", ""))).expanduser().resolve()
            desktop_ini = folder / "desktop.ini"
            previous = str(item.get("previous_desktop_ini", ""))
            if previous:
                desktop_ini.write_text(previous, encoding="utf-8")
            elif desktop_ini.exists():
                desktop_ini.unlink()
            return {"ok": True, "message": "folder icon restored", "target": str(folder)}

        if kind == "shortcut":
            shortcut = Path(str(item.get("target", ""))).expanduser().resolve()
            previous = str(item.get("previous_icon_location", ""))
            ps = (
                "$ws=New-Object -ComObject WScript.Shell;"
                f"$s=$ws.CreateShortcut('{str(shortcut).replace("'", "''")}');"
                f"$s.IconLocation='{previous.replace("'", "''")}';"
                "$s.Save();"
            )
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False, capture_output=True, text=True)
            if proc.returncode != 0:
                return {"ok": False, "message": proc.stderr.strip() or "failed to restore shortcut icon"}
            return {"ok": True, "message": "shortcut icon restored", "target": str(shortcut)}

        if kind == "file_extension":
            ext = self._normalize_extension(str(item.get("target", "")))
            progid = str(item.get("progid", "")).strip()
            classes = r"HKCU\Software\Classes"
            ext_key = f"{classes}\\{ext}"
            if progid:
                subprocess.run(["reg", "delete", f"{classes}\\{progid}", "/f"], check=False, capture_output=True)
            subprocess.run(["reg", "delete", ext_key, "/ve", "/f"], check=False, capture_output=True)
            return {"ok": True, "message": "file extension icon override removed", "target": ext}

        if kind == "application":
            app = str(item.get("target", "")).strip()
            key_path = f"HKCU\\Software\\Classes\\Applications\\{app}\\DefaultIcon"
            subprocess.run(["reg", "delete", key_path, "/ve", "/f"], check=False, capture_output=True)
            return {"ok": True, "message": "application icon override removed", "target": app}

        if kind == "drive":
            letter = str(item.get("target", "")).strip().upper()
            if letter.endswith(":"):
                letter = letter[:-1]
            key_path = f"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\DriveIcons\\{letter}\\DefaultIcon"
            subprocess.run(["reg", "delete", key_path, "/ve", "/f"], check=False, capture_output=True)
            return {"ok": True, "message": "drive icon override removed", "target": f"{letter}:"}

        return {"ok": False, "message": f"unsupported backup type: {kind}"}

    def get_production_sheet_path(self) -> Path:
        return self.root / "assets" / "icons" / "iconforge_production_sheet.json"

    def load_production_sheet(self, sheet_path: str | None = None) -> dict[str, Any]:
        candidate = Path(sheet_path).expanduser().resolve() if sheet_path else self.get_production_sheet_path().resolve()
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError(f"production sheet not found: {candidate}")
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("production sheet root must be an object")
        return payload

    def generate_placeholder_pack(
        self,
        output_dir: str,
        sheet_path: str | None = None,
        background: str = "#0A0A0C",
        foreground: str = "#D4A857",
    ) -> dict[str, Any]:
        """Generate baseline ICO placeholders for all icon ids in the production sheet.

        This does not replace vector artwork. It provides immediate usable icons for
        shell wiring while final art is being produced.
        """
        sheet = self.load_production_sheet(sheet_path)
        categories = sheet.get("categories") if isinstance(sheet.get("categories"), dict) else {}
        if not categories:
            return {"ok": False, "message": "production sheet has no categories"}

        out_root = Path(output_dir).expanduser().resolve()
        out_root.mkdir(parents=True, exist_ok=True)

        generated: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        for category, icon_ids in categories.items():
            if not isinstance(icon_ids, list):
                continue
            category_dir = out_root / str(category)
            category_dir.mkdir(parents=True, exist_ok=True)
            for icon_id in icon_ids:
                icon_name = str(icon_id or "").strip().lower()
                if not icon_name:
                    continue
                label = "".join(ch for ch in icon_name if ch.isalnum()).upper()[:3] or "BF"
                target = category_dir / f"{icon_name}.ico"
                result = self.create_icon_from_text(
                    text=label,
                    output_ico=str(target),
                    background=background,
                    foreground=foreground,
                )
                if result.get("ok"):
                    generated.append(
                        {
                            "category": str(category),
                            "icon_id": icon_name,
                            "icon": str(target),
                            "label": label,
                        }
                    )
                else:
                    failed.append(
                        {
                            "category": str(category),
                            "icon_id": icon_name,
                            "message": str(result.get("message", "unknown error")),
                        }
                    )

        manifest = {
            "schema_version": "iconforge.placeholder-pack.v1",
            "generated_at": int(time.time()),
            "source_production_sheet": str(self.get_production_sheet_path() if sheet_path is None else Path(sheet_path).expanduser().resolve()),
            "output_dir": str(out_root),
            "generated": generated,
            "failed": failed,
        }
        manifest_path = out_root / "placeholder_icon_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return {
            "ok": len(failed) == 0,
            "message": "placeholder pack generated" if not failed else "placeholder pack generated with errors",
            "output_dir": str(out_root),
            "manifest": str(manifest_path),
            "generated_count": len(generated),
            "failed_count": len(failed),
        }
