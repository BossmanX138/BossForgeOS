from __future__ import annotations

from pathlib import Path
from typing import Any, BinaryIO

from modules.soundforge import service


SOUNDFORGE_CONFIG_PATH = service.SOUNDFORGE_CONFIG_PATH
LEGACY_SOUNDSTAGE_CONFIG_PATH = service.LEGACY_SOUNDSTAGE_CONFIG_PATH
SOUNDFORGE_SCHEMES_DIR = service.SOUNDFORGE_SCHEMES_DIR
LEGACY_SOUNDSTAGE_SCHEMES_DIR = service.LEGACY_SOUNDSTAGE_SCHEMES_DIR
SOUNDFORGE_SOUNDS_DIR = service.SOUNDFORGE_SOUNDS_DIR


def ensure_layout() -> None:
    service.ensure_layout()


def load_active_config() -> dict[str, Any]:
    return service.load_active_config()


def save_active_config(config: dict[str, Any]) -> None:
    service.save_active_config(config)


def export_bundle(destination: Path) -> Path:
    return service.export_bundle(destination)


def import_bundle(bundle_stream: BinaryIO, scheme_name: str, collision_policy: str = "rename") -> dict[str, Any]:
    return service.import_bundle(bundle_stream, scheme_name=scheme_name, collision_policy=collision_policy)


def list_schemes() -> list[str]:
    return service.list_schemes()


def activate_scheme(scheme_name: str) -> dict[str, Any]:
    return service.activate_scheme(scheme_name)


def validate_bundle(bundle_stream: BinaryIO) -> dict[str, Any]:
    return service.validate_bundle(bundle_stream)


def diagnose_config() -> dict[str, Any]:
    return service.diagnose_config()


def migration_status() -> dict[str, Any]:
    return service.migration_status()


def migrate_legacy_to_soundforge(collision_policy: str = "rename") -> dict[str, Any]:
    return service.migrate_legacy_to_soundforge(collision_policy=collision_policy)


def finalize_soundstage_removal(collision_policy: str = "rename") -> dict[str, Any]:
    return service.finalize_soundstage_removal(collision_policy=collision_policy)
