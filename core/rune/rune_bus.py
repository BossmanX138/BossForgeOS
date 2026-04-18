import json
import os
import heapq
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuneBus:
    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root or Path.home() / "BossCrafts")
        self.bus = self.root / "bus"
        self.events = self.bus / "events"
        self.events_archive = self.bus / "events_archive"
        self.commands = self.bus / "commands"
        self.state = self.bus / "state"
        self.recent_events_cache = self.state / "_recent_events.jsonl"
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        self.events.mkdir(parents=True, exist_ok=True)
        self.events_archive.mkdir(parents=True, exist_ok=True)
        self.commands.mkdir(parents=True, exist_ok=True)
        self.state.mkdir(parents=True, exist_ok=True)

    def _write_json(self, folder: Path, prefix: str, payload: Dict[str, Any]) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = folder / f"{prefix}_{stamp}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def emit_command(self, target: str, command: str, args: Optional[Dict[str, Any]] = None, issued_by: str = "cli") -> Path:
        payload = {
            "type": "command",
            "target": target,
            "command": command,
            "args": args or {},
            "issued_by": issued_by,
            "timestamp": _utc_now_iso(),
        }
        return self._write_json(self.commands, "cmd", payload)

    def emit_event(self, source: str, event: str, data: Optional[Dict[str, Any]] = None, level: str = "info") -> Path:
        payload = {
            "type": "event",
            "source": source,
            "event": event,
            "level": level,
            "data": data or {},
            "timestamp": _utc_now_iso(),
        }
        path = self._write_json(self.events, "evt", payload)
        self._append_recent_event(payload)
        return path

    def _append_recent_event(self, payload: Dict[str, Any], max_lines: int = 12000, trim_target: int = 8000) -> None:
        line = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        try:
            with self.recent_events_cache.open("a", encoding="utf-8") as fp:
                fp.write(line)
                fp.write("\n")
        except OSError:
            return

        # Keep cache bounded to avoid unbounded growth.
        try:
            with self.recent_events_cache.open("r", encoding="utf-8") as fp:
                lines = fp.readlines()
            if len(lines) <= max_lines:
                return
            lines = lines[-trim_target:]
            with self.recent_events_cache.open("w", encoding="utf-8") as fp:
                fp.writelines(lines)
        except OSError:
            return

    def _read_recent_cache(self, limit: int) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if not self.recent_events_cache.exists():
            return items

        try:
            with self.recent_events_cache.open("r", encoding="utf-8") as fp:
                lines = fp.readlines()
        except OSError:
            return items

        for raw in reversed(lines):
            raw = raw.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                items.append(payload)
            else:
                items.append({"value": payload})
            if len(items) >= limit:
                break
        return items

    def warm_recent_events_cache(self, days: int = 3, max_lines: int = 8000) -> Dict[str, int]:
        days = max(1, int(days))
        max_lines = max(100, int(max_lines))
        now = datetime.now(timezone.utc)

        loaded: List[str] = []
        seen: set[tuple[str, str, str]] = set()

        for days_back in range(0, days):
            day = (now - timedelta(days=days_back)).strftime("%Y%m%d")
            for path in sorted(self.events.glob(f"evt_{day}_*.json"), reverse=True):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                key = (
                    str(payload.get("timestamp", "")),
                    str(payload.get("source", "")),
                    str(payload.get("event", "")),
                )
                if key in seen:
                    continue
                seen.add(key)
                loaded.append(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
                if len(loaded) >= max_lines:
                    break
            if len(loaded) >= max_lines:
                break

        loaded.reverse()
        try:
            with self.recent_events_cache.open("w", encoding="utf-8") as fp:
                for line in loaded:
                    fp.write(line)
                    fp.write("\n")
        except OSError:
            return {"written": 0, "errors": 1}

        return {"written": len(loaded), "errors": 0}

    def write_state(self, name: str, payload: Dict[str, Any]) -> Path:
        path = self.state / f"{name}.json"
        payload = dict(payload)
        payload.setdefault("timestamp", _utc_now_iso())
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def read_latest_events(self, limit: int = 25) -> List[Dict[str, Any]]:
        limit = max(1, int(limit))
        target = limit
        cached = self._read_recent_cache(limit)
        if len(cached) >= limit:
            return cached

        items: List[Dict[str, Any]] = []
        seen_keys: set[tuple[str, str, str]] = set()

        if cached:
            items.extend(cached)
            for payload in cached:
                seen_keys.add(
                    (
                        str(payload.get("timestamp", "")),
                        str(payload.get("source", "")),
                        str(payload.get("event", "")),
                    )
                )
            # Fall through and backfill only missing entries if needed.
            limit = max(1, limit - len(cached))

        # Fast path: recent days by filename prefix (evt_YYYYMMDD_...).
        now = datetime.now(timezone.utc)
        for days_back in range(0, 4):
            day = (now - timedelta(days=days_back)).strftime("%Y%m%d")
            for path in sorted(self.events.glob(f"evt_{day}_*.json"), reverse=True):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(payload, dict):
                    key = (
                        str(payload.get("timestamp", "")),
                        str(payload.get("source", "")),
                        str(payload.get("event", "")),
                    )
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                items.append(payload if isinstance(payload, dict) else {"value": payload})
                if len(items) >= limit:
                    return items[:target]

        # Fallback: bounded top-N by filename without sorting whole directory.
        # This still scans all entries but avoids materializing/sorting millions.
        candidates: list[tuple[str, Path]] = []
        try:
            with os.scandir(self.events) as it:
                for entry in it:
                    if not entry.is_file() or not entry.name.endswith(".json"):
                        continue
                    if len(candidates) < limit * 8:
                        heapq.heappush(candidates, (entry.name, Path(entry.path)))
                    else:
                        if entry.name > candidates[0][0]:
                            heapq.heapreplace(candidates, (entry.name, Path(entry.path)))
        except OSError:
            return items

        for _, path in sorted(candidates, key=lambda pair: pair[0], reverse=True)[:limit]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                key = (
                    str(payload.get("timestamp", "")),
                    str(payload.get("source", "")),
                    str(payload.get("event", "")),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
            items.append(payload if isinstance(payload, dict) else {"value": payload})
            if len(items) >= target:
                break
        return items[:target]

    def count_json_files(self, folder: Path) -> int:
        count = 0
        try:
            with os.scandir(folder) as it:
                for entry in it:
                    if entry.is_file() and entry.name.endswith(".json"):
                        count += 1
        except OSError:
            return 0
        return count

    def prune_events(self, keep_days: int = 3, archive: bool = True) -> Dict[str, int]:
        keep_days = max(1, int(keep_days))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).strftime("%Y%m%d")

        inspected = 0
        moved = 0
        deleted = 0
        errors = 0

        try:
            with os.scandir(self.events) as it:
                for entry in it:
                    if not entry.is_file() or not entry.name.endswith(".json"):
                        continue
                    if not entry.name.startswith("evt_") or len(entry.name) < 12:
                        continue

                    inspected += 1
                    day = entry.name[4:12]
                    if day >= cutoff:
                        continue

                    src = Path(entry.path)
                    try:
                        if archive:
                            dst_dir = self.events_archive / day
                            dst_dir.mkdir(parents=True, exist_ok=True)
                            src.replace(dst_dir / entry.name)
                            moved += 1
                        else:
                            src.unlink(missing_ok=True)
                            deleted += 1
                    except OSError:
                        errors += 1
        except OSError:
            errors += 1

        return {
            "inspected": inspected,
            "moved": moved,
            "deleted": deleted,
            "errors": errors,
            "cutoff_yyyymmdd": int(cutoff),
        }

    def poll_commands(self, seen: Optional[set[str]] = None) -> List[tuple[Path, Dict[str, Any]]]:
        known = seen if seen is not None else set()
        found: List[tuple[Path, Dict[str, Any]]] = []
        for path in sorted(self.commands.glob("*.json")):
            if path.name in known:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                known.add(path.name)
                continue
            known.add(path.name)
            found.append((path, payload))
        return found


def resolve_root_from_env() -> Path:
    env_root = os.environ.get("BOSSFORGE_ROOT")
    return Path(env_root).expanduser() if env_root else Path.home() / "BossCrafts"
