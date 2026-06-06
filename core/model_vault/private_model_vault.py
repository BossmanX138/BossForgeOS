from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MODEL_VAULT_SCHEMA_VERSION = "1.0"
_WEIGHT_INDEX_NAMES = {
    "model.safetensors.index.json",
    "pytorch_model.bin.index.json",
}


def _resolve_inside(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=True)
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f"model source path escapes root: {candidate}")
    return resolved


def _category(relative_path: str) -> str:
    name = Path(relative_path).name.lower()
    if name.startswith("adapter_"):
        return "adapter"
    if (
        name.endswith((".safetensors", ".bin", ".gguf"))
        or name in _WEIGHT_INDEX_NAMES
    ):
        return "weights"
    if name.startswith(("tokenizer", "vocab", "merges", "special_tokens")):
        return "tokenizer"
    if name == "config.json":
        return "model_config"
    if name == "generation_config.json":
        return "generation_config"
    if name in {"requirements.txt", "runtime_requirements.json"}:
        return "runtime_requirements"
    return "supporting"


def _validate_declared_shards(root: Path, files: list[dict[str, Any]]) -> None:
    for item in files:
        relative_path = str(item["relative_path"])
        if Path(relative_path).name.lower() not in _WEIGHT_INDEX_NAMES:
            continue
        index_path = Path(str(item["source_path"]))
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid model weight index: {relative_path}") from exc
        weight_map = payload.get("weight_map")
        if not isinstance(weight_map, dict) or not weight_map:
            raise ValueError(f"model weight index has no weight_map: {relative_path}")
        for declared in sorted({str(value).strip() for value in weight_map.values()}):
            if not declared:
                raise ValueError(f"model weight index has an empty declared shard: {relative_path}")
            candidate = root / declared
            try:
                resolved = _resolve_inside(root, candidate)
            except (FileNotFoundError, OSError, RuntimeError) as exc:
                raise ValueError(f"declared shard is missing: {declared}") from exc
            if not resolved.is_file():
                raise ValueError(f"declared shard is missing: {declared}")


def inspect_model_source(source_root: str | Path) -> dict[str, object]:
    try:
        root = Path(source_root).resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        raise ValueError(f"model source does not exist: {source_root}") from exc
    if not root.is_dir():
        raise ValueError("model source must be a directory")

    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if path.is_symlink():
            raise ValueError(f"model source links are not allowed: {path}")
        if not path.is_file():
            continue
        resolved = _resolve_inside(root, path)
        relative = resolved.relative_to(root).as_posix()
        files.append(
            {
                "source_path": str(resolved),
                "relative_path": relative,
                "size": resolved.stat().st_size,
                "category": _category(relative),
            }
        )

    present = {str(item["category"]) for item in files}
    for required, message in (
        ("weights", "model weights are required"),
        ("tokenizer", "tokenizer assets are required"),
        ("model_config", "model configuration is required"),
    ):
        if required not in present:
            raise ValueError(message)

    _validate_declared_shards(root, files)
    return {
        "source_root": str(root),
        "files": files,
        "present_categories": sorted(present),
        "required_categories": ["model_config", "tokenizer", "weights"],
        "total_size": sum(int(item["size"]) for item in files),
    }
