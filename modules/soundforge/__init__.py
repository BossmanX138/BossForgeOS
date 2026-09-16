"""SoundForge compatibility exports backed by modules.soundforge.service."""

from modules.soundforge.service import (
    LEGACY_SOUNDSTAGE_CONFIG_PATH,
    LEGACY_SOUNDSTAGE_SCHEMES_DIR,
    LEGACY_SOUNDSTAGE_SOUNDS_DIR,
    SOUNDFORGE_CONFIG_PATH,
    SOUNDFORGE_SCHEMES_DIR,
    SOUNDFORGE_SOUNDS_DIR,
    ensure_layout,
    list_schemes,
    load_active_config,
    resolve_sound_path,
    rewrite_config_paths,
    save_active_config,
    source_config_path,
)

__all__ = [
    "SOUNDFORGE_CONFIG_PATH",
    "LEGACY_SOUNDSTAGE_CONFIG_PATH",
    "SOUNDFORGE_SCHEMES_DIR",
    "LEGACY_SOUNDSTAGE_SCHEMES_DIR",
    "SOUNDFORGE_SOUNDS_DIR",
    "LEGACY_SOUNDSTAGE_SOUNDS_DIR",
    "ensure_layout",
    "source_config_path",
    "load_active_config",
    "save_active_config",
    "list_schemes",
    "rewrite_config_paths",
    "resolve_sound_path",
]
