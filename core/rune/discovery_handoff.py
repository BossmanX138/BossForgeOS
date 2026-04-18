import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.rune.rune_bus import RuneBus


HANDS_ON_AGENT_IDS = {"runeforge", "codemage", "devlot"}

OWNER_ALIASES = {
    "runeforge": "runeforge",
    "rune forge": "runeforge",
    "codemage": "codemage",
    "code mage": "codemage",
    "devlot": "devlot",
    "archivist": "archivist",
}

TODO_LINE_RE = re.compile(r"\b(?:TODO|FIXME|TBD)\b", re.IGNORECASE)
OWNER_HINT_RE = re.compile(
    r"(?:TODO\s*[\[(]\s*(?P<todo_owner>[a-zA-Z_\- ]+)\s*[\])]"
    r"|owner\s*[:=]\s*(?P<kv_owner>[a-zA-Z_\- ]+)"
    r"|@(?P<at_owner>[a-zA-Z_\-]+))",
    re.IGNORECASE,
)
PATH_TOKEN_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"'`]+|\.{0,2}[\\/][^\s\"'`]+")
SCAN_SUFFIXES = {".md", ".txt", ".py", ".json", ".yaml", ".yml", ".ps1"}


def scheduled_discovery_window_key(window_minutes: int = 2, now: datetime | None = None) -> str | None:
    window_minutes = max(1, min(59, int(window_minutes)))
    current = now.astimezone(timezone.utc) if isinstance(now, datetime) else datetime.now(timezone.utc)
    if current.minute >= window_minutes:
        return None
    return current.strftime("%Y%m%d%H")


def _canonical_owner(raw: str) -> str:
    key = str(raw or "").strip().lower().replace("_", " ")
    return OWNER_ALIASES.get(key, "")


def _normalize_path_token(token: str) -> str:
    return token.strip().strip(",.;:!?)\"]}'")


def _extract_path_tokens(value: Any) -> list[str]:
    tokens: list[str] = []
    if isinstance(value, str):
        text = value.strip()
        if text:
            tokens.append(text)
            tokens.extend(PATH_TOKEN_RE.findall(text))
    elif isinstance(value, list):
        for item in value:
            tokens.extend(_extract_path_tokens(item))
    elif isinstance(value, dict):
        for item in value.values():
            tokens.extend(_extract_path_tokens(item))
    return [_normalize_path_token(token) for token in tokens if token and _normalize_path_token(token)]


def _resolve_candidate_path(token: str, root: Path) -> Path | None:
    if not token:
        return None
    raw = Path(token)
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append((root / raw).resolve())
        candidates.append((Path.cwd() / raw).resolve())
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _discover_files_near(paths: list[Path], limit: int = 30) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()

    def add_file(path: Path) -> None:
        if len(out) >= limit:
            return
        if path in seen:
            return
        if not path.exists() or not path.is_file():
            return
        if path.suffix.lower() not in SCAN_SUFFIXES:
            return
        seen.add(path)
        out.append(path)

    for path in paths:
        if len(out) >= limit:
            break
        if path.is_file():
            add_file(path)
            parent = path.parent
            for sibling in sorted(parent.iterdir()):
                if len(out) >= limit:
                    break
                add_file(sibling)
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if len(out) >= limit:
                    break
                add_file(child)
    return out


def _scan_todos(path: Path, current_agent: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return findings

    for index, line in enumerate(lines, start=1):
        if not TODO_LINE_RE.search(line):
            continue
        owner = ""
        match = OWNER_HINT_RE.search(line)
        if match:
            owner = _canonical_owner(
                match.group("todo_owner")
                or match.group("kv_owner")
                or match.group("at_owner")
                or ""
            )
        if not owner or owner == current_agent or owner not in HANDS_ON_AGENT_IDS:
            continue
        findings.append(
            {
                "owner": owner,
                "file": str(path),
                "line": index,
                "text": line.strip()[:400],
            }
        )
    return findings


def run_discovery_handoff(bus: RuneBus, agent_id: str, args: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    current_agent = str(agent_id or "").strip().lower()
    if current_agent not in HANDS_ON_AGENT_IDS:
        return {"ok": True, "skipped": True, "reason": "agent_not_hands_on"}

    if bool(args.get("discovery_handoff", False)):
        return {"ok": True, "skipped": True, "reason": "handoff_payload"}

    project_root = Path(root or bus.root)
    path_tokens = _extract_path_tokens(args)
    resolved_paths: list[Path] = []
    for token in path_tokens:
        resolved = _resolve_candidate_path(token, project_root)
        if resolved is not None:
            resolved_paths.append(resolved)

    candidate_files = _discover_files_near(resolved_paths)
    if not candidate_files:
        return {
            "ok": True,
            "scanned_files": 0,
            "handoffs_sent": 0,
            "resolved_paths": [str(path) for path in resolved_paths[:10]],
        }

    findings: list[dict[str, Any]] = []
    for file_path in candidate_files:
        findings.extend(_scan_todos(file_path, current_agent))

    sent = 0
    for finding in findings[:8]:
        target = str(finding.get("owner", "")).strip().lower()
        details = str(finding.get("text", "")).strip()
        file_path = str(finding.get("file", "")).strip()
        line_number = int(finding.get("line", 0) or 0)
        item_args = {
            "packet_id": "discovery_handoff",
            "title": f"TODO handoff from {current_agent}",
            "details": f"{details} (source: {file_path}:{line_number})",
            "source": "discovery_mode",
            "assigned_by": current_agent,
            "discovery_handoff": True,
            "discovered_owner": target,
            "source_path": file_path,
            "source_line": line_number,
        }
        bus.emit_command(target, "work_item", item_args, issued_by=f"{current_agent}:discovery_mode")
        sent += 1

    summary = {
        "ok": True,
        "agent": current_agent,
        "resolved_paths": [str(path) for path in resolved_paths[:10]],
        "scanned_files": len(candidate_files),
        "findings": len(findings),
        "handoffs_sent": sent,
    }
    if sent > 0:
        bus.emit_event(current_agent, "discovery_handoff", summary)
    return summary
