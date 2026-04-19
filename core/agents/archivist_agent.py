import argparse
import base64
import hashlib
import json
import os
import sys
import pathlib

# === Path Resolver for Bundled/Source Modes ===
def get_project_root():
    if getattr(sys, 'frozen', False):
        # PyInstaller bundled mode
        return pathlib.Path(sys.executable).parent
    return pathlib.Path(__file__).resolve().parent.parent.parent

PROJECT_ROOT = get_project_root()
import re
import shutil
import sqlite3
import subprocess
import threading
from datetime import datetime, timedelta, time as dt_time, timezone
from pathlib import Path
from typing import Any

from core.rune.rune_bus import RuneBus, resolve_root_from_env
from core.rune.discovery_handoff import run_discovery_handoff
from core.rune.agent_consumer import AgentConsumerLoop

from core.agent_registry import register_agent

UNCHECKED_CHECKLIST_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s*\[\s\]\s+(?P<task>.+?)\s*$", re.IGNORECASE)


class ArchivistAgent:
    TODO_SCAN_SUFFIXES = {".md", ".txt", ".py", ".ps1", ".json", ".yaml", ".yml"}
    TODO_IGNORE_DIR_NAMES = {
        ".git",
        ".continue",
        ".venv",
        ".venv-xtts",
        ".venv-vllm",
        ".runtime",
        ".models",
        "__pycache__",
        "node_modules",
        "build",
        "dist",
        "bus",
        "archives",
        "releases",
    }
    TODO_IGNORE_FILE_NAMES = {
        "delegation_notes.md",
        "daily_ledger.md",
        "autonomous_todo_backlog.md",
        "todos.md",
        "changelog.md",
        "decisions.md",
        "archivistreadme.md",
        "agent_task_assignments.md",
    }
    TODO_IGNORE_GLOBS = {
        "**/.venv/**",
        "**/.venv-*/**",
        "**/node_modules/**",
        "**/site-packages/**",
        "**/docs/autonomous_todo_backlog.md",
        "**/docs/delegation_notes.md",
        "**/docs/daily_ledger.md",
    }
    README_IGNORE_DIR_NAMES = {
        ".git",
        ".venv",
        ".venv-xtts",
        ".venv-vllm",
        ".runtime",
        ".models",
        "__pycache__",
        "node_modules",
        "build",
        "dist",
        "bus",
        "archives",
        "releases",
        "site-packages",
    }
    TODO_PATTERNS = ["TODO", "FIXME", "TBD"]
    TODO_ACTION_WORDS = {
        "add",
        "build",
        "complete",
        "create",
        "define",
        "document",
        "fix",
        "implement",
        "improve",
        "investigate",
        "migrate",
        "optimize",
        "refactor",
        "remove",
        "replace",
        "review",
        "ship",
        "update",
        "validate",
        "write",
    }
    RUNEBUS_IMPORTANT_LEVELS = {"warning", "error", "critical"}
    RUNEBUS_IMPORTANT_KEYWORDS = {
        "error",
        "fail",
        "failed",
        "exception",
        "critical",
        "security",
        "incident",
        "seal",
        "deploy",
        "rollback",
        "panic",
    }
    RUNEBUS_PROJECT_KEYS = {
        "project",
        "project_id",
        "project_path",
        "project_root",
        "repo",
        "repository",
        "ticket",
        "issue",
    }

    def __init__(self, interval_seconds: int = 15, root: Path | None = None, daily_run_time: str = "00:45") -> None:
        self.interval_seconds = interval_seconds
        self.bus = RuneBus(root or resolve_root_from_env())
        self.daily_run_time = daily_run_time
        self.seen_commands: set[str] = set()
        self.archives_root = self.bus.root / "archives"
        self.archives_root.mkdir(parents=True, exist_ok=True)
        self.last_daily_run_key: str | None = None
        self.maintenance_state_path = self.bus.state / "archivist_bus_maintenance.json"
        self.last_bus_maintenance_at = self._load_last_bus_maintenance_at()
        self.policy_path = self.bus.state / "archivist_policy.json"
        self.policy = self._load_policy()
        
        # Register with central agent registry
        profile = {
            "id": "archivist",
            "name": "ArchivistAgent",
            "description": "Project archivist, TODO/test debt scanner, and documentation agent.",
        }
        try:
            register_agent("archivist", profile)
        except ValueError:
            # Keep local invocation functional while legacy profiles migrate to stricter registry schema.
            pass

    def _default_policy(self) -> dict[str, Any]:
        return {
            "todo_scan_suffixes": sorted(self.TODO_SCAN_SUFFIXES),
            "todo_ignore_dir_names": sorted(self.TODO_IGNORE_DIR_NAMES),
            "todo_ignore_file_names": sorted(self.TODO_IGNORE_FILE_NAMES),
            "todo_ignore_globs": sorted(self.TODO_IGNORE_GLOBS),
            "readme_ignore_dir_names": sorted(self.README_IGNORE_DIR_NAMES),
            "todo_patterns": list(self.TODO_PATTERNS),
            "runebus_maintenance": {
                "enabled": True,
                "interval_hours": 24,
                "min_age_hours": 24,
            },
        }

    def _load_last_bus_maintenance_at(self) -> datetime | None:
        if not self.maintenance_state_path.exists():
            return None
        try:
            payload = json.loads(self.maintenance_state_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return None
            value = str(payload.get("last_run_at", "")).strip()
            if not value:
                return None
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (OSError, json.JSONDecodeError, ValueError):
            return None

    def _save_last_bus_maintenance_at(self, at: datetime) -> None:
        payload = {"last_run_at": at.astimezone(timezone.utc).isoformat()}
        try:
            self.maintenance_state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _runebus_maintenance_config(self) -> dict[str, Any]:
        cfg = self.policy.get("runebus_maintenance")
        if not isinstance(cfg, dict):
            return {"enabled": True, "interval_hours": 24, "min_age_hours": 24}
        enabled = bool(cfg.get("enabled", True))
        interval_hours = max(1, int(cfg.get("interval_hours", 24) or 24))
        min_age_hours = max(1, int(cfg.get("min_age_hours", 24) or 24))
        return {
            "enabled": enabled,
            "interval_hours": interval_hours,
            "min_age_hours": min_age_hours,
        }

    def _is_runebus_payload_important(self, payload: dict[str, Any], file_name: str) -> bool:
        level = str(payload.get("level", "")).strip().lower()
        if level in self.RUNEBUS_IMPORTANT_LEVELS:
            return True

        source = str(payload.get("source", "")).strip().lower()
        if source in {"security_sentinel", "archivist", "test_sentinel"}:
            return True

        text_fields = [
            file_name,
            str(payload.get("event", "")),
            str(payload.get("command", "")),
            str(payload.get("message", "")),
        ]
        blob = " ".join(text_fields).lower()
        if any(token in blob for token in self.RUNEBUS_IMPORTANT_KEYWORDS):
            return True

        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
        for key in self.RUNEBUS_PROJECT_KEYS:
            if key in payload and str(payload.get(key, "")).strip():
                return True
            if key in data and str(data.get(key, "")).strip():
                return True
            if key in args and str(args.get(key, "")).strip():
                return True

        return False

    def _maintain_runebus_folder(
        self,
        folder: Path,
        archive_folder: Path,
        min_age: timedelta,
    ) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        stats = {
            "inspected": 0,
            "archived": 0,
            "deleted": 0,
            "important": 0,
            "unimportant": 0,
            "errors": 0,
        }

        try:
            with os.scandir(folder) as it:
                for entry in it:
                    if not entry.is_file() or not entry.name.endswith(".json"):
                        continue
                    stats["inspected"] += 1

                    try:
                        mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
                        if (now - mtime) < min_age:
                            continue
                    except OSError:
                        stats["errors"] += 1
                        continue

                    src = Path(entry.path)
                    try:
                        payload = json.loads(src.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        payload = {}

                    payload = payload if isinstance(payload, dict) else {}
                    important = self._is_runebus_payload_important(payload, entry.name)

                    try:
                        if important:
                            archive_folder.mkdir(parents=True, exist_ok=True)
                            src.replace(archive_folder / entry.name)
                            stats["archived"] += 1
                            stats["important"] += 1
                        else:
                            src.unlink(missing_ok=True)
                            stats["deleted"] += 1
                            stats["unimportant"] += 1
                    except OSError:
                        stats["errors"] += 1
        except OSError:
            stats["errors"] += 1

        return stats

    def maintain_runebus_unread(self) -> dict[str, Any]:
        cfg = self._runebus_maintenance_config()
        if not cfg.get("enabled", True):
            return {"ok": True, "skipped": True, "reason": "disabled"}

        min_age = timedelta(hours=int(cfg.get("min_age_hours", 24)))
        target = self._new_archive_dir("runebus")
        events_archive = target / "events"
        commands_archive = target / "commands"

        events_stats = self._maintain_runebus_folder(self.bus.events, events_archive, min_age)
        commands_stats = self._maintain_runebus_folder(self.bus.commands, commands_archive, min_age)

        result = {
            "ok": True,
            "archive_path": str(target),
            "config": cfg,
            "events": events_stats,
            "commands": commands_stats,
        }

        self.bus.emit_event("archivist", "runebus_maintenance", result)
        return result

    def _normalize_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        return out

    def _load_policy(self) -> dict[str, Any]:
        default = self._default_policy()
        if not self.policy_path.exists():
            try:
                self.policy_path.parent.mkdir(parents=True, exist_ok=True)
                self.policy_path.write_text(json.dumps(default, indent=2), encoding="utf-8")
            except OSError:
                pass
            return default

        try:
            loaded = json.loads(self.policy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default
        if not isinstance(loaded, dict):
            return default

        merged = dict(default)
        for key in [
            "todo_scan_suffixes",
            "todo_ignore_dir_names",
            "todo_ignore_file_names",
            "readme_ignore_dir_names",
            "todo_patterns",
        ]:
            values = self._normalize_list(loaded.get(key))
            if values:
                merged[key] = values
        return merged

    def _refresh_policy(self) -> None:
        self.policy = self._load_policy()

    def _todo_scan_suffixes(self) -> set[str]:
        values = self._normalize_list(self.policy.get("todo_scan_suffixes"))
        if not values:
            values = sorted(self.TODO_SCAN_SUFFIXES)
        return {v.lower() if v.startswith(".") else f".{v.lower()}" for v in values}

    def _todo_ignore_dir_names(self) -> set[str]:
        values = self._normalize_list(self.policy.get("todo_ignore_dir_names"))
        if not values:
            values = sorted(self.TODO_IGNORE_DIR_NAMES)
        return {v.lower() for v in values}

    def _todo_ignore_file_names(self) -> set[str]:
        values = self._normalize_list(self.policy.get("todo_ignore_file_names"))
        if not values:
            values = sorted(self.TODO_IGNORE_FILE_NAMES)
        return {v.lower() for v in values}

    def _todo_ignore_globs(self) -> list[str]:
        values = self._normalize_list(self.policy.get("todo_ignore_globs"))
        if not values:
            values = sorted(self.TODO_IGNORE_GLOBS)
        return values

    def _readme_ignore_dir_names(self) -> set[str]:
        values = self._normalize_list(self.policy.get("readme_ignore_dir_names"))
        if not values:
            values = sorted(self.README_IGNORE_DIR_NAMES)
        return {v.lower() for v in values}

    def _todo_regex(self) -> re.Pattern[str]:
        raw_tokens = self._normalize_list(self.policy.get("todo_patterns"))
        tokens = raw_tokens or list(self.TODO_PATTERNS)
        escaped = "|".join(re.escape(token) for token in tokens)
        # Word boundaries avoid false positives like todo_or_open and ToDosDateTime.
        return re.compile(rf"\b(?:{escaped})\b", re.IGNORECASE)

    @property
    def onboarded_projects_path(self) -> Path:
        return self.bus.root / "archivist_onboarded_projects.json"

    @property
    def seal_queue_path(self) -> Path:
        return self.bus.state / "archivist_seal_queue.json"

    def get_onboarded_projects(self) -> list[Path]:
        if self.onboarded_projects_path.exists():
            try:
                payload = json.loads(self.onboarded_projects_path.read_text(encoding="utf-8"))
                raw = payload.get("projects", [])
                projects = [Path(item).expanduser() for item in raw if isinstance(item, str)]
                valid = [p for p in projects if p.exists() and p.is_dir()]
                if valid:
                    return valid
            except (OSError, json.JSONDecodeError):
                pass

        default_project = Path.cwd()
        return [default_project]

    def add_onboarded_project(self, path: str) -> dict[str, Any]:
        project = Path(path).expanduser().resolve()
        if not project.exists() or not project.is_dir():
            return {"ok": False, "message": f"invalid project path: {project}"}

        projects = self.get_onboarded_projects()
        as_strings = sorted({str(p.resolve()) for p in projects} | {str(project)})
        payload = {"projects": as_strings}
        self.onboarded_projects_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"ok": True, "projects": as_strings}

    def _ensure_markdown(self, path: Path, heading: str, intro: str) -> bool:
        if path.exists():
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        content = f"# {heading}\n\n{intro}\n"
        path.write_text(content, encoding="utf-8")
        return True

    def _append_daily_ledger(self, project: Path, lines: list[str]) -> Path:
        ledger = project / "docs" / "daily_ledger.md"
        if not ledger.exists():
            ledger.write_text("# Daily Ledger\n\n", encoding="utf-8")

        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        block = [f"## {stamp}"] + lines + [""]
        with ledger.open("a", encoding="utf-8") as f:
            f.write("\n".join(block))
        return ledger

    def _should_skip_todo_path(self, path: Path, project: Path) -> bool:
        try:
            rel = path.resolve().relative_to(project.resolve())
        except Exception:
            return True

        if path.name.lower() in self._todo_ignore_file_names():
            return True

        parts = {p.lower() for p in rel.parts}
        if parts & self._todo_ignore_dir_names():
            return True
        if "site-packages" in parts:
            return True

        rel_posix = rel.as_posix().lower()
        for pattern in self._todo_ignore_globs():
            p = pattern.strip().lower()
            if not p:
                continue
            if Path(rel_posix).match(p):
                return True

        return False

    def _is_noise_todo_line(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return True

        lower = stripped.lower()
        if any(token in lower for token in ["site-packages", "node_modules", ".venv", "__pycache__"]):
            return True

        # Backlog/ledger/delegation transcript lines are references, not work items.
        if re.match(r"^\s*-\s*\[[^\]]+:[0-9]+\]\s*-\s*", stripped):
            return True
        if " :: " in stripped and stripped.startswith("-"):
            return True
        if re.match(r"^\s*[-*]\s*\[[^\]]+\]\(#[^\)]+\)", stripped):
            return True

        if stripped.lower() in {"todo", "fixme", "tbd", "## todo", "# todo"}:
            return True

        return False

    def _is_actionable_todo_text(self, text: str) -> bool:
        if self._is_noise_todo_line(text):
            return False

        lower = text.lower()
        if any(word in lower for word in self.TODO_ACTION_WORDS):
            return True

        # Keep explicit TODO/FIXME markers as actionable by default.
        if re.search(r"\b(todo|fixme|tbd)\b", lower):
            return True

        # If a custom token matched but no action language is present, treat as weak/noise.
        return False

    def _severity_for_text(self, text: str) -> str:
        lower = text.lower()
        if "fixme" in lower or any(k in lower for k in ["security", "crash", "critical", "data loss"]):
            return "high"
        if "tbd" in lower or any(k in lower for k in ["later", "investigate", "review"]):
            return "low"
        return "medium"

    def _is_test_debt_item(self, path: Path, project: Path, text: str) -> bool:
        try:
            rel = path.resolve().relative_to(project.resolve())
        except Exception:
            return False
        parts = [p.lower() for p in rel.parts]
        filename = path.name.lower()
        if "tests" in parts:
            return True
        if filename.startswith("test_") or filename.endswith("_test.py"):
            return True
        lower = text.lower()
        if any(k in lower for k in ["assert", "coverage", "flaky test", "regression test"]):
            return True
        return False

    def _suggest_next_action(self, text: str, assignee: str, severity: str) -> str:
        lower = text.lower()
        if assignee == "archivist":
            return "Update documentation section and cross-link related docs"
        if assignee == "runeforge":
            return "Validate model/runtime impact and propose configuration update"
        if assignee == "codemage":
            if severity == "high":
                return "Create fix plan, implement patch, and add regression tests"
            return "Open implementation task with acceptance criteria and tests"
        if assignee == "test_sentinel":
            return "Add or improve tests, then record updated test metrics"
        if "todo" in lower:
            return "Convert this note into a tracked work item with owner/date"
        return "Review context, confirm scope, and create a concrete next task"

    def _todo_priority_score(self, item: dict[str, Any]) -> int:
        severity = str(item.get("severity", "medium")).lower()
        severity_score = {"high": 3, "medium": 2, "low": 1}.get(severity, 1)
        text = str(item.get("text", "")).lower()
        action_bonus = 2 if any(word in text for word in self.TODO_ACTION_WORDS) else 0
        test_bonus = 1 if bool(item.get("is_test_debt")) else 0
        return severity_score * 10 + action_bonus + test_bonus

    def _dedupe_todos(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in items:
            key = (
                str(item.get("file", "")).lower(),
                str(item.get("line", "")),
                re.sub(r"\s+", " ", str(item.get("text", "")).strip().lower()),
            )
            if key not in unique:
                unique[key] = item
        return list(unique.values())

    def _write_actionable_todos(self, project: Path, todos: list[dict[str, Any]]) -> Path:
        todos_path = project / "docs" / "todos.md"
        todos_path.parent.mkdir(parents=True, exist_ok=True)

        deduped = self._dedupe_todos(todos)
        ranked = sorted(deduped, key=lambda item: self._todo_priority_score(item), reverse=True)
        general = [item for item in ranked if not bool(item.get("is_test_debt"))]
        test_debt = [item for item in ranked if bool(item.get("is_test_debt"))]

        lines = [
            "# Open Todos",
            "",
            "Curated by Archivist from actionable TODO/FIXME/TBD signals.",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total actionable: {len(ranked)}",
            f"General backlog: {len(general)}",
            f"Test debt: {len(test_debt)}",
            "",
            "## Priority Backlog",
            "",
        ]

        if general:
            for item in general[:80]:
                assignee = str(item.get("assignee", "devlot"))
                severity = str(item.get("severity", "medium"))
                lines.append(
                    f"- [{assignee}][{severity}] {item['file']}:{item['line']} :: {item['text']}"
                )
                lines.append(f"  next: {item.get('suggested_next_action', '')}")
        else:
            lines.append("- No actionable general backlog detected.")

        lines.extend(["", "## Test Debt", ""])

        if test_debt:
            for item in test_debt[:40]:
                assignee = str(item.get("assignee", "test_sentinel"))
                severity = str(item.get("severity", "medium"))
                lines.append(
                    f"- [{assignee}][{severity}] {item['file']}:{item['line']} :: {item['text']}"
                )
                lines.append(f"  next: {item.get('suggested_next_action', '')}")
        else:
            lines.append("- No actionable test debt detected.")

        lines.append("")
        todos_path.write_text("\n".join(lines), encoding="utf-8")
        return todos_path

    def _collect_todos(self, project: Path) -> list[dict[str, Any]]:
        todo_items: list[dict[str, Any]] = []
        pattern = self._todo_regex()
        ignore_dirs = self._todo_ignore_dir_names()
        allowed_suffixes = self._todo_scan_suffixes()

        for root, dirnames, filenames in os.walk(project):
            # Prune ignored directories in-place to prevent expensive deep traversal.
            dirnames[:] = [d for d in dirnames if d.lower() not in ignore_dirs]

            root_path = Path(root)
            for filename in filenames:
                path = root_path / filename
                if self._should_skip_todo_path(path, project):
                    continue
                if path.suffix.lower() not in allowed_suffixes:
                    continue

                try:
                    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
                except OSError:
                    continue

                for idx, line in enumerate(lines, start=1):
                    todo_match = bool(pattern.search(line))
                    checklist_match = UNCHECKED_CHECKLIST_RE.match(line)
                    if not todo_match and not checklist_match:
                        continue
                    text = line.strip() if todo_match else str(checklist_match.group("task") if checklist_match else "").strip()
                    text = text[:240]
                    if not self._is_actionable_todo_text(text):
                        continue
                    is_test_debt = self._is_test_debt_item(path=path, project=project, text=text)
                    assignee = "test_sentinel" if is_test_debt else self._delegate_for(text)
                    severity = self._severity_for_text(text)
                    context_before = lines[idx - 2].strip()[:240] if idx - 2 >= 0 else ""
                    context_after = lines[idx].strip()[:240] if idx < len(lines) else ""
                    todo_items.append(
                        {
                            "file": str(path),
                            "line": str(idx),
                            "text": text,
                            "context_before": context_before,
                            "context_after": context_after,
                            "assignee": assignee,
                            "is_test_debt": is_test_debt,
                            "severity": severity,
                            "suggested_next_action": self._suggest_next_action(text, assignee, severity),
                        }
                    )
        return todo_items

    def _slugify_heading(self, text: str) -> str:
        slug = re.sub(r"[^a-z0-9\s-]", "", text.lower()).strip()
        slug = re.sub(r"\s+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug

    def _owned_readme_files(self, project: Path) -> list[Path]:
        readmes: list[Path] = []
        readme_ignore_dirs = self._readme_ignore_dir_names()
        for root, dirnames, filenames in os.walk(project):
            dirnames[:] = [d for d in dirnames if d.lower() not in readme_ignore_dirs]
            root_path = Path(root)
            for filename in filenames:
                lower = filename.lower()
                if lower.endswith(".md") and lower.startswith("readme"):
                    readmes.append(root_path / filename)
        return sorted(readmes)

    def _update_readme_toc(self, path: Path) -> bool:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return False

        if not lines:
            return False

        heading_re = re.compile(r"^##\s+(.+?)\s*$")

        # Remove existing TOC block if present so it can be regenerated idempotently.
        toc_start = -1
        for idx, line in enumerate(lines):
            if line.strip().lower() == "## table of contents":
                toc_start = idx
                break
        if toc_start != -1:
            toc_end = toc_start + 1
            while toc_end < len(lines):
                stripped = lines[toc_end].strip()
                if lines[toc_end].startswith("## ") and stripped.lower() != "## table of contents":
                    break
                toc_end += 1
            lines = lines[:toc_start] + lines[toc_end:]

        headings: list[str] = []
        for line in lines:
            m = heading_re.match(line)
            if not m:
                continue
            text = m.group(1).strip()
            if text.lower() == "table of contents":
                continue
            headings.append(text)

        if not headings:
            return False

        toc_lines = ["## Table of Contents", ""]
        for heading in headings:
            toc_lines.append(f"- [{heading}](#{self._slugify_heading(heading)})")
        toc_lines.append("")

        insert_idx = -1
        for idx, line in enumerate(lines):
            if line.startswith("## "):
                insert_idx = idx
                break
        if insert_idx == -1:
            insert_idx = len(lines)

        new_lines = lines[:insert_idx]
        if new_lines and new_lines[-1].strip() != "":
            new_lines.append("")
        new_lines.extend(toc_lines)
        new_lines.extend(lines[insert_idx:])

        content = "\n".join(new_lines).rstrip() + "\n"
        try:
            current = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False
        if current == content:
            return False

        try:
            path.write_text(content, encoding="utf-8")
        except OSError:
            return False
        return True

    def _steward_readmes(self, project: Path) -> list[str]:
        updated: list[str] = []
        for readme in self._owned_readme_files(project):
            if self._update_readme_toc(readme):
                updated.append(str(readme))
        return updated

    def _delegate_for(self, text: str) -> str:
        lower = text.lower()
        if any(k in lower for k in ["docs", "readme", "changelog", "ledger"]):
            return "archivist"
        if any(k in lower for k in ["test", "bug", "fix", "refactor", "code"]):
            return "codemage"
        if any(k in lower for k in ["model", "endpoint", "gpu", "vllm"]):
            return "runeforge"
        return "devlot"

    def _dispatch_to_runeforge_review(self, project: Path, todos: list[dict[str, Any]], source_doc: Path) -> dict[str, Any]:
        if not todos:
            return {"ok": True, "submitted": 0, "skipped": True}

        queue_items: list[dict[str, Any]] = []
        for idx, item in enumerate(todos[:150], start=1):
            queue_items.append(
                {
                    "id": f"archivist-{datetime.now().strftime('%Y%m%d%H%M%S')}-{idx}",
                    "title": f"{Path(str(item.get('file', ''))).name}:{item.get('line', '')}",
                    "details": str(item.get("text", "")).strip(),
                    "assignee": str(item.get("assignee", "devlot")).strip() or "devlot",
                    "severity": str(item.get("severity", "medium")).strip() or "medium",
                    "source_path": str(item.get("file", "")).strip(),
                    "source_line": int(item.get("line", 0) or 0),
                    "suggested_next_action": str(item.get("suggested_next_action", "")).strip(),
                    "is_test_debt": bool(item.get("is_test_debt", False)),
                }
            )

        payload = {
            "project_path": str(project),
            "source_doc": str(source_doc),
            "submitted_by": "archivist",
            "items": queue_items,
        }
        self.bus.emit_command("runeforge", "review_archivist_delegations", payload, issued_by="archivist")
        self.bus.emit_event(
            "archivist",
            "delegation_submitted_to_runeforge",
            {
                "project_path": str(project),
                "submitted": len(queue_items),
                "source_doc": str(source_doc),
            },
        )
        return {"ok": True, "submitted": len(queue_items), "source_doc": str(source_doc)}

    def on_invoke(self) -> dict[str, Any]:
        self._refresh_policy()
        projects = self.get_onboarded_projects()
        produced_docs: list[str] = []
        delegation_total = 0
        changes_total = 0

        for project in projects:
            docs_dir = project / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)

            readme_created = self._ensure_markdown(
                project / "README.md",
                project.name,
                "Project overview will be maintained by Archivist.",
            )
            changelog_created = self._ensure_markdown(
                docs_dir / "CHANGELOG.md",
                "Changelog",
                "All notable documentation and system updates are tracked here.",
            )
            decisions_created = self._ensure_markdown(
                docs_dir / "decisions.md",
                "Decision Log",
                "Architectural and operational decisions are recorded here.",
            )
            todos_created = self._ensure_markdown(
                docs_dir / "todos.md",
                "Open Todos",
                "Outstanding work and delegated actions are tracked here.",
            )
            archivist_readme_created = self._ensure_markdown(
                docs_dir / "archivistREADME.md",
                "Archivist Stewardship",
                "This file records Archivist maintenance operations and outputs.",
            )

            readmes_updated = self._steward_readmes(project)

            changes_total += sum(int(x) for x in [readme_created, changelog_created, decisions_created, todos_created, archivist_readme_created])
            changes_total += len(readmes_updated)

            todos = self._collect_todos(project)
            todos = self._dedupe_todos(todos)
            delegation_total += len(todos)

            todos_file = self._write_actionable_todos(project, todos)
            runeforge_submission = self._dispatch_to_runeforge_review(project, todos, todos_file)

            delegation_file = docs_dir / "delegation_notes.md"
            if not delegation_file.exists():
                delegation_file.write_text("# Delegation Notes\n\n", encoding="utf-8")

            if todos:
                with delegation_file.open("a", encoding="utf-8") as f:
                    f.write(f"## {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    test_debt = [item for item in todos if bool(item.get("is_test_debt"))]
                    general_backlog = [item for item in todos if not bool(item.get("is_test_debt"))]

                    if general_backlog:
                        f.write("### General Backlog\n")
                        for item in general_backlog[:100]:
                            assignee = str(item.get("assignee") or self._delegate_for(str(item.get("text", ""))))
                            severity = str(item.get("severity", "medium"))
                            f.write(f"- [{assignee}][{severity}] {item['file']}:{item['line']} :: {item['text']}\n")
                            before = str(item.get("context_before", "")).strip()
                            after = str(item.get("context_after", "")).strip()
                            if before or after:
                                f.write(f"  context: prev='{before}' | next='{after}'\n")
                            f.write(f"  next: {item.get('suggested_next_action', '')}\n")

                    if test_debt:
                        f.write("### Test Debt\n")
                        for item in test_debt[:100]:
                            assignee = str(item.get("assignee") or "test_sentinel")
                            severity = str(item.get("severity", "medium"))
                            f.write(f"- [{assignee}][{severity}] {item['file']}:{item['line']} :: {item['text']}\n")
                            before = str(item.get("context_before", "")).strip()
                            after = str(item.get("context_after", "")).strip()
                            if before or after:
                                f.write(f"  context: prev='{before}' | next='{after}'\n")
                            f.write(f"  next: {item.get('suggested_next_action', '')}\n")
                    f.write("\n")

            test_debt_count = sum(1 for item in todos if bool(item.get("is_test_debt")))
            general_count = len(todos) - test_debt_count
            ledger_lines = [
                f"- surveyed_project: {project}",
                f"- docs_created_or_initialized: {changes_total}",
                f"- readmes_stewarded: {len(readmes_updated)}",
                f"- todos_detected: {len(todos)}",
                f"- general_backlog_detected: {general_count}",
                f"- test_debt_detected: {test_debt_count}",
                f"- runeforge_review_submitted: {int(runeforge_submission.get('submitted', 0) or 0)}",
                "- commit_status: awaiting_seal",
            ]
            ledger_path = self._append_daily_ledger(project, ledger_lines)

            produced_docs.extend(
                [
                    *readmes_updated,
                    str(docs_dir / "CHANGELOG.md"),
                    str(docs_dir / "decisions.md"),
                    str(docs_dir / "todos.md"),
                    str(todos_file),
                    str(docs_dir / "archivistREADME.md"),
                    str(ledger_path),
                    str(delegation_file),
                ]
            )

            self._enqueue_seal(project, produced_docs=[
                *readmes_updated,
                str(project / "README.md"),
                str(docs_dir / "CHANGELOG.md"),
                str(docs_dir / "decisions.md"),
                str(todos_file),
                str(docs_dir / "archivistREADME.md"),
                str(ledger_path),
                str(delegation_file),
            ])

        result = {
            "ok": True,
            "projects_surveyed": len(projects),
            "doc_updates": produced_docs,
            "delegation_notes": delegation_total,
            "changes_detected": changes_total,
            "commit": "awaiting_seal",
        }
        self.bus.emit_event("archivist", "awaiting_seal", {"message": "Documentation updated. Ask user before commit/push."})
        return result

    def _git_run(self, project: Path, args: list[str]) -> tuple[bool, str]:
        try:
            out = subprocess.check_output(["git", "-C", str(project), *args], text=True, stderr=subprocess.STDOUT)
            return True, out.strip()
        except Exception as ex:
            return False, str(ex)

    def _read_origin_url(self, project: Path) -> str:
        ok, out = self._git_run(project, ["config", "--get", "remote.origin.url"])
        if not ok:
            return ""
        return out.strip()

    def _is_github_origin(self, project: Path) -> bool:
        origin = self._read_origin_url(project).lower()
        return "github.com" in origin

    def _read_vault_secret(self, name: str) -> str:
        vault_path = self.bus.state / "security_secrets_vault.json"
        if not vault_path.exists():
            return ""
        try:
            payload = json.loads(vault_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        if not isinstance(payload, dict):
            return ""
        cipher = payload.get(name)
        if not isinstance(cipher, str) or not cipher:
            return ""
        try:
            from core.security.security_vault import unprotect_text

            return str(unprotect_text(cipher))
        except Exception:
            return ""

    def _get_github_access_token(self) -> str:
        oauth_raw = self._read_vault_secret("oauth:github")
        if oauth_raw:
            try:
                payload = json.loads(oauth_raw)
                if isinstance(payload, dict):
                    token = payload.get("access_token")
                    if isinstance(token, str) and token.strip():
                        return token.strip()
            except json.JSONDecodeError:
                pass

        direct = self._read_vault_secret("github_api_key")
        if direct.strip():
            return direct.strip()
        return ""

    def _git_push(self, project: Path) -> tuple[bool, str]:
        token = self._get_github_access_token()
        if token and self._is_github_origin(project):
            auth = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
            return self._git_run(project, ["-c", f"http.extraHeader=AUTHORIZATION: basic {auth}", "push"])
        return self._git_run(project, ["push"])

    def _is_git_repo(self, project: Path) -> bool:
        ok, out = self._git_run(project, ["rev-parse", "--is-inside-work-tree"])
        return ok and out.lower().strip() == "true"

    def _load_seal_queue(self) -> dict[str, Any]:
        if self.seal_queue_path.exists():
            try:
                return json.loads(self.seal_queue_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return {"pending": [], "history": []}

    def _save_seal_queue(self, payload: dict[str, Any]) -> None:
        self.seal_queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.seal_queue_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.bus.write_state("archivist_seal_queue", payload)

    def _enqueue_seal(self, project: Path, produced_docs: list[str]) -> None:
        payload = self._load_seal_queue()
        pending = payload.get("pending", [])
        seal = {
            "seal_id": f"seal_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            "project_path": str(project),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "awaiting_seal",
            "repo_available": self._is_git_repo(project),
            "doc_updates": sorted({p for p in produced_docs if str(project) in p}),
            "commit_message": f"docs(archivist): stewardship update {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        }
        pending.append(seal)
        payload["pending"] = pending
        self._save_seal_queue(payload)

    def preview_seal(self) -> dict[str, Any]:
        payload = self._load_seal_queue()
        return {"ok": True, **payload}

    def _select_pending_seal(self, seal_id: str | None) -> tuple[dict[str, Any] | None, dict[str, Any], int]:
        payload = self._load_seal_queue()
        pending = payload.get("pending", [])
        if not pending:
            return None, payload, -1
        if seal_id:
            for idx, item in enumerate(pending):
                if item.get("seal_id") == seal_id:
                    return item, payload, idx
            return None, payload, -1
        return pending[-1], payload, len(pending) - 1

    def approve_seal(
        self,
        seal_id: str | None = None,
        commit_message: str | None = None,
        push: bool = False,
        init_repo_if_missing: bool = True,
    ) -> dict[str, Any]:
        seal, payload, idx = self._select_pending_seal(seal_id)
        if seal is None:
            return {"ok": False, "message": "no pending seal found"}

        project = Path(str(seal.get("project_path", "")))
        if not self._is_git_repo(project):
            if not init_repo_if_missing:
                seal["status"] = "sealed_no_git"
                seal["sealed_at"] = datetime.now(timezone.utc).isoformat()
                seal["push"] = False
                seal["result"] = {"message": "approved without git commit (repository not initialized)"}

                pending = payload.get("pending", [])
                pending.pop(idx)
                history = payload.get("history", [])
                history.append(seal)
                payload["pending"] = pending
                payload["history"] = history[-100:]
                self._save_seal_queue(payload)

                return {
                    "ok": True,
                    "seal_id": seal.get("seal_id"),
                    "status": "sealed_no_git",
                    "message": f"approved without git commit (not a git repository): {project}",
                }

            ok_init, out_init = self._git_run(project, ["init"])
            if not ok_init:
                return {
                    "ok": False,
                    "seal_id": seal.get("seal_id"),
                    "message": f"failed to initialize git repository: {out_init}",
                }
            seal["repo_initialized"] = True

        doc_updates = [Path(p) for p in seal.get("doc_updates", []) if Path(p).exists()]
        if not doc_updates:
            return {"ok": False, "message": "no updated files to commit", "seal_id": seal.get("seal_id")}

        relative_paths = [str(p.resolve().relative_to(project.resolve())).replace("\\", "/") for p in doc_updates if str(project.resolve()) in str(p.resolve())]
        ok_add, out_add = self._git_run(project, ["add", *relative_paths])
        if not ok_add:
            return {"ok": False, "message": out_add, "seal_id": seal.get("seal_id")}

        message = commit_message or str(seal.get("commit_message", "docs(archivist): seal"))
        ok_commit, out_commit = self._git_run(project, ["-c", "user.name=BossForge Archivist", "-c", "user.email=archivist@bossforge.local", "commit", "-m", message])
        if not ok_commit:
            return {"ok": False, "message": out_commit, "seal_id": seal.get("seal_id")}

        push_output = ""
        if push:
            ok_push, out_push = self._git_push(project)
            if not ok_push:
                return {"ok": False, "message": out_push, "seal_id": seal.get("seal_id")}
            push_output = out_push

        ok_hash, commit_hash = self._git_run(project, ["rev-parse", "HEAD"])
        seal["status"] = "sealed"
        seal["sealed_at"] = datetime.now(timezone.utc).isoformat()
        seal["commit_message"] = message
        seal["commit_hash"] = commit_hash if ok_hash else ""
        seal["push"] = push
        seal["result"] = {"commit": out_commit, "push": push_output}

        pending = payload.get("pending", [])
        pending.pop(idx)
        history = payload.get("history", [])
        history.append(seal)
        payload["pending"] = pending
        payload["history"] = history[-100:]
        self._save_seal_queue(payload)

        return {"ok": True, "seal_id": seal.get("seal_id"), "commit_hash": seal.get("commit_hash"), "push": push}

    def reject_seal(self, seal_id: str | None = None, reason: str | None = None) -> dict[str, Any]:
        seal, payload, idx = self._select_pending_seal(seal_id)
        if seal is None:
            return {"ok": False, "message": "no pending seal found"}

        seal["status"] = "rejected"
        seal["rejected_at"] = datetime.now(timezone.utc).isoformat()
        seal["reason"] = reason or "user rejected"

        pending = payload.get("pending", [])
        pending.pop(idx)
        history = payload.get("history", [])
        history.append(seal)
        payload["pending"] = pending
        payload["history"] = history[-100:]
        self._save_seal_queue(payload)
        return {"ok": True, "seal_id": seal.get("seal_id"), "status": "rejected"}

    def Archive_index_db(
        self,
        project_path: str,
        db_path: str,
        include_patterns: list[str] | None = None,
        db_type: str = "sqlite",
    ) -> dict[str, Any]:
        project = Path(project_path).expanduser().resolve()
        if not project.exists() or not project.is_dir():
            return {"ok": False, "message": f"invalid project path: {project}"}

        patterns = include_patterns or ["*.md", "*.txt", "*.py", "*.json", "*.yaml", "*.yml", "*.ps1"]
        files: list[Path] = []
        for pattern in patterns:
            files.extend([p for p in project.rglob(pattern) if p.is_file()])

        unique_files = sorted({str(p.resolve()): p for p in files}.values(), key=lambda p: str(p).lower())
        rows: list[dict[str, Any]] = []
        for path in unique_files:
            try:
                data = path.read_bytes()
            except OSError:
                continue
            rel = path.resolve().relative_to(project)
            rows.append(
                {
                    "project_root": str(project),
                    "relative_path": str(rel).replace("\\", "/"),
                    "absolute_path": str(path.resolve()),
                    "size_bytes": len(data),
                    "modified_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )

        target_db = Path(db_path).expanduser().resolve()
        if db_type.lower() == "access" or target_db.suffix.lower() in {".accdb", ".mdb"}:
            return self._index_files_access(rows, target_db)
        return self._index_files_sqlite(rows, target_db)

    def _index_files_sqlite(self, rows: list[dict[str, Any]], db_path: Path) -> dict[str, Any]:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(db_path))
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS archivist_file_index (
                    absolute_path TEXT PRIMARY KEY,
                    project_root TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    modified_utc TEXT NOT NULL,
                    sha256 TEXT NOT NULL
                )
                """
            )
            con.executemany(
                """
                INSERT INTO archivist_file_index (
                    absolute_path, project_root, relative_path, size_bytes, modified_utc, sha256
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(absolute_path) DO UPDATE SET
                    project_root=excluded.project_root,
                    relative_path=excluded.relative_path,
                    size_bytes=excluded.size_bytes,
                    modified_utc=excluded.modified_utc,
                    sha256=excluded.sha256
                """,
                [
                    (
                        r["absolute_path"],
                        r["project_root"],
                        r["relative_path"],
                        r["size_bytes"],
                        r["modified_utc"],
                        r["sha256"],
                    )
                    for r in rows
                ],
            )
            con.commit()
        finally:
            con.close()

        return {"ok": True, "db_type": "sqlite", "db_path": str(db_path), "rows_written": len(rows)}

    def _index_files_access(self, rows: list[dict[str, Any]], db_path: Path) -> dict[str, Any]:
        try:
            import pyodbc  # type: ignore
        except Exception:
            return {
                "ok": False,
                "message": "pyodbc is required for Access indexing. Install pyodbc and Access ODBC driver.",
                "db_path": str(db_path),
            }

        conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_path};"
        try:
            con = pyodbc.connect(conn_str)
        except Exception as ex:
            return {"ok": False, "message": f"failed to open Access DB: {ex}", "db_path": str(db_path)}

        try:
            cur = con.cursor()
            try:
                cur.execute(
                    """
                    CREATE TABLE archivist_file_index (
                        absolute_path TEXT(1024),
                        project_root TEXT(1024),
                        relative_path TEXT(1024),
                        size_bytes DOUBLE,
                        modified_utc TEXT(64),
                        sha256 TEXT(128)
                    )
                    """
                )
                con.commit()
            except Exception:
                pass

            for row in rows:
                cur.execute("DELETE FROM archivist_file_index WHERE absolute_path = ?", row["absolute_path"])
                cur.execute(
                    """
                    INSERT INTO archivist_file_index
                    (absolute_path, project_root, relative_path, size_bytes, modified_utc, sha256)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    row["absolute_path"],
                    row["project_root"],
                    row["relative_path"],
                    row["size_bytes"],
                    row["modified_utc"],
                    row["sha256"],
                )
            con.commit()
        finally:
            con.close()

        return {"ok": True, "db_type": "access", "db_path": str(db_path), "rows_written": len(rows)}

    def _new_archive_dir(self, prefix: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.archives_root / f"{prefix}_{stamp}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def archive_logs(self) -> dict[str, Any]:
        target = self._new_archive_dir("logs")
        events_target = target / "events"
        commands_target = target / "commands"
        events_target.mkdir(exist_ok=True)
        commands_target.mkdir(exist_ok=True)

        event_count = 0
        command_count = 0

        for src in self.bus.events.glob("*.json"):
            shutil.copy2(src, events_target / src.name)
            event_count += 1

        for src in self.bus.commands.glob("*.json"):
            shutil.copy2(src, commands_target / src.name)
            command_count += 1

        return {
            "ok": True,
            "archive_path": str(target),
            "events_archived": event_count,
            "commands_archived": command_count,
        }

    def summarize_events(self, limit: int = 200) -> dict[str, Any]:
        events = self.bus.read_latest_events(limit=limit)
        by_source: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_event: dict[str, int] = {}

        for item in events:
            source = str(item.get("source", "unknown"))
            level = str(item.get("level", "info"))
            event_name = str(item.get("event", "unknown"))
            by_source[source] = by_source.get(source, 0) + 1
            by_level[level] = by_level.get(level, 0) + 1
            by_event[event_name] = by_event.get(event_name, 0) + 1

        summary = {
            "ok": True,
            "events_considered": len(events),
            "by_source": by_source,
            "by_level": by_level,
            "by_event": by_event,
        }

        target_dir = self._new_archive_dir("summary")
        summary_path = target_dir / "event_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summary["summary_path"] = str(summary_path)
        return summary

    def snapshot_state(self) -> dict[str, Any]:
        target = self._new_archive_dir("state")
        copied = 0
        for src in self.bus.state.glob("*.json"):
            shutil.copy2(src, target / src.name)
            copied += 1
        return {"ok": True, "snapshot_path": str(target), "files_copied": copied}

    def handle_command(self, payload: dict[str, Any]) -> None:
        if payload.get("target") != "archivist":
            return

        command = payload.get("command")
        args = payload.get("args") or {}
        if not isinstance(args, dict):
            args = {}

        discovery = run_discovery_handoff(self.bus, "archivist", args, root=self.bus.root)

        if command == "archive_logs":
            result = self.archive_logs()
        elif command == "summarize_events":
            result = self.summarize_events(limit=int(args.get("limit", 200)))
        elif command == "snapshot_state":
            result = self.snapshot_state()
        elif command in {"on_invoke", "run_daily"}:
            result = self.on_invoke()
        elif command == "maintain_runebus_unread":
            result = self.maintain_runebus_unread()
        elif command == "preview_seal":
            result = self.preview_seal()
        elif command == "approve_seal":
            result = self.approve_seal(
                seal_id=str(args.get("seal_id")) if args.get("seal_id") else None,
                commit_message=str(args.get("commit_message")) if args.get("commit_message") else None,
                push=bool(args.get("push", False)),
                init_repo_if_missing=bool(args.get("init_repo_if_missing", True)),
            )
        elif command == "reject_seal":
            result = self.reject_seal(
                seal_id=str(args.get("seal_id")) if args.get("seal_id") else None,
                reason=str(args.get("reason")) if args.get("reason") else None,
            )
        elif command == "add_project":
            result = self.add_onboarded_project(str(args.get("path", "")))
        elif command in {"Archive_index_db", "index_files_db"}:
            include_patterns = args.get("include_patterns")
            if isinstance(include_patterns, str):
                include_patterns = [p.strip() for p in include_patterns.split(",") if p.strip()]
            result = self.Archive_index_db(
                project_path=str(args.get("project_path", Path.cwd())),
                db_path=str(args.get("db_path", self.bus.root / "archives" / "archivist_index.sqlite3")),
                include_patterns=include_patterns if isinstance(include_patterns, list) else None,
                db_type=str(args.get("db_type", "sqlite")),
            )
        elif command == "status_ping":
            result = {"ok": True, "status": "alive"}
        else:
            result = {"ok": False, "message": f"unknown command: {command}"}

        if isinstance(result, dict):
            result.setdefault("discovery", discovery)

        self.bus.emit_event("archivist", f"command:{command}", result)
        self.bus.write_state("archivist", {"service": "archivist", "pid": os.getpid(), "last_command": command, **result})

    def run(self, stop_event: threading.Event | None = None) -> None:
        def on_idle() -> None:
            now = datetime.now()
            current_key = now.strftime("%Y-%m-%d")
            run_time = dt_time.fromisoformat(self.daily_run_time)
            should_run_daily = now.time().hour == run_time.hour and now.time().minute == run_time.minute and self.last_daily_run_key != current_key

            maintenance_cfg = self._runebus_maintenance_config()
            should_run_maintenance = False
            if maintenance_cfg.get("enabled", True):
                interval = timedelta(hours=int(maintenance_cfg.get("interval_hours", 24)))
                now_utc = datetime.now(timezone.utc)
                should_run_maintenance = (
                    self.last_bus_maintenance_at is None
                    or (now_utc - self.last_bus_maintenance_at) >= interval
                )

            if should_run_maintenance:
                maintenance_result = self.maintain_runebus_unread()
                self.last_bus_maintenance_at = datetime.now(timezone.utc)
                self._save_last_bus_maintenance_at(self.last_bus_maintenance_at)
                self.bus.emit_event("archivist", "scheduled:runebus_maintenance", maintenance_result)

            if should_run_daily:
                daily_result = self.on_invoke()
                self.last_daily_run_key = current_key
                self.bus.emit_event("archivist", "scheduled:on_invoke", daily_result)

            self.bus.write_state(
                "archivist",
                {
                    "service": "archivist",
                    "pid": os.getpid(),
                    "status": "idle",
                    "daily_run_time": self.daily_run_time,
                    "last_daily_run": self.last_daily_run_key,
                    "last_runebus_maintenance": self.last_bus_maintenance_at.isoformat() if self.last_bus_maintenance_at else None,
                },
            )

        loop = AgentConsumerLoop(
            bus=self.bus,
            seen_commands=self.seen_commands,
            interval_seconds=self.interval_seconds,
            on_idle=on_idle,
            on_command=self.handle_command,
        )
        loop.run(stop_check=lambda: bool(stop_event is not None and stop_event.is_set()))

    def run_forever(self) -> None:
        self.run(stop_event=None)


def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS Archivist agent")
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--daily-run-time", default="00:45", help="Daily run time in HH:MM local")
    args = parser.parse_args()

    agent = ArchivistAgent(interval_seconds=args.interval, daily_run_time=args.daily_run_time)
    agent.run_forever()


if __name__ == "__main__":
    main()
