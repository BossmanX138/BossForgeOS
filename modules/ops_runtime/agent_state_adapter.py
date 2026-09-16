from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def health_from_timestamp(ts: str | None, now: datetime | None = None) -> str:
    if not ts:
        return "offline"
    try:
        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return "offline"
    current = now or datetime.now(timezone.utc)
    delta = (current - then).total_seconds()
    if delta <= 60:
        return "online"
    if delta <= 300:
        return "stale"
    return "offline"


def model_agent_state_key(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in name.strip().lower())
    return f"model_agent_{safe}"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_agent_state(
    state_dir: Path,
    static_agents: dict[str, str],
    now: datetime | None = None,
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}

    dynamic_agents: dict[str, str] = {}
    dynamic_meta: dict[str, dict[str, str]] = {}
    profiles_path = state_dir / "model_agents.json"
    if profiles_path.exists():
        profiles = _load_json(profiles_path)
        if isinstance(profiles, dict):
            endpoints: dict[str, Any] = {}
            endpoints_path = state_dir / "model_endpoints.json"
            if endpoints_path.exists():
                raw_eps = _load_json(endpoints_path)
                if isinstance(raw_eps, dict):
                    endpoints = raw_eps

            for name, profile in profiles.items():
                key = str(name).strip().lower()
                if not key:
                    continue
                state_key = model_agent_state_key(key)
                dynamic_agents[state_key] = f"Model Agent: {key}"
                endpoint = ""
                provider = ""
                if isinstance(profile, dict):
                    endpoint = str(profile.get("endpoint", "")).strip()
                if endpoint and isinstance(endpoints, dict):
                    endpoint_cfg = endpoints.get(endpoint)
                    if isinstance(endpoint_cfg, dict):
                        provider = str(endpoint_cfg.get("provider", "")).strip()
                dynamic_meta[state_key] = {"endpoint": endpoint, "provider": provider}

    combined = dict(static_agents)
    combined.update(dynamic_agents)

    for key, display in combined.items():
        payload = {}
        state_file = state_dir / f"{key}.json"
        if state_file.exists():
            loaded = _load_json(state_file)
            if isinstance(loaded, dict):
                payload = loaded

        last_seen = payload.get("timestamp")
        meta = dynamic_meta.get(key, {})
        endpoint = str(payload.get("endpoint", "") or meta.get("endpoint", "")).strip()
        provider = str(meta.get("provider", "")).strip()
        result[key] = {
            "display_name": display,
            "health": health_from_timestamp(last_seen, now),
            "last_seen": last_seen or "never",
            "endpoint": endpoint,
            "provider": provider,
        }
    return result
