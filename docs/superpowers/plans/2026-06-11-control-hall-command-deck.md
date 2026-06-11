# Control Hall Command Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved Control Hall Command Deck with normalized operational data, calm live updates, accessible side-drawer details, and typed Runeforge decision actions.

**Architecture:** Add a focused `modules/control_hall_dashboard` package that normalizes existing agent, task, snapshot, event, and Runeforge state into one dashboard contract. Keep `ui/control_hall.py` as the Flask composition layer, but move Command Deck CSS, browser behavior, and pure update logic into dedicated assets. Resolve only registered decision actions; authority escalations are visible and inspectable but read-only until their subsystem gains a typed resolver.

**Tech Stack:** Python 3, Flask, `unittest`, Rune Bus, vanilla ES modules, CSS Grid, Node's built-in test runner, browser accessibility APIs.

---

## File Map

Create:

- `modules/control_hall_dashboard/__init__.py`
  - exports dashboard aggregation and action-dispatch entry points
- `modules/control_hall_dashboard/service.py`
  - pure normalization, severity ordering, source-health handling, and summary aggregation
- `modules/control_hall_dashboard/decision_registry.py`
  - registered decision adapters and typed action dispatch
- `tests/test_control_hall_dashboard_service.py`
  - pure service and reliability-state tests
- `tests/test_control_hall_dashboard_decisions.py`
  - decision normalization, authorization, and dispatch tests
- `tests/test_control_hall_dashboard_routes.py`
  - Flask endpoint and asset-serving tests
- `assets/ui/control_hall_command_deck.css`
  - approved panel, drawer, reliability, responsive, hover, focus, and reduced-motion styles
- `assets/ui/control_hall_command_deck_state.mjs`
  - pure calm-update state transitions for browser and Node tests
- `assets/ui/control_hall_command_deck.js`
  - DOM rendering, polling, drawer, confirmation, overflow, and focus management
- `tests/js/control_hall_command_deck_state.test.mjs`
  - Node tests for ordering freezes and critical updates

Modify:

- `core/security/bossgate_authorization.py`
  - register the dashboard resolution permission
- `tests/test_bossgate_authorization.py`
  - verify operator inheritance of the permission
- `ui/control_hall.py`
  - serve UI assets, expose dashboard routes, and replace the Agent Status markup
- `.gitignore`
  - ignore local `.superpowers/` visual-companion artifacts

Do not modify unrelated Control Hall views.

### Task 1: Add the Dashboard Resolution Permission

