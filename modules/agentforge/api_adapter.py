from __future__ import annotations

import base64
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from werkzeug.utils import secure_filename

from modules.agentforge import service as agentforge_service
from modules.iconforge import service as iconforge_service


def list_agent_profiles() -> dict[str, Any]:
    return agentforge_service.list_agent_profiles()


def create_agent_profile(payload: dict[str, Any]) -> dict[str, Any]:
    return agentforge_service.create_agent_profile(payload)


def _safe_icon_stem(value: str) -> str:
    cleaned = secure_filename(str(value or "").strip())
    if not cleaned:
        return "agent_icon"
    stem = Path(cleaned).stem.replace("-", "_")
    stem = "".join(ch for ch in stem if ch.isalnum() or ch == "_").strip("_")
    return (stem[:64] or "agent_icon").lower()


def _to_project_relpath(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def upload_icon(uploaded: Any, icon_name: str, project_root: Path) -> tuple[dict[str, Any], int]:
    original_name = secure_filename(getattr(uploaded, "filename", "") or "")
    if not original_name:
        return {"ok": False, "message": "icon file name is required"}, 400

    source_ext = Path(original_name).suffix.lower()
    if source_ext not in {".png"}:
        return {"ok": False, "message": "unsupported file type; use .png"}, 400

    stem = _safe_icon_stem(icon_name)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    icon_dir = project_root / "assets" / "icons" / "agents"
    icon_dir.mkdir(parents=True, exist_ok=True)

    source_path = icon_dir / f"{stem}_{suffix}{source_ext}"
    final_path = icon_dir / f"{stem}_{suffix}.ico"
    try:
        uploaded.save(source_path)
        forge = iconforge_service.get_forge(project_root)
        result = forge.create_icon_from_image(str(source_path), str(final_path))
        if not result.get("ok"):
            return {"ok": False, "message": str(result.get("message", "icon conversion failed"))}, 400
        return {"ok": True, "icon": _to_project_relpath(final_path, project_root), "message": "icon uploaded and converted"}, 200
    except Exception as exc:
        return {"ok": False, "message": f"icon upload failed: {exc}"}, 500
    finally:
        if source_path.exists():
            source_path.unlink(missing_ok=True)


def create_icon(payload: dict[str, Any], project_root: Path) -> tuple[dict[str, Any], int]:
    icon_name = str(payload.get("icon_name", "agent_icon")).strip()
    label = str(payload.get("label", "AG")).strip() or "AG"
    background = str(payload.get("background", "#1d3557")).strip() or "#1d3557"
    foreground = str(payload.get("foreground", "#f1faee")).strip() or "#f1faee"
    stem = _safe_icon_stem(icon_name)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    icon_dir = project_root / "assets" / "icons" / "agents"
    icon_dir.mkdir(parents=True, exist_ok=True)
    final_path = icon_dir / f"{stem}_{suffix}.ico"
    try:
        forge = iconforge_service.get_forge(project_root)
        result = forge.create_icon_from_text(text=label, output_ico=str(final_path), background=background, foreground=foreground)
        if not result.get("ok"):
            return {"ok": False, "message": str(result.get("message", "icon creation failed"))}, 400
        return {"ok": True, "icon": _to_project_relpath(final_path, project_root), "message": "icon created"}, 200
    except Exception as exc:
        return {"ok": False, "message": f"icon creation failed: {exc}"}, 500


def create_icon_from_canvas(payload: dict[str, Any], project_root: Path) -> tuple[dict[str, Any], int]:
    icon_name = str(payload.get("icon_name", "agent_icon")).strip()
    image_data = str(payload.get("image_data", "")).strip()
    if not image_data.startswith("data:image/png"):
        return {"ok": False, "message": "image_data must be a PNG data URL"}, 400
    comma_idx = image_data.find(",")
    if comma_idx <= 0:
        return {"ok": False, "message": "invalid image_data format"}, 400
    encoded = image_data[comma_idx + 1 :]
    stem = _safe_icon_stem(icon_name)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    icon_dir = project_root / "assets" / "icons" / "agents"
    icon_dir.mkdir(parents=True, exist_ok=True)
    temp_png = icon_dir / f"{stem}_{suffix}_src.png"
    final_path = icon_dir / f"{stem}_{suffix}.ico"
    try:
        raw = base64.b64decode(encoded)
    except Exception:
        return {"ok": False, "message": "image_data is not valid base64"}, 400
    try:
        temp_png.write_bytes(raw)
        forge = iconforge_service.get_forge(project_root)
        result = forge.create_icon_from_image(str(temp_png), str(final_path))
        if not result.get("ok"):
            return {"ok": False, "message": str(result.get("message", "icon creation failed"))}, 400
        return {"ok": True, "icon": _to_project_relpath(final_path, project_root), "message": "icon created"}, 200
    except Exception as exc:
        return {"ok": False, "message": f"icon creation failed: {exc}"}, 500
    finally:
        if temp_png.exists():
            temp_png.unlink(missing_ok=True)


def create_animated_icon_from_canvas(payload: dict[str, Any], project_root: Path) -> tuple[dict[str, Any], int]:
    icon_name = str(payload.get("icon_name", "agent_icon")).strip()
    image_data = str(payload.get("image_data", "")).strip()
    preset = str(payload.get("preset", "pulse")).strip().lower()
    seconds = int(payload.get("seconds", 3))
    fps = int(payload.get("fps", 12))
    if not image_data.startswith("data:image/png"):
        return {"ok": False, "message": "image_data must be a PNG data URL"}, 400
    comma_idx = image_data.find(",")
    if comma_idx <= 0:
        return {"ok": False, "message": "invalid image_data format"}, 400
    encoded = image_data[comma_idx + 1 :]
    stem = _safe_icon_stem(icon_name)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    icon_dir = project_root / "assets" / "icons" / "agents"
    icon_dir.mkdir(parents=True, exist_ok=True)
    temp_png = icon_dir / f"{stem}_{suffix}_anim_src.png"
    final_ico = icon_dir / f"{stem}_{suffix}.ico"
    final_gif = icon_dir / f"{stem}_{suffix}.gif"
    try:
        raw = base64.b64decode(encoded)
    except Exception:
        return {"ok": False, "message": "image_data is not valid base64"}, 400
    try:
        from PIL import Image, ImageEnhance
    except Exception:
        return {"ok": False, "message": "Pillow is required for animated export. Install with: pip install pillow"}, 400

    seconds = max(1, min(12, seconds))
    fps = max(6, min(30, fps))
    total_frames = max(8, min(360, seconds * fps))
    duration_ms = int(1000 / fps)
    try:
        temp_png.write_bytes(raw)
        base = Image.open(temp_png).convert("RGBA")
        w, h = base.size
        frames = []
        for idx in range(total_frames):
            t = idx / max(1, total_frames - 1)
            if preset == "spin":
                frame = base.rotate(360.0 * t, resample=Image.BICUBIC, expand=False)
            elif preset == "shimmer":
                frame = base.copy()
                overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                band_center = int((w * 1.5) * t) - (w // 4)
                for x in range(w):
                    dist = abs(x - band_center)
                    if dist > w // 5:
                        continue
                    alpha = max(0, 140 - int((dist / (w // 5 + 1)) * 140))
                    for y in range(h):
                        overlay.putpixel((x, y), (255, 255, 255, alpha))
                frame = Image.alpha_composite(frame, overlay)
            else:
                pulse = 0.88 + 0.20 * (0.5 + 0.5 * math.sin(2.0 * math.pi * t))
                nw = max(8, int(w * pulse))
                nh = max(8, int(h * pulse))
                resized = base.resize((nw, nh), resample=Image.BICUBIC)
                frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                frame.paste(resized, ((w - nw) // 2, (h - nh) // 2), resized)
                frame = ImageEnhance.Brightness(frame).enhance(1.05)
            frames.append(frame)
        if not frames:
            return {"ok": False, "message": "failed to build animated frames"}, 400
        frames[0].save(
            final_gif,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            loop=0,
            duration=duration_ms,
            disposal=2,
            transparency=0,
        )
        forge = iconforge_service.get_forge(project_root)
        ico_result = forge.create_icon_from_image(str(temp_png), str(final_ico))
        if not ico_result.get("ok"):
            return {"ok": False, "message": str(ico_result.get("message", "ico fallback creation failed"))}, 400
        return {
            "ok": True,
            "animated": _to_project_relpath(final_gif, project_root),
            "icon": _to_project_relpath(final_ico, project_root),
            "preset": preset,
            "frames": total_frames,
            "fps": fps,
            "seconds": seconds,
            "message": "animated gif + ico fallback created",
        }, 200
    except Exception as exc:
        return {"ok": False, "message": f"animated export failed: {exc}"}, 500
    finally:
        if temp_png.exists():
            temp_png.unlink(missing_ok=True)
