from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = (
    "schema_version",
    "module_id",
    "display_name",
    "version",
    "standalone_entrypoint",
    "orchestrator_connector",
    "capabilities",
)


class ModuleValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ModuleManifest:
    path: Path
    payload: dict[str, Any]


class ModuleRegistry:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.modules_root = self.repo_root / "modules"

    def _manifest_paths(self) -> list[Path]:
        if not self.modules_root.exists():
            return []
        return sorted(self.modules_root.glob("*/manifest.json"))

    def _validate_payload(self, payload: dict[str, Any], source: Path) -> None:
        missing = [name for name in REQUIRED_FIELDS if name not in payload]
        if missing:
            raise ModuleValidationError(f"{source}: missing required fields: {', '.join(missing)}")

        if payload.get("schema_version") != "1.0":
            raise ModuleValidationError(f"{source}: unsupported schema_version {payload.get('schema_version')!r}")

        for key in ("module_id", "display_name", "version", "standalone_entrypoint"):
            if not str(payload.get(key, "")).strip():
                raise ModuleValidationError(f"{source}: field {key!r} must be non-empty")

        connector = payload.get("orchestrator_connector")
        if not isinstance(connector, dict):
            raise ModuleValidationError(f"{source}: 'orchestrator_connector' must be an object")
        connector_cmd = connector.get("command")
        if not isinstance(connector_cmd, list) or not connector_cmd or not all(
            str(part).strip() for part in connector_cmd
        ):
            raise ModuleValidationError(f"{source}: orchestrator_connector.command must be a non-empty string array")

        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, list) or not capabilities:
            raise ModuleValidationError(f"{source}: capabilities must be a non-empty array")

    def load(self) -> list[ModuleManifest]:
        manifests: list[ModuleManifest] = []
        for path in self._manifest_paths():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as ex:
                raise ModuleValidationError(f"{path}: could not parse manifest: {ex}") from ex

            if not isinstance(payload, dict):
                raise ModuleValidationError(f"{path}: manifest root must be a JSON object")

            self._validate_payload(payload, path)
            manifests.append(ModuleManifest(path=path, payload=payload))
        return manifests

    def validate(self) -> dict[str, Any]:
        manifests = self.load()
        return {
            "ok": True,
            "modules_found": len(manifests),
            "manifests": [str(item.path) for item in manifests],
        }

    def summarize(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in self.load():
            payload = item.payload
            connector = payload.get("orchestrator_connector", {})
            out.append(
                {
                    "module_id": payload.get("module_id"),
                    "display_name": payload.get("display_name"),
                    "version": payload.get("version"),
                    "standalone_entrypoint": payload.get("standalone_entrypoint"),
                    "connector_command": connector.get("command", []),
                    "capabilities": payload.get("capabilities", []),
                    "manifest": str(item.path),
                }
            )
        return out

    def get(self, module_id: str) -> dict[str, Any] | None:
        key = str(module_id).strip().lower()
        if not key:
            return None
        for item in self.summarize():
            if str(item.get("module_id", "")).strip().lower() == key:
                return item
        return None

