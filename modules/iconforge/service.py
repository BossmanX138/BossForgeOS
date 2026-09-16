from __future__ import annotations

from pathlib import Path
from typing import Any


def get_forge(root: str | Path | None = None) -> Any:
    from core.icons.icon_forge import IconForge

    return IconForge(root)


def create_icon_from_image(root: str | Path | None, image_path: str, output_ico: str, sizes: list[int] | None = None) -> dict[str, Any]:
    return get_forge(root).create_icon_from_image(image_path=image_path, output_ico=output_ico, sizes=sizes)


def create_icon_from_text(
    root: str | Path | None,
    text: str,
    output_ico: str,
    background: str = "#1d3557",
    foreground: str = "#f1faee",
    size: int = 256,
) -> dict[str, Any]:
    return get_forge(root).create_icon_from_text(
        text=text,
        output_ico=output_ico,
        background=background,
        foreground=foreground,
        size=size,
    )