**Files:**
- Modify: `core/security/bossgate_authorization.py`
- Modify: `tests/test_bossgate_authorization.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing authorization test**

Add to `tests/test_bossgate_authorization.py`:

```python
def test_operator_can_resolve_control_hall_decisions(self) -> None:
    self.registry.assign_user_roles(
        "bossforge-owner",
        "operator-1",
        ["operator"],
    )

    self.assertTrue(
        self.registry.has_permission(
            "operator-1",
            "control_hall.decisions.resolve",
        )
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m unittest tests.test_bossgate_authorization.BossGateAuthorizationRegistryTests.test_operator_can_resolve_control_hall_decisions -v
```

Expected: `FAIL` because the permission is not in the catalog or operator role.

- [ ] **Step 3: Add the permission and ignore local mockups**

In `core/security/bossgate_authorization.py`, add:

```python
PERMISSION_CATALOG = {
    "agentforge.profile.view",
    "bossgate.commerce.view",
    "bossgate.discovery.run",
    "bossgate.install",
    "bossgate.key.rotate",
    "bossgate.license.issue",
    "bossgate.license.validate",
    "bossgate.map.view",
    "bossgate.package",
    "bossgate.remote_debug.close",
    "bossgate.remote_debug.open",
    "bossgate.roles.manage",
    "bossgate.support.view",
    "bossgate.transfer",
    "bossgate.usage.report",
    "control_hall.decisions.resolve",
}
```

Add the permission to the seeded `operator` role:

```python
"operator": {
    "includes": ["viewer"],
    "permissions": [
        "bossgate.install",
        "bossgate.package",
        "bossgate.transfer",
        "control_hall.decisions.resolve",
    ],
},
```

Append to `.gitignore`:

```gitignore
# Local Superpowers visual-companion artifacts
.superpowers/
```

- [ ] **Step 4: Run the authorization suite**

Run:

```powershell
python -m unittest tests.test_bossgate_authorization -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add core/security/bossgate_authorization.py tests/test_bossgate_authorization.py .gitignore
git commit -m "feat: authorize Control Hall decision actions"
```

### Task 2: Normalize Dashboard Source Health and Operational State

**Files:**
- Create: `modules/control_hall_dashboard/__init__.py`
- Create: `modules/control_hall_dashboard/service.py`
- Create: `tests/test_control_hall_dashboard_service.py`

- [ ] **Step 1: Write failing source-health and aggregation tests**

Create `tests/test_control_hall_dashboard_service.py`:

```python
import unittest
from datetime import datetime, timezone

from modules.control_hall_dashboard.service import build_dashboard


NOW = datetime(2026, 6, 11, 20, 0, tzinfo=timezone.utc)


class ControlHallDashboardServiceTests(unittest.TestCase):
    def test_builds_summary_and_work_items(self) -> None:
        payload = build_dashboard(
            agent_state={
                "forge": {"display_name": "Forge", "health": "online", "last_seen": "now"},
                "relay": {"display_name": "Relay", "health": "offline", "last_seen": "never"},
            },
            task_state={
                "ok": True,
                "updated_at": NOW.isoformat(),
                "items": [
                    {
                        "id": "forge-1",
                        "agent": "Forge",
                        "task": "Build dashboard",
                        "status": "in_progress",
                        "updated_at": NOW.isoformat(),
                        "note": "",
                    },
                    {
                        "id": "relay-1",
                        "agent": "Relay",
                        "task": "Reconnect",
                        "status": "blocked",
                        "updated_at": NOW.isoformat(),
                        "note": "gateway unavailable",
                    },
                ],
            },
            snapshot={"system": {"cpu_percent": 67, "memory": {"percent": 51}}},
            events=[],
            voice_status={"ok": True, "pending_approval": None},
            capabilities={"permissions": ["control_hall.decisions.resolve"]},
            now=NOW,
        )

        self.assertEqual(payload["summary"]["agents_total"], 2)
        self.assertEqual(payload["summary"]["agents_active"], 1)
        self.assertEqual(payload["summary"]["tasks_running"], 1)
        self.assertEqual(payload["work_items"][0]["state"], "blocked")
        self.assertEqual(payload["system_load"]["cpu_percent"], 67.0)

    def test_partial_failure_marks_only_failed_source(self) -> None:
        payload = build_dashboard(
            agent_state=RuntimeError("agent state unavailable"),
            task_state={"ok": True, "updated_at": NOW.isoformat(), "items": []},
            snapshot={},
            events=[],
            voice_status={"ok": True, "pending_approval": None},
            capabilities={"permissions": []},
            now=NOW,
        )

        self.assertEqual(payload["sources"]["agents"]["state"], "failed")
        self.assertEqual(payload["sources"]["tasks"]["state"], "no_data")
        self.assertEqual(payload["summary"]["agents_total"], 0)

    def test_old_successful_task_feed_is_stale(self) -> None:
        payload = build_dashboard(
            agent_state={},
            task_state={
                "ok": True,
                "updated_at": "2026-06-11T19:50:00+00:00",
                "items": [],
            },
            snapshot={},
            events=[],
            voice_status={"ok": True, "pending_approval": None},
            capabilities={"permissions": []},
            now=NOW,
        )

        self.assertEqual(payload["sources"]["tasks"]["state"], "stale")
        self.assertEqual(payload["sources"]["tasks"]["last_success_at"], "2026-06-11T19:50:00+00:00")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m unittest tests.test_control_hall_dashboard_service -v
```

Expected: import failure because the package does not exist.

- [ ] **Step 3: Implement the pure dashboard service**

Create `modules/control_hall_dashboard/__init__.py`:

```python
from .service import build_dashboard

__all__ = ["build_dashboard"]
```

Create `modules/control_hall_dashboard/service.py` with these public contracts:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SEVERITY_ORDER = {"neutral": 0, "warning": 1, "critical": 2}
STALE_AFTER_SECONDS = 120


def _iso_now(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _source_health(
    value: Any,
    *,
    now: datetime,
    updated_at: Any = "",
    empty: bool = False,
) -> dict[str, Any]:
    checked_at = _iso_now(now)
    if isinstance(value, Exception):
        return {
            "state": "failed",
            "last_success_at": "",
            "checked_at": checked_at,
            "message": str(value) or value.__class__.__name__,
            "retryable": True,
        }
    stamp = _parse_timestamp(updated_at)
    if stamp and (now - stamp).total_seconds() > STALE_AFTER_SECONDS:
        return {
            "state": "stale",
            "last_success_at": str(updated_at),
            "checked_at": checked_at,
            "message": "updates are delayed",
            "retryable": True,
        }
    return {
        "state": "no_data" if empty else "current",
        "last_success_at": str(updated_at or checked_at),
        "checked_at": checked_at,
        "message": "no records available" if empty else "",
        "retryable": False,
    }


def _work_items(task_state: Any) -> list[dict[str, Any]]:
    if not isinstance(task_state, dict):
        return []
    items = task_state.get("items")
    if not isinstance(items, list):
        return []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        state = str(item.get("status", "assigned")).strip().lower()
        normalized.append(
            {
                "id": str(item.get("id", "")).strip(),
                "owner": str(item.get("agent", "unknown-agent")).strip(),
                "title": str(item.get("task", "")).strip(),
                "state": state,
                "progress": None,
                "blocked_reason": str(item.get("note", "")).strip() if state == "blocked" else "",
                "updated_at": str(item.get("updated_at", "")).strip(),
                "source": "agent_tasks",
            }
        )
    priority = {"blocked": 0, "in_progress": 1, "assigned": 2, "done": 3}
    return sorted(normalized, key=lambda item: (priority.get(item["state"], 9), item["id"]))


def build_dashboard(
    *,
    agent_state: Any,
    task_state: Any,
    snapshot: Any,
    events: Any,
    voice_status: Any,
    capabilities: Any,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    agents = agent_state if isinstance(agent_state, dict) else {}
    work_items = _work_items(task_state)
    task_stamp = task_state.get("updated_at", "") if isinstance(task_state, dict) else ""
    system = snapshot.get("system", {}) if isinstance(snapshot, dict) else {}
    memory = system.get("memory", {}) if isinstance(system, dict) else {}

    from .decision_registry import normalize_decisions

    decisions = normalize_decisions(
        events=events,
        voice_status=voice_status,
        capabilities=capabilities,
        now=current,
    )
    highest = max(
        (item["severity"] for item in decisions),
        key=lambda value: SEVERITY_ORDER.get(value, 0),
        default="neutral",
    )
    running = sum(item["state"] == "in_progress" for item in work_items)

    return {
        "generated_at": _iso_now(current),
        "summary": {
            "agents_total": len(agents),
            "agents_active": sum(info.get("health") == "online" for info in agents.values()),
            "tasks_running": running,
            "decisions_pending": len(decisions),
            "risk_count": sum(item["severity"] in {"warning", "critical"} for item in decisions),
            "highest_severity": highest,
        },
        "decisions": decisions,
        "work_items": work_items,
        "system_load": {
            "cpu_percent": float(system.get("cpu_percent", 0) or 0),
            "memory_percent": float(memory.get("percent", 0) or 0),
        },
        "sources": {
            "agents": _source_health(agent_state, now=current, empty=not agents),
            "tasks": _source_health(
                task_state,
                now=current,
                updated_at=task_stamp,
                empty=not work_items,
            ),
            "snapshot": _source_health(snapshot, now=current, empty=not bool(system)),
            "decisions": _source_health(
                voice_status if not isinstance(events, Exception) else events,
                now=current,
                empty=not decisions,
            ),
        },
    }
```

- [ ] **Step 4: Run the service tests**

Run:

```powershell
python -m unittest tests.test_control_hall_dashboard_service -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add modules/control_hall_dashboard tests/test_control_hall_dashboard_service.py
git commit -m "feat: aggregate Control Hall dashboard state"
```

### Task 3: Normalize and Dispatch Registered Decisions

**Files:**
- Create: `modules/control_hall_dashboard/decision_registry.py`
- Create: `tests/test_control_hall_dashboard_decisions.py`
- Modify: `modules/control_hall_dashboard/__init__.py`

- [ ] **Step 1: Write failing decision tests**

Create `tests/test_control_hall_dashboard_decisions.py`:

```python
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from modules.control_hall_dashboard.decision_registry import (
    dispatch_decision_action,
    normalize_decisions,
)


NOW = datetime(2026, 6, 11, 20, 0, tzinfo=timezone.utc)


class ControlHallDashboardDecisionTests(unittest.TestCase):
    def test_runeforge_pending_approval_exposes_registered_actions(self) -> None:
        decisions = normalize_decisions(
            events=[],
            voice_status={
                "ok": True,
                "pending_approval": {
                    "type": "os_action",
                    "created_at": "2026-06-11T19:59:00Z",
                    "action": {"action_type": "close_app", "params": {"name": "notepad"}},
                    "requires_command_code": False,
                },
            },
            capabilities={"permissions": ["control_hall.decisions.resolve"]},
            now=NOW,
        )

        self.assertEqual(decisions[0]["kind"], "runeforge_approval")
        self.assertEqual(
            [action["id"] for action in decisions[0]["allowed_actions"]],
            ["deny", "approve_once"],
        )
        self.assertTrue(decisions[0]["requires_confirmation"])

    def test_authority_escalation_is_visible_but_read_only(self) -> None:
        decisions = normalize_decisions(
            events=[
                {
                    "source": "model_gateway",
                    "event": "authority_resolution",
                    "timestamp": "2026-06-11T19:58:00Z",
                    "data": {
                        "authority_resolution": "escalate",
                        "decision": "authority_escalation",
                        "reason_codes": ["equal_rank_conflict"],
                    },
                }
            ],
            voice_status={"ok": True, "pending_approval": None},
            capabilities={"permissions": ["control_hall.decisions.resolve"]},
            now=NOW,
        )

        self.assertEqual(decisions[0]["kind"], "authority_escalation")
        self.assertEqual(decisions[0]["allowed_actions"], [])

    def test_dispatch_runeforge_approval_emits_existing_command(self) -> None:
        bus = Mock()
        result, status = dispatch_decision_action(
            decision_id="runeforge:os_action:2026-06-11T19:59:00Z",
            action_id="deny",
            payload={
                "acting_user": "operator-1",
                "expected_version": "2026-06-11T19:59:00Z",
                "confirmed": True,
            },
            permissions={"control_hall.decisions.resolve"},
            voice_status={
                "pending_approval": {
                    "type": "os_action",
                    "created_at": "2026-06-11T19:59:00Z",
                }
            },
            bus=bus,
        )

        self.assertEqual(status, 202)
        self.assertTrue(result["ok"])
        bus.emit_command.assert_called_once_with(
            target="runeforge",
            command="respond_pending_approval",
            args={"approved": False, "source": "control_hall"},
            issued_by="control_hall:operator-1",
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m unittest tests.test_control_hall_dashboard_decisions -v
```

Expected: import failure or missing functions.

- [ ] **Step 3: Implement the registry**

Create `modules/control_hall_dashboard/decision_registry.py` with:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

RESOLVE_PERMISSION = "control_hall.decisions.resolve"


def _runeforge_id(pending: dict[str, Any]) -> str:
    return "runeforge:{kind}:{version}".format(
        kind=str(pending.get("type", "approval")).strip(),
        version=str(pending.get("created_at", "unknown")).strip(),
    )


def normalize_decisions(
    *,
    events: Any,
    voice_status: Any,
    capabilities: Any,
    now: datetime,
) -> list[dict[str, Any]]:
    del now
    decisions: list[dict[str, Any]] = []
    permissions = set(capabilities.get("permissions", [])) if isinstance(capabilities, dict) else set()
    pending = voice_status.get("pending_approval") if isinstance(voice_status, dict) else None
    if isinstance(pending, dict) and pending.get("type"):
        can_resolve = RESOLVE_PERMISSION in permissions
        action = pending.get("action") if isinstance(pending.get("action"), dict) else {}
        action_type = str(action.get("action_type", pending.get("type", "action"))).strip()
        allowed = []
        if can_resolve:
            allowed = [
                {"id": "deny", "label": "Deny and close", "requires_confirmation": True},
                {"id": "approve_once", "label": "Approve once", "requires_confirmation": True},
            ]
        decisions.append(
            {
                "id": _runeforge_id(pending),
                "kind": "runeforge_approval",
                "title": f"Approve Runeforge {action_type}",
                "summary": "Runeforge is waiting for operator approval.",
                "severity": "critical" if pending.get("requires_command_code") else "warning",
                "state": "pending",
                "created_at": str(pending.get("created_at", "")).strip(),
                "source": "runeforge",
                "owner": "Runeforge",
                "details": pending,
                "evidence": [],
                "allowed_actions": allowed,
                "requires_confirmation": True,
                "version": str(pending.get("created_at", "")).strip(),
            }
        )

    iterable = events if isinstance(events, list) else []
    for event in iterable:
        if not isinstance(event, dict):
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        if (
            str(event.get("source", "")).strip() != "model_gateway"
            or str(event.get("event", "")).strip() != "authority_resolution"
            or str(data.get("authority_resolution", "")).strip() != "escalate"
        ):
            continue
        stamp = str(event.get("timestamp", "")).strip()
        decisions.append(
            {
                "id": f"authority:{stamp}",
                "kind": "authority_escalation",
                "title": "Authority conflict detected",
                "summary": "Equal-ranked authorities issued conflicting orders.",
                "severity": "critical",
                "state": "pending",
                "created_at": stamp,
                "source": "model_gateway",
                "owner": "Model Gateway",
                "details": data,
                "evidence": data.get("reason_codes", []),
                "allowed_actions": [],
                "requires_confirmation": False,
                "version": stamp,
            }
        )
    severity = {"critical": 0, "warning": 1, "neutral": 2}
    return sorted(decisions, key=lambda item: (severity[item["severity"]], item["created_at"], item["id"]))


def dispatch_decision_action(
    *,
    decision_id: str,
    action_id: str,
    payload: dict[str, Any],
    permissions: set[str],
    voice_status: dict[str, Any],
    bus: Any,
) -> tuple[dict[str, Any], int]:
    if RESOLVE_PERMISSION not in permissions:
        return {"ok": False, "code": "authorization_denied", "message": "decision resolution permission is required"}, 403
    pending = voice_status.get("pending_approval")
    if not isinstance(pending, dict) or _runeforge_id(pending) != decision_id:
        return {"ok": False, "code": "decision_not_pending", "message": "decision is no longer pending"}, 409
    version = str(pending.get("created_at", "")).strip()
    if str(payload.get("expected_version", "")).strip() != version:
        return {"ok": False, "code": "decision_version_conflict", "message": "decision changed; reload before acting"}, 409
    if payload.get("confirmed") is not True:
        return {"ok": False, "code": "confirmation_required", "message": "confirmation is required"}, 400
    if action_id not in {"deny", "approve_once"}:
        return {"ok": False, "code": "unknown_action", "message": "unsupported decision action"}, 404

    args = {
        "approved": action_id == "approve_once",
        "source": "control_hall",
    }
    command_code = str(payload.get("command_code", "")).strip()
    if command_code:
        args["command_code"] = command_code
    acting_user = str(payload.get("acting_user", "")).strip()
    bus.emit_command(
        target="runeforge",
        command="respond_pending_approval",
        args=args,
        issued_by=f"control_hall:{acting_user}",
    )
    return {
        "ok": True,
        "accepted": True,
        "decision_id": decision_id,
        "action_id": action_id,
        "message": "decision action submitted",
    }, 202
```

Update `modules/control_hall_dashboard/__init__.py`:

```python
from .decision_registry import dispatch_decision_action, normalize_decisions
from .service import build_dashboard

__all__ = ["build_dashboard", "dispatch_decision_action", "normalize_decisions"]
```

- [ ] **Step 4: Run decision and service tests**

Run:

```powershell
python -m unittest tests.test_control_hall_dashboard_decisions tests.test_control_hall_dashboard_service -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add modules/control_hall_dashboard tests/test_control_hall_dashboard_decisions.py
git commit -m "feat: register Control Hall decision handlers"
```

### Task 4: Expose Dashboard and Typed Action Routes

**Files:**
- Create: `tests/test_control_hall_dashboard_routes.py`
- Modify: `ui/control_hall.py`

- [ ] **Step 1: Write failing route tests**

Create `tests/test_control_hall_dashboard_routes.py`:

```python
import unittest
from unittest.mock import Mock, patch

from ui import control_hall


class ControlHallDashboardRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = control_hall.app.test_client()

    @patch("ui.control_hall.dashboard_service.build_dashboard")
    def test_dashboard_route_returns_normalized_payload(self, mock_build) -> None:
        mock_build.return_value = {
            "generated_at": "2026-06-11T20:00:00Z",
            "summary": {},
            "decisions": [],
            "work_items": [],
            "system_load": {},
            "sources": {},
        }
        response = self.client.get(
            "/api/control_hall/dashboard?user_id=bossforge-owner"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("summary", response.get_json())
        self.assertTrue(mock_build.called)

    @patch("ui.control_hall.runeforge_voice_service.get_voice_status")
    @patch("ui.control_hall._bossgate_authorization")
    @patch("ui.control_hall.dashboard_decisions.dispatch_decision_action")
    def test_decision_action_forwards_permissions(
        self,
        mock_dispatch,
        mock_registry_factory,
        mock_voice,
    ) -> None:
        registry = Mock()
        registry.effective_permissions.return_value = [
            "control_hall.decisions.resolve"
        ]
        mock_registry_factory.return_value = registry
        mock_voice.return_value = {"pending_approval": {}}
        mock_dispatch.return_value = ({"ok": True, "accepted": True}, 202)

        response = self.client.post(
            "/api/control_hall/decisions/decision-1/actions/deny",
            json={
                "acting_user": "operator-1",
                "expected_version": "v1",
                "confirmed": True,
            },
        )

        self.assertEqual(response.status_code, 202)
        self.assertTrue(mock_dispatch.called)

    def test_command_deck_asset_route_rejects_traversal(self) -> None:
        response = self.client.get("/api/assets/ui/..%2F..%2Fui%2Fcontrol_hall.py")
        self.assertIn(response.status_code, {400, 404})
```

- [ ] **Step 2: Run route tests to verify they fail**

Run:

```powershell
python -m unittest tests.test_control_hall_dashboard_routes -v
```

Expected: failures because routes and imports do not exist.

- [ ] **Step 3: Add imports, safe asset serving, and routes**

In `ui/control_hall.py`, import:

```python
from modules.control_hall_dashboard import decision_registry as dashboard_decisions
from modules.control_hall_dashboard import service as dashboard_service
```

Add a safe UI asset route beside the icon asset route:

```python
@app.get("/api/assets/ui/<path:filename>")
def serve_ui_asset(filename: str):
    safe_name = str(filename or "").replace("\\", "/").strip("/")
    asset_root = (PROJECT_ROOT / "assets" / "ui").resolve()
    candidate = (asset_root / safe_name).resolve()
    try:
        candidate.relative_to(asset_root)
    except Exception:
        return jsonify({"ok": False, "message": "invalid UI asset path"}), 400
    if candidate.suffix.lower() not in {".css", ".js", ".mjs"}:
        return jsonify({"ok": False, "message": "unsupported UI asset extension"}), 400
    if not candidate.is_file():
        return jsonify({"ok": False, "message": "UI asset not found"}), 404
    return send_file(candidate)
```

Add helper wrappers so each source failure is isolated:

```python
def _dashboard_source(callable_obj):
    try:
        return callable_obj()
    except Exception as exc:
        return exc
```

Add the read endpoint:

```python
@app.get("/api/control_hall/dashboard")
def control_hall_dashboard():
    user_id = str(request.args.get("user_id", "")).strip()
    registry = _bossgate_authorization()
    payload = dashboard_service.build_dashboard(
        agent_state=_dashboard_source(read_agent_state),
        task_state=_dashboard_source(load_agent_task_state),
        snapshot=_dashboard_source(snapshot_all),
        events=_dashboard_source(lambda: bus.read_latest_events(limit=200)),
        voice_status=_dashboard_source(
            lambda: runeforge_voice_service.get_voice_status(bus)
        ),
        capabilities=registry.capabilities_for_user(user_id),
    )
    return jsonify(payload)
```

Add the typed action endpoint:

```python
@app.post(
    "/api/control_hall/decisions/<path:decision_id>/actions/<action_id>"
)
def control_hall_decision_action(decision_id: str, action_id: str):
    payload = request.get_json(force=True, silent=True) or {}
    acting_user = str(payload.get("acting_user", "")).strip()
    permissions = set(
        _bossgate_authorization().effective_permissions(acting_user)
    )
    result, status = dashboard_decisions.dispatch_decision_action(
        decision_id=decision_id,
        action_id=action_id,
        payload=payload,
        permissions=permissions,
        voice_status=runeforge_voice_service.get_voice_status(bus),
        bus=bus,
    )
    return jsonify(result), status
```

- [ ] **Step 4: Run route and regression tests**

Run:

```powershell
python -m unittest tests.test_control_hall_dashboard_routes tests.test_control_hall_status_routes tests.test_control_hall_model_routes -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add ui/control_hall.py tests/test_control_hall_dashboard_routes.py
git commit -m "feat: expose Control Hall dashboard API"
```

### Task 5: Add the Command Deck Markup and Approved Visual System

**Files:**
- Create: `assets/ui/control_hall_command_deck.css`
- Modify: `ui/control_hall.py`
- Modify: `tests/test_control_hall_dashboard_routes.py`

- [ ] **Step 1: Write failing page-shell assertions**

Add to `tests/test_control_hall_dashboard_routes.py`:

```python
def test_index_contains_command_deck_shell_and_assets(self) -> None:
    response = self.client.get("/")
    html = response.get_data(as_text=True)

    self.assertIn('id="command_deck"', html)
    self.assertIn('id="command_deck_decisions"', html)
    self.assertIn('id="command_deck_quick_commands"', html)
    self.assertIn('id="command_deck_work_items"', html)
    self.assertIn('id="command_deck_system_load"', html)
    self.assertIn('id="command_deck_drawer"', html)
    self.assertIn("/api/assets/ui/control_hall_command_deck.css", html)
    self.assertIn("/api/assets/ui/control_hall_command_deck.js", html)

    css = self.client.get(
        "/api/assets/ui/control_hall_command_deck.css"
    ).get_data(as_text=True).lower()
    self.assertNotIn("#4da6ff", css)
```

- [ ] **Step 2: Run the assertion to verify it fails**

Run:

```powershell
python -m unittest tests.test_control_hall_dashboard_routes.ControlHallDashboardRouteTests.test_index_contains_command_deck_shell_and_assets -v
```

Expected: `FAIL` because the shell is absent.

- [ ] **Step 3: Replace only the Agent Status panel markup**

In `PAGE`, replace the contents of `section#view_status` with:

```html
<section id="view_status" class="view-panel command-deck-view">
  <div id="command_deck" class="command-deck" aria-busy="true">
    <div class="command-deck-heading">
      <div>
        <div class="command-deck-eyebrow">BossForgeOS / Control Hall</div>
        <h2>Command Deck</h2>
      </div>
      <div id="command_deck_freshness" class="command-deck-freshness">
        Loading operational state...
      </div>
    </div>
    <div id="command_deck_summary" class="command-deck-summary"></div>
    <div class="command-deck-row command-deck-primary-row">
      <section id="command_deck_decisions" class="command-panel" tabindex="-1"></section>
      <section id="command_deck_quick_commands" class="command-panel"></section>
    </div>
    <div class="command-deck-row command-deck-operations-row">
      <section id="command_deck_work_items" class="command-panel"></section>
      <section id="command_deck_system_load" class="command-panel"></section>
    </div>
  </div>
  <div id="command_deck_scrim" class="command-drawer-scrim" hidden></div>
  <aside
    id="command_deck_drawer"
    class="command-drawer"
    role="dialog"
    aria-modal="true"
    aria-labelledby="command_deck_drawer_title"
    hidden
  >
    <div id="command_deck_drawer_body"></div>
  </aside>
  <div id="command_deck_status" class="sr-only" role="status" aria-live="polite"></div>
</section>
```

Add to the document head:

```html
<link rel="stylesheet" href="/api/assets/ui/control_hall_command_deck.css" />
```

Add before `</body>`:

```html
<script type="module" src="/api/assets/ui/control_hall_command_deck.js"></script>
```

Update the legacy `refresh()` fallback so it checks that `#agents` exists before
writing to it. The existing `renderAgents()` function already returns early and
can remain for other consumers.

- [ ] **Step 4: Create the CSS from approved tokens**

Create `assets/ui/control_hall_command_deck.css`. Include these exact core rules,
then add the summary grid, rows, badges, reliability messages, sticky drawer
header/footer, and small-screen layout:

```css
.command-deck {
  --deck-gold: #d4a857;
  --deck-neutral: #2c2d33;
  --deck-warning: #ffb84d;
  --deck-critical: #ff4d4d;
  --deck-hover: #39ff88;
  display: grid;
  gap: 10px;
}

.command-panel {
  --deck-status: var(--deck-neutral);
  min-width: 0;
  border: 1px solid var(--deck-status);
  border-left: 9px solid var(--deck-gold);
  border-radius: 9px;
  background: #141417;
  padding: 14px;
  transition: transform 160ms ease, box-shadow 160ms ease,
    border-color 120ms ease;
}

.command-panel[data-severity="warning"] {
  --deck-status: var(--deck-warning);
}

.command-panel[data-severity="critical"],
.command-panel[data-source-state="failed"] {
  --deck-status: var(--deck-critical);
}

.command-panel:hover {
  border-top-color: var(--deck-hover);
  border-right-color: var(--deck-hover);
  border-bottom-color: var(--deck-hover);
  transform: translateY(-3px) scale(1.018);
  box-shadow: 0 16px 32px rgba(0, 0, 0, .38),
    0 0 18px rgba(57, 255, 136, .16);
  z-index: 2;
}

.command-panel:focus-visible,
.command-item:focus-visible,
.command-drawer button:focus-visible {
  outline: 3px solid #fff3bd;
  outline-offset: 3px;
}

.command-drawer {
  position: fixed;
  inset: 14px 0 14px auto;
  width: min(46vw, 560px);
  overflow-y: auto;
  border: 1px solid #3a3b42;
  border-left: 9px solid var(--deck-gold);
  border-right: 9px solid var(--deck-gold);
  background: #111216;
  box-shadow: -24px 0 60px rgba(0, 0, 0, .55);
  z-index: 100;
  scrollbar-color: var(--deck-gold) #1b1c20;
  scrollbar-width: thin;
}

.command-drawer.has-scrollbar {
  border-right-width: 4px;
}

.command-drawer::-webkit-scrollbar {
  width: 5px;
}

.command-drawer::-webkit-scrollbar-track {
  background: #1b1c20;
}

.command-drawer::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: linear-gradient(180deg, #efc873, var(--deck-gold));
}

@media (max-width: 900px) {
  .command-deck-row {
    grid-template-columns: 1fr;
  }
  .command-drawer {
    width: min(70vw, 560px);
  }
}

@media (max-width: 620px) {
  .command-deck-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .command-drawer {
    inset: 0;
    width: 100vw;
    border-radius: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .command-panel {
    transition: none;
  }
  .command-panel:hover {
    transform: none;
  }
}
```

- [ ] **Step 5: Run shell and asset tests**

Run:

```powershell
python -m unittest tests.test_control_hall_dashboard_routes -v
```

Expected: all tests pass, including `GET` requests for the CSS asset.

- [ ] **Step 6: Commit**

```powershell
git add ui/control_hall.py assets/ui/control_hall_command_deck.css tests/test_control_hall_dashboard_routes.py
git commit -m "feat: add Command Deck visual shell"
```

### Task 6: Implement and Test Calm Update State

**Files:**
- Create: `assets/ui/control_hall_command_deck_state.mjs`
- Create: `tests/js/control_hall_command_deck_state.test.mjs`

- [ ] **Step 1: Write failing Node tests**

Create `tests/js/control_hall_command_deck_state.test.mjs`:

```javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  applyDashboardUpdate,
  createDeckState,
} from "../../assets/ui/control_hall_command_deck_state.mjs";

const item = (id, severity = "neutral") => ({
  id,
  severity,
  title: id,
});

test("freezes routine ordering while interaction is active", () => {
  const state = createDeckState({
    decisions: [item("a"), item("b")],
  });

  const next = applyDashboardUpdate(
    state,
    { decisions: [item("b"), item("a")] },
    { interactionActive: true },
  );

  assert.deepEqual(next.visible.decisions.map((entry) => entry.id), ["a", "b"]);
  assert.deepEqual(next.pending.decisions.map((entry) => entry.id), ["b", "a"]);
});

test("inserts new critical decisions immediately", () => {
  const state = createDeckState({ decisions: [item("a")] });

  const next = applyDashboardUpdate(
    state,
    { decisions: [item("critical", "critical"), item("a")] },
    { interactionActive: true },
  );

  assert.equal(next.visible.decisions[0].id, "critical");
});

test("applies queued ordering when interaction ends", () => {
  const state = {
    ...createDeckState({ decisions: [item("a"), item("b")] }),
    pending: { decisions: [item("b"), item("a")] },
  };

  const next = applyDashboardUpdate(
    state,
    { decisions: [item("b"), item("a")] },
    { interactionActive: false },
  );

  assert.deepEqual(next.visible.decisions.map((entry) => entry.id), ["b", "a"]);
  assert.equal(next.pending, null);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
node --test tests/js/control_hall_command_deck_state.test.mjs
```

Expected: module-not-found failure.

- [ ] **Step 3: Implement the pure update state module**

Create `assets/ui/control_hall_command_deck_state.mjs`:

```javascript
const clone = (value) => structuredClone(value ?? {});

export function createDeckState(payload = {}) {
  return {
    visible: clone(payload),
    pending: null,
  };
}

function mergeCritical(visible = [], incoming = []) {
  const visibleIds = new Set(visible.map((item) => item.id));
  const newCritical = incoming.filter(
    (item) => item.severity === "critical" && !visibleIds.has(item.id),
  );
  return [...newCritical, ...visible];
}

export function applyDashboardUpdate(
  state,
  incoming,
  { interactionActive = false } = {},
) {
  const payload = clone(incoming);
  if (!interactionActive) {
    return { visible: payload, pending: null };
  }
  return {
    visible: {
      ...state.visible,
      ...payload,
      decisions: mergeCritical(
        state.visible?.decisions ?? [],
        payload.decisions ?? [],
      ),
      work_items: state.visible?.work_items ?? [],
    },
    pending: payload,
  };
}
```

- [ ] **Step 4: Run Node tests**

Run:

```powershell
node --test tests/js/control_hall_command_deck_state.test.mjs
```

Expected: three tests pass.

- [ ] **Step 5: Commit**

```powershell
git add assets/ui/control_hall_command_deck_state.mjs tests/js/control_hall_command_deck_state.test.mjs
git commit -m "feat: add calm Command Deck update state"
```

### Task 7: Render the Dashboard and Reliability States

**Files:**
- Create: `assets/ui/control_hall_command_deck.js`
- Modify: `assets/ui/control_hall_command_deck.css`
- Modify: `tests/test_control_hall_dashboard_routes.py`

- [ ] **Step 1: Add failing browser-asset contract tests**

Add to `tests/test_control_hall_dashboard_routes.py`:

```python
def test_command_deck_script_uses_normalized_endpoint(self) -> None:
    response = self.client.get("/api/assets/ui/control_hall_command_deck.js")
    script = response.get_data(as_text=True)

    self.assertEqual(response.status_code, 200)
    self.assertIn("/api/control_hall/dashboard", script)
    self.assertIn("applyDashboardUpdate", script)
    self.assertIn("renderSourceState", script)
    self.assertIn("textContent", script)
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run:

```powershell
python -m unittest tests.test_control_hall_dashboard_routes.ControlHallDashboardRouteTests.test_command_deck_script_uses_normalized_endpoint -v
```

Expected: `404` because the script does not exist.

- [ ] **Step 3: Implement safe DOM rendering**

Create `assets/ui/control_hall_command_deck.js`. Import the pure state module and
use DOM APIs rather than concatenating untrusted HTML:

```javascript
import {
  applyDashboardUpdate,
  createDeckState,
} from "./control_hall_command_deck_state.mjs";

const deck = document.getElementById("command_deck");
if (deck) {
  let deckState = createDeckState();
  let drawerTrigger = null;
  let pollTimer = null;

  const element = (tag, className, text = "") => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };

  const currentUser = () =>
    document.getElementById("bossgate_user")?.value?.trim()
      || "bossforge-owner";

  function renderSourceState(panel, source) {
    panel.dataset.sourceState = source?.state || "failed";
    const state = source?.state || "failed";
    if (state === "current") return;
    const message = element("div", `command-source-state is-${state}`);
    const label = {
      stale: "STALE",
      no_data: "NO DATA",
      failed: "FAILED",
    }[state] || "FAILED";
    message.append(
      element("strong", "", label),
      element("span", "", source?.message || "Source unavailable"),
    );
    panel.append(message);
  }

  function renderDashboard(payload) {
    renderSummary(payload.summary, payload.sources);
    renderDecisions(payload.decisions, payload.sources?.decisions);
    renderQuickCommands();
    renderWorkItems(payload.work_items, payload.sources?.tasks);
    renderSystemLoad(payload.system_load, payload.sources?.snapshot);
    deck.setAttribute("aria-busy", "false");
    document.getElementById("command_deck_freshness").textContent =
      `Updated ${payload.generated_at || "unknown"}`;
  }

  function panelHeading(title, subtitle = "") {
    const wrapper = element("div", "command-panel-heading");
    wrapper.append(element("h3", "", title));
    if (subtitle) wrapper.append(element("p", "muted", subtitle));
    return wrapper;
  }

  function renderSummary(summary = {}, sources = {}) {
    const root = document.getElementById("command_deck_summary");
    const cards = [
      ["Agents", summary.agents_total ?? 0, `${summary.agents_active ?? 0} active`, sources.agents],
      ["Running", summary.tasks_running ?? 0, "active tasks", sources.tasks],
      ["Awaiting", summary.decisions_pending ?? 0, "your decision", sources.decisions],
      ["Risk", summary.risk_count ?? 0, summary.highest_severity || "neutral", sources.decisions],
    ];
    root.replaceChildren(...cards.map(([label, value, note, source]) => {
      const card = element("section", "command-panel command-summary-card");
      card.dataset.sourceState = source?.state || "failed";
      card.append(
        element("div", "command-panel-label", label),
        element("strong", "command-summary-value", String(value)),
        element("span", "muted", note),
      );
      renderSourceState(card, source);
      return card;
    }));
  }

  function renderDecisions(items = [], source) {
    const root = document.getElementById("command_deck_decisions");
    root.replaceChildren(panelHeading("Needs Your Decision"));
    root.dataset.severity = items[0]?.severity || "neutral";
    if (!items.length) {
      root.append(element("p", "muted", "No pending decisions."));
    }
    for (const item of items) {
      const button = element("button", "command-item");
      button.type = "button";
      button.append(
        element("strong", "", item.title || "Untitled decision"),
        element("span", "muted", item.summary || ""),
        element("span", `command-badge is-${item.severity || "neutral"}`, (item.severity || "neutral").toUpperCase()),
      );
      button.addEventListener("click", () => openDrawer(item, button));
      root.append(button);
    }
    renderSourceState(root, source);
  }

  function renderQuickCommands() {
    const root = document.getElementById("command_deck_quick_commands");
    root.replaceChildren(panelHeading("Quick Commands"));
    const commands = [
      ["Create mission", "view_manual"],
      ["Dispatch agent", "view_maker"],
      ["Open diagnostics", "view_diagnostics"],
    ];
    for (const [label, view] of commands) {
      const button = element("button", "command-quick-action", label);
      button.type = "button";
      button.addEventListener("click", () => window.switchView?.(view));
      root.append(button);
    }
    const resolve = element("button", "command-quick-action", "Resolve selected");
    resolve.type = "button";
    resolve.addEventListener("click", () => {
      document.querySelector("#command_deck_decisions .command-item")?.click();
    });
    root.append(resolve);
  }

  function renderWorkItems(items = [], source) {
    const root = document.getElementById("command_deck_work_items");
    root.replaceChildren(panelHeading("Work in Motion"));
    root.dataset.severity = items.some((item) => item.state === "blocked")
      ? "warning"
      : "neutral";
    if (!items.length) root.append(element("p", "muted", "No tracked work."));
    for (const item of items.slice(0, 8)) {
      const button = element("button", "command-item");
      button.type = "button";
      button.append(
        element("strong", "", item.owner || "Unknown owner"),
        element("span", "", item.title || "Untitled work item"),
        element("span", "muted", item.blocked_reason || item.state || "assigned"),
      );
      button.addEventListener("click", () => openDrawer(item, button));
      root.append(button);
    }
    renderSourceState(root, source);
  }

  function renderSystemLoad(load = {}, source) {
    const root = document.getElementById("command_deck_system_load");
    root.replaceChildren(panelHeading("System Load"));
    for (const [label, raw] of [
      ["CPU", load.cpu_percent],
      ["Memory", load.memory_percent],
    ]) {
      const value = Math.max(0, Math.min(100, Number(raw) || 0));
      const row = element("div", "command-load-row");
      const meter = element("progress", "command-load-meter");
      meter.max = 100;
      meter.value = value;
      row.append(
        element("span", "", label),
        meter,
        element("strong", "", `${value.toFixed(1)}%`),
      );
      root.append(row);
    }
    renderSourceState(root, source);
  }

  function renderDashboardFailure(error) {
    const source = {
      state: "failed",
      message: error?.message || "Dashboard request failed",
    };
    for (const id of [
      "command_deck_decisions",
      "command_deck_work_items",
      "command_deck_system_load",
    ]) {
      const panel = document.getElementById(id);
      panel.replaceChildren(panelHeading("Data unavailable"));
      renderSourceState(panel, source);
    }
    deck.setAttribute("aria-busy", "false");
  }

  async function refreshDashboard() {
    const response = await fetch(
      `/api/control_hall/dashboard?user_id=${encodeURIComponent(currentUser())}`,
      { headers: { Accept: "application/json" } },
    );
    if (!response.ok) throw new Error(`dashboard request failed: ${response.status}`);
    const incoming = await response.json();
    const interactionActive =
      Boolean(document.querySelector(".command-panel:hover"))
      || Boolean(document.activeElement?.closest?.(".command-panel"))
      || !document.getElementById("command_deck_drawer").hidden;
    deckState = applyDashboardUpdate(
      deckState,
      incoming,
      { interactionActive },
    );
    renderDashboard(deckState.visible);
  }

  async function poll() {
    try {
      await refreshDashboard();
    } catch (error) {
      renderDashboardFailure(error);
    } finally {
      pollTimer = window.setTimeout(
        poll,
        document.hidden ? 30000 : 5000,
      );
    }
  }

  document.addEventListener("visibilitychange", () => {
    window.clearTimeout(pollTimer);
    poll();
  });

  poll();
}
```

Extend `renderSourceState()` with two buttons when the source is retryable:

```javascript
if (source?.retryable) {
  const actions = element("div", "command-source-actions");
  const retry = element("button", "", "Retry");
  retry.type = "button";
  retry.addEventListener("click", refreshDashboard);
  const diagnostics = element("button", "", "Open diagnostics");
  diagnostics.type = "button";
  diagnostics.addEventListener(
    "click",
    () => window.switchView?.("view_diagnostics"),
  );
  actions.append(retry, diagnostics);
  message.append(actions);
}
```

All server-provided values must reach the page through `textContent`, element
properties, or `setAttribute`; do not interpolate them into HTML strings.

- [ ] **Step 4: Add reliability-state styles**

In `assets/ui/control_hall_command_deck.css`, add:

```css
.command-panel[data-source-state="stale"] {
  --deck-status: var(--deck-warning);
}

.command-source-state {
  display: grid;
  gap: 4px;
  margin-top: 12px;
  padding: 10px;
  border: 1px solid #303138;
  border-radius: 7px;
  background: #101115;
}

.command-source-state strong {
  letter-spacing: .08em;
}

.command-source-state.is-stale strong {
  color: var(--deck-warning);
}

.command-source-state.is-failed strong {
  color: var(--deck-critical);
}
```

- [ ] **Step 5: Run frontend state and route tests**

Run:

```powershell
node --test tests/js/control_hall_command_deck_state.test.mjs
python -m unittest tests.test_control_hall_dashboard_routes -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add assets/ui/control_hall_command_deck.js assets/ui/control_hall_command_deck.css tests/test_control_hall_dashboard_routes.py
git commit -m "feat: render live Command Deck state"
```

### Task 8: Implement the Accessible Drawer and Risk Confirmation

**Files:**
- Modify: `assets/ui/control_hall_command_deck.js`
- Modify: `assets/ui/control_hall_command_deck.css`
- Modify: `tests/test_control_hall_dashboard_routes.py`

- [ ] **Step 1: Add failing drawer contract tests**

Add:

```python
def test_command_deck_script_contains_drawer_accessibility_contract(self) -> None:
    script = self.client.get(
        "/api/assets/ui/control_hall_command_deck.js"
    ).get_data(as_text=True)

    self.assertIn("openDrawer", script)
    self.assertIn("closeDrawer", script)
    self.assertIn("focusableDrawerElements", script)
    self.assertIn("ResizeObserver", script)
    self.assertIn("expected_version", script)
    self.assertIn("confirmation_required", script)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m unittest tests.test_control_hall_dashboard_routes.ControlHallDashboardRouteTests.test_command_deck_script_contains_drawer_accessibility_contract -v
```

Expected: `FAIL` until drawer behavior exists.

- [ ] **Step 3: Add drawer lifecycle and adaptive rail**

In `control_hall_command_deck.js`, implement:

```javascript
const drawer = document.getElementById("command_deck_drawer");
const scrim = document.getElementById("command_deck_scrim");

function focusableDrawerElements() {
  return [...drawer.querySelectorAll(
    'button:not([disabled]), input:not([disabled]), select:not([disabled]), '
      + 'textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
  )];
}

function syncDrawerOverflow() {
  drawer.classList.toggle(
    "has-scrollbar",
    drawer.scrollHeight > drawer.clientHeight + 1,
  );
}

const drawerResizeObserver = new ResizeObserver(syncDrawerOverflow);
drawerResizeObserver.observe(drawer);

function openDrawer(item, trigger) {
  drawerTrigger = trigger;
  renderDrawer(item);
  drawer.hidden = false;
  scrim.hidden = false;
  document.body.classList.add("command-drawer-open");
  syncDrawerOverflow();
  drawer.querySelector("#command_deck_drawer_title")?.focus();
}

function closeDrawer() {
  drawer.hidden = true;
  scrim.hidden = true;
  document.body.classList.remove("command-drawer-open");
  drawerTrigger?.focus();
  drawerTrigger = null;
  if (deckState.pending) {
    deckState = {
      visible: deckState.pending,
      pending: null,
    };
    renderDashboard(deckState.visible);
  }
}
```

Add keyboard handling:

```javascript
drawer.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    event.preventDefault();
    closeDrawer();
    return;
  }
  if (event.key !== "Tab") return;
  const focusable = focusableDrawerElements();
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
});
```

Render the selected item with this concrete structure:

```javascript
function appendDefinitionList(parent, details) {
  const list = element("dl", "command-drawer-details");
  for (const [key, value] of Object.entries(details || {})) {
    if (value && typeof value === "object") continue;
    list.append(
      element("dt", "", key.replaceAll("_", " ")),
      element("dd", "", String(value ?? "")),
    );
  }
  parent.append(list);
}

function renderDrawer(item) {
  const body = document.getElementById("command_deck_drawer_body");
  const header = element("header", "command-drawer-header");
  const title = element(
    "h2",
    "",
    item.title || "Item details",
  );
  title.id = "command_deck_drawer_title";
  title.tabIndex = -1;
  const close = element("button", "command-drawer-close", "Close");
  close.type = "button";
  close.addEventListener("click", closeDrawer);
  header.append(title, close);

  const content = element("div", "command-drawer-content");
  content.append(
    element("div", `command-badge is-${item.severity || "neutral"}`, (item.severity || item.state || "neutral").toUpperCase()),
    element("p", "", item.summary || item.blocked_reason || ""),
  );
  appendDefinitionList(content, item.details || {
    owner: item.owner,
    state: item.state,
    updated_at: item.updated_at,
  });
  if (Array.isArray(item.evidence) && item.evidence.length) {
    const evidence = element("section", "command-drawer-evidence");
    evidence.append(element("h3", "", "Evidence"));
    for (const entry of item.evidence) {
      evidence.append(element("code", "", String(entry)));
    }
    content.append(evidence);
  }

  const footer = element("footer", "command-drawer-actions");
  for (const action of item.allowed_actions || []) {
    const button = element("button", "command-drawer-action", action.label);
    button.type = "button";
    button.addEventListener("click", () => {
      if (action.requires_confirmation) {
        renderActionConfirmation(item, action, footer);
      } else {
        submitDecisionAction(item, action);
      }
    });
    footer.append(button);
  }
  if (!(item.allowed_actions || []).length) {
    footer.append(element("span", "muted", "No direct action is available."));
  }
  body.replaceChildren(header, content, footer);
}

function renderActionConfirmation(decision, action, footer) {
  const prompt = element("div", "command-confirmation");
  prompt.append(
    element("strong", "", `Confirm: ${action.label}`),
    element("p", "", "This action affects a live BossForgeOS operation."),
  );
  let commandCode = null;
  if (
    decision.details?.requires_command_code
    && action.id === "approve_once"
  ) {
    commandCode = element("input", "command-confirmation-code");
    commandCode.type = "password";
    commandCode.required = true;
    commandCode.autocomplete = "off";
    commandCode.placeholder = "Command code";
    prompt.append(commandCode);
  }
  const cancel = element("button", "", "Cancel");
  cancel.type = "button";
  cancel.addEventListener("click", () => renderDrawer(decision));
  const confirm = element("button", "primary", action.label);
  confirm.type = "button";
  confirm.addEventListener("click", () => {
    if (commandCode && !commandCode.value.trim()) {
      commandCode.setCustomValidity("Command code is required");
      commandCode.reportValidity();
      return;
    }
    submitDecisionAction(decision, action, {
      command_code: commandCode?.value.trim() || "",
    });
  });
  prompt.append(cancel, confirm);
  footer.replaceChildren(prompt);
  confirm.focus();
}

function renderDrawerActionError(code, message) {
  const body = document.getElementById("command_deck_drawer_body");
  const alert = element("div", "command-drawer-error");
  alert.setAttribute("role", "alert");
  alert.append(
    element("strong", "", code.replaceAll("_", " ")),
    element("span", "", message || "The action could not be completed."),
  );
  body.prepend(alert);
}
```

- [ ] **Step 4: Add risk-based confirmation and action submission**

For actions with `requires_confirmation`, first replace the action footer with
an inline confirmation block. Submit only after the explicit confirm button:

```javascript
async function submitDecisionAction(decision, action, form = {}) {
  const response = await fetch(
    `/api/control_hall/decisions/${encodeURIComponent(decision.id)}`
      + `/actions/${encodeURIComponent(action.id)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        acting_user: currentUser(),
        expected_version: decision.version,
        confirmed: true,
        ...form,
      }),
    },
  );
  const result = await response.json();
  if (!response.ok) {
    renderDrawerActionError(result.code || "action_failed", result.message);
    if (result.code === "decision_version_conflict") {
      await refreshDashboard();
    }
    return;
  }
  document.getElementById("command_deck_status").textContent = result.message;
  await refreshDashboard();
}
```

If the pending Runeforge decision states `requires_command_code`, include a
required command-code input before approval. Denial does not require the code.

- [ ] **Step 5: Run contract and state tests**

Run:

```powershell
python -m unittest tests.test_control_hall_dashboard_routes -v
node --test tests/js/control_hall_command_deck_state.test.mjs
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add assets/ui/control_hall_command_deck.js assets/ui/control_hall_command_deck.css tests/test_control_hall_dashboard_routes.py
git commit -m "feat: add accessible Command Deck drawer"
```

### Task 9: Complete Regression and Browser Verification

**Files:**
- Modify if required by findings:
  - `assets/ui/control_hall_command_deck.css`
  - `assets/ui/control_hall_command_deck.js`
  - `modules/control_hall_dashboard/service.py`
  - `modules/control_hall_dashboard/decision_registry.py`
  - relevant focused tests

- [ ] **Step 1: Run focused Python tests**

Run:

```powershell
python -m unittest `
  tests.test_control_hall_dashboard_service `
  tests.test_control_hall_dashboard_decisions `
  tests.test_control_hall_dashboard_routes `
  tests.test_control_hall_status_routes `
  tests.test_control_hall_ops_routes `
  tests.test_control_hall_model_routes -v
```

Expected: all tests pass.

- [ ] **Step 2: Run the browser-state tests**

Run:

```powershell
node --test tests/js/control_hall_command_deck_state.test.mjs
```

Expected: all tests pass.

- [ ] **Step 3: Run the full repository test suite**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: all tests pass. If unrelated environment-dependent tests fail, record
the exact failing test and verify that the focused suites remain green.

- [ ] **Step 4: Start the Control Hall**

Run:

```powershell
python ui/control_hall.py
```

Expected: Flask starts and exposes the local Control Hall URL.

- [ ] **Step 5: Verify with the Browser plugin**

Open the local Control Hall and verify:

1. Agent Status opens as Command Deck.
2. Summary, decisions, Quick Commands, work, and load render.
3. Quick Commands is beside Needs Your Decision.
4. Panels have `9px` gold left rails.
5. Hover bulges without reflow and turns only three thin borders neon green.
6. Warning and critical colors return after hover.
7. Blue is absent from Command Deck status semantics.
8. A decision opens the drawer and the dashboard remains visible.
9. The drawer has a `9px` left rail.
10. With overflow, the right rail is `4px` plus a `5px` gold scrollbar.
11. Without overflow, the right rail is `9px`.
12. `Escape` closes the drawer and restores focus.
13. `Tab` remains trapped inside the open drawer.
14. Confirmation appears inline for warning and critical actions.
15. Stale, no-data, and failed states include text and correct border colors.
16. At medium width, panels stack and the drawer uses 60-70 percent width.
17. At narrow width, the drawer becomes full screen.
18. Reduced-motion emulation disables panel translation and scale.
19. No horizontal page scrollbar appears at 320 CSS pixels.
20. Existing non-dashboard views still open.

- [ ] **Step 6: Run final diff checks**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors and only intentional files changed.

- [ ] **Step 7: Commit verification fixes**

```powershell
git add modules/control_hall_dashboard core/security/bossgate_authorization.py ui/control_hall.py assets/ui tests .gitignore
git commit -m "test: verify Control Hall Command Deck"
```

Skip this commit only if Step 5 required no changes and the worktree is already
clean.
