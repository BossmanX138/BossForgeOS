# BossGate Presence Trust and Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shared BossGate presence/trust/discovery layer that drives the map, access panel, and transfer history with sparse away-agent identity, grey unrevealed beacons, local unknown-message policy, and a radial interaction menu.

**Architecture:** Add a normalized BossGate presence module on the backend, expose it through the existing model-gateway and Control Hall routes, and teach the BossGate UI surfaces to render the shared trust/discovery states consistently. Keep sealed-agent visibility rules intact by reusing the existing AgentForge sparse-view contract and only enriching BossGate with public presence information plus owner-local policy state.

**Tech Stack:** Python, Flask, existing `ModelGatewayAgent` / BossGate connector stack, inline Control Hall JavaScript in `ui/control_hall.py`, `pytest`

---

## File Structure

- Create: `core/security/bossgate_presence_policy.py`
  - Stores and reads per-node local policy such as `accept_unknown_messages`.
- Create: `core/bossgate/presence_view.py`
  - Normalizes raw gateway, beacon, and transfer-log data into shared `node_presence` / `agent_presence` records.
- Create: `tests/test_bossgate_presence_view.py`
  - Covers reveal rules, trust-color classification, and sparse agent projection.
- Modify: `core/connectors/bossgate_connector.py`
  - Expand normalized beacon payload inputs so the presence layer can classify nodes and agents consistently.
- Modify: `core/agents/model_gateway_agent.py`
  - Publish normalized BossGate map payloads and local policy state.
- Modify: `modules/model_gateway/api_adapter.py`
  - Forward new BossGate presence and policy calls into the gateway.
- Modify: `ui/control_hall.py`
  - Add access-policy route handling, normalize transfer history for the UI, and render the map radial menu plus sparse public cards.
- Modify: `tests/test_model_gateway_agent.py`
  - Verify gateway payload shape and local policy transitions.
- Modify: `tests/test_control_hall_model_routes.py`
  - Verify new route payloads and policy endpoints.

### Task 1: Build the Shared BossGate Presence Normalizer

**Files:**
- Create: `core/bossgate/presence_view.py`
- Modify: `core/connectors/bossgate_connector.py`
- Test: `tests/test_bossgate_presence_view.py`

- [ ] **Step 1: Write the failing presence-view tests**

```python
from core.bossgate.presence_view import (
    classify_presence_color,
    build_agent_presence,
    build_node_presence,
)


def test_build_node_presence_keeps_neutral_beacon_hidden():
    presence = build_node_presence(
        {
            "node_id": "beacon-1",
            "target_type": "unknown",
            "visited": False,
            "trade_linked": False,
        },
        current_node_id="bossforgeos",
    )
    assert presence["presence_kind"] == "node"
    assert presence["discovery_state"] == "unrevealed_beacon"
    assert presence["trust_state"] == "neutral_unaffiliated"
    assert presence["display_name"] == ""


def test_build_agent_presence_only_emits_public_identity():
    presence = build_agent_presence(
        "promethius",
        {
            "current_node": "remote-node",
            "created_by_node": "bossforgeos",
            "agent_card": {"name": "Promethius", "agent_type": "worker", "rank": "specialist"},
            "disclosure_posture": "hidden",
        },
        current_node_id="bossforgeos",
    )
    assert presence["presence_kind"] == "agent"
    assert presence["agent_name"] == "promethius"
    assert "profile" not in presence
    assert presence["inspection_state"] == "origin_forge_required"


def test_classify_presence_color_maps_trade_and_unknown_states():
    assert classify_presence_color("own", "revealed") == "green"
    assert classify_presence_color("trade_linked", "revealed") == "blue"
    assert classify_presence_color("unknown", "revealed") == "red"
    assert classify_presence_color("neutral_unaffiliated", "unrevealed_beacon") == "grey"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bossgate_presence_view.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.bossgate.presence_view'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/bossgate/presence_view.py
from __future__ import annotations

from typing import Any

from core.schemas.agent_capsule import build_public_identity_card


def classify_presence_color(trust_state: str, discovery_state: str) -> str:
    if discovery_state == "unrevealed_beacon":
        return "grey"
    return {
        "own": "green",
        "trade_linked": "blue",
        "unknown": "red",
    }.get(str(trust_state or "").strip().lower(), "grey")


def build_node_presence(raw: dict[str, Any], *, current_node_id: str) -> dict[str, Any]:
    node_id = str(raw.get("node_id", "")).strip() or "unknown-node"
    visited = bool(raw.get("visited", False))
    trade_linked = bool(raw.get("trade_linked", False))
    if node_id == current_node_id:
        trust_state = "own"
    elif trade_linked:
        trust_state = "trade_linked"
    else:
        trust_state = "neutral_unaffiliated" if not visited else "unknown"
    discovery_state = "revealed" if visited or trust_state == "own" else "unrevealed_beacon"
    return {
        "presence_kind": "node",
        "node_id": node_id,
        "node_type": str(raw.get("target_type", "unknown")).strip() or "unknown",
        "visited": visited,
        "trust_state": trust_state,
        "discovery_state": discovery_state,
        "color": classify_presence_color(trust_state, discovery_state),
        "display_name": node_id if discovery_state == "revealed" else "",
        "public_summary": str(raw.get("target_type", "")).strip() if discovery_state == "revealed" else "",
    }


def build_agent_presence(name: str, profile: dict[str, Any], *, current_node_id: str) -> dict[str, Any]:
    model_card = profile.get("agent_card") if isinstance(profile.get("agent_card"), dict) else build_public_identity_card(profile)
    origin_node_id = str(profile.get("created_by_node", "")).strip()
    inspection_state = "origin_forge_available" if origin_node_id and origin_node_id == current_node_id else "origin_forge_required"
    return {
        "presence_kind": "agent",
        "agent_id": str(name or "").strip().lower(),
        "agent_name": str(name or "").strip().lower(),
        "origin_node_id": origin_node_id,
        "current_node_id": str(profile.get("current_node", "")).strip(),
        "trust_state": "own" if origin_node_id == current_node_id else "trade_linked",
        "public_identity_card": build_public_identity_card(profile),
        "model_card": model_card,
        "disclosure_posture": str(profile.get("disclosure_posture", "hidden")).strip().lower() or "hidden",
        "inspection_state": inspection_state,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bossgate_presence_view.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/bossgate/presence_view.py core/connectors/bossgate_connector.py tests/test_bossgate_presence_view.py
git commit -m "feat: add BossGate presence normalizer"
```

### Task 2: Add Local Unknown-Message Policy Storage and Gateway Surface

**Files:**
- Create: `core/security/bossgate_presence_policy.py`
- Modify: `core/agents/model_gateway_agent.py`
- Modify: `modules/model_gateway/api_adapter.py`
- Test: `tests/test_model_gateway_agent.py`

- [ ] **Step 1: Write the failing policy and gateway tests**

```python
def test_bossgate_presence_policy_defaults_unknown_messages_off(tmp_path):
    from core.security.bossgate_presence_policy import BossGatePresencePolicyStore

    store = BossGatePresencePolicyStore(tmp_path / "bossgate_presence_policy.json")
    state = store.read()
    assert state["accept_unknown_messages"] is False


def test_model_gateway_exposes_presence_policy(self) -> None:
    agent = ModelGatewayAgent(interval_seconds=1)
    result = agent.bossgate_presence_policy()
    assert result["ok"] is True
    assert result["policy"]["accept_unknown_messages"] is False


def test_model_gateway_updates_presence_policy(self) -> None:
    agent = ModelGatewayAgent(interval_seconds=1)
    result = agent.set_bossgate_presence_policy(accept_unknown_messages=True)
    assert result["ok"] is True
    assert result["policy"]["accept_unknown_messages"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_model_gateway_agent.py -k "presence_policy" -q`
Expected: FAIL with missing `BossGatePresencePolicyStore` and missing gateway methods

- [ ] **Step 3: Write minimal implementation**

```python
# core/security/bossgate_presence_policy.py
from __future__ import annotations

import json
from pathlib import Path


class BossGatePresencePolicyStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def read(self) -> dict:
        if not self.path.exists():
            return {"accept_unknown_messages": False}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"accept_unknown_messages": False}
        if not isinstance(payload, dict):
            return {"accept_unknown_messages": False}
        return {"accept_unknown_messages": bool(payload.get("accept_unknown_messages", False))}

    def write(self, *, accept_unknown_messages: bool) -> dict:
        payload = {"accept_unknown_messages": bool(accept_unknown_messages)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
```

```python
# core/agents/model_gateway_agent.py
from core.security.bossgate_presence_policy import BossGatePresencePolicyStore

def bossgate_presence_policy(self) -> Dict[str, Any]:
    policy = BossGatePresencePolicyStore(self.bus.state / "bossgate_presence_policy.json").read()
    return {"ok": True, "policy": policy}

def set_bossgate_presence_policy(self, *, accept_unknown_messages: bool) -> Dict[str, Any]:
    policy = BossGatePresencePolicyStore(self.bus.state / "bossgate_presence_policy.json").write(
        accept_unknown_messages=accept_unknown_messages
    )
    return {"ok": True, "policy": policy}
```

```python
# modules/model_gateway/api_adapter.py
def bossgate_presence_policy() -> dict[str, Any]:
    return _gateway().bossgate_presence_policy()

def set_bossgate_presence_policy(*, accept_unknown_messages: bool) -> dict[str, Any]:
    return _gateway().set_bossgate_presence_policy(
        accept_unknown_messages=bool(accept_unknown_messages)
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_model_gateway_agent.py -k "presence_policy" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/security/bossgate_presence_policy.py core/agents/model_gateway_agent.py modules/model_gateway/api_adapter.py tests/test_model_gateway_agent.py
git commit -m "feat: add BossGate local presence policy"
```

### Task 3: Enrich Map and Transfer Payloads with Shared Presence Records

**Files:**
- Modify: `core/agents/model_gateway_agent.py`
- Modify: `ui/control_hall.py`
- Test: `tests/test_model_gateway_agent.py`
- Test: `tests/test_control_hall_model_routes.py`

- [ ] **Step 1: Write the failing map and transfer route tests**

```python
@patch.object(control_hall.model_gateway_api, "bossgate_map_snapshot")
def test_model_travel_map_exposes_presence_collections(self, mock_snapshot) -> None:
    mock_snapshot.return_value = {
        "ok": True,
        "map": {
            "gates": [],
            "travelable_gates": [],
            "agents": {},
            "node_presences": [{"presence_kind": "node", "color": "grey"}],
            "agent_presences": [{"presence_kind": "agent", "color": "green"}],
        },
    }
    res = self.client.get("/api/model/travel/map")
    payload = res.get_json()
    assert "node_presences" in payload["map"]
    assert "agent_presences" in payload["map"]


@patch("ui.control_hall._read_bossgate_transfers")
def test_model_travel_transfers_reads_presence_aware_log(self, mock_read_transfers) -> None:
    mock_read_transfers.return_value = {
        "ok": True,
        "items": [{"status": "posted", "presence_color": "green", "agent_name": "promethius"}],
    }
    res = self.client.get("/api/model/travel/transfers?limit=7")
    payload = res.get_json()
    assert payload["items"][0]["presence_color"] == "green"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_hall_model_routes.py -k "presence" -q`
Expected: FAIL because presence collections are not returned yet

- [ ] **Step 3: Write minimal implementation**

```python
# core/agents/model_gateway_agent.py
from core.bossgate.presence_view import build_agent_presence, build_node_presence

def bossgate_map_snapshot(self, refresh: bool = False, timeout: int = 2) -> Dict[str, Any]:
    raw = self.bossgate_commands.map_snapshot(refresh=bool(refresh), timeout=max(1, int(timeout)))
    if not raw.get("ok"):
        return raw
    map_payload = raw.get("map") if isinstance(raw.get("map"), dict) else {}
    gates = map_payload.get("gates") if isinstance(map_payload.get("gates"), list) else []
    agents = map_payload.get("agents") if isinstance(map_payload.get("agents"), dict) else {}
    node_presences = [
        build_node_presence(gate if isinstance(gate, dict) else {}, current_node_id=self.node_id)
        for gate in gates
    ]
    agent_presences = [
        build_agent_presence(name, profile if isinstance(profile, dict) else {}, current_node_id=self.node_id)
        for name, profile in agents.items()
        if isinstance(profile, dict)
    ]
    map_payload["node_presences"] = node_presences
    map_payload["agent_presences"] = agent_presences
    return {"ok": True, "map": map_payload}
```

```python
# ui/control_hall.py
def _read_bossgate_transfers(limit: int = 20) -> dict:
    path = bus.state / "bossgate_transfers.jsonl"
    ...
    normalized = []
    for item in entries[-lim:]:
        normalized.append(
            {
                **item,
                "presence_color": str(item.get("presence_color", "")).strip() or "grey",
                "agent_name": str(item.get("agent_name", "")).strip(),
                "discovery_state": str(item.get("discovery_state", "")).strip() or "revealed",
            }
        )
    return {"ok": True, "items": normalized}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_hall_model_routes.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/agents/model_gateway_agent.py ui/control_hall.py tests/test_model_gateway_agent.py tests/test_control_hall_model_routes.py
git commit -m "feat: expose BossGate presence payloads"
```

### Task 4: Add BossGate Access Policy Endpoints and Summary Wiring

**Files:**
- Modify: `ui/control_hall.py`
- Modify: `tests/test_control_hall_model_routes.py`
- Test: `tests/test_control_hall_model_routes.py`

- [ ] **Step 1: Write the failing access-policy route tests**

```python
@patch.object(control_hall.model_gateway_api, "bossgate_presence_policy")
def test_bossgate_access_policy_reads_gateway_policy(self, mock_policy) -> None:
    mock_policy.return_value = {"ok": True, "policy": {"accept_unknown_messages": False}}
    res = self.client.get("/api/bossgate/access/policy")
    assert res.status_code == 200
    assert res.get_json()["policy"]["accept_unknown_messages"] is False


@patch.object(control_hall.model_gateway_api, "set_bossgate_presence_policy")
def test_bossgate_access_policy_update_forwards_toggle(self, mock_policy) -> None:
    mock_policy.return_value = {"ok": True, "policy": {"accept_unknown_messages": True}}
    res = self.client.post("/api/bossgate/access/policy", json={"accept_unknown_messages": True})
    assert res.status_code == 200
    mock_policy.assert_called_once_with(accept_unknown_messages=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_hall_model_routes.py -k "access_policy" -q`
Expected: FAIL with 404 or missing adapter method

- [ ] **Step 3: Write minimal implementation**

```python
# ui/control_hall.py
@app.get("/api/bossgate/access/policy")
def bossgate_access_policy():
    return jsonify(model_gateway_api.bossgate_presence_policy())


@app.post("/api/bossgate/access/policy")
def bossgate_access_policy_update():
    payload = request.get_json(force=True, silent=True) or {}
    result = model_gateway_api.set_bossgate_presence_policy(
        accept_unknown_messages=bool(payload.get("accept_unknown_messages", False))
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status
```

```javascript
// ui/control_hall.py inline JS
async function refreshBossGateAccess() {
    const user = bossGateCurrentUser();
    const data = await fetchJsonWithTimeout('/api/bossgate/access/capabilities?user_id=' + encodeURIComponent(user));
    const policy = await fetchJsonWithTimeout('/api/bossgate/access/policy');
    ...
    if (summary) summary.textContent = JSON.stringify({ ...data, policy: policy?.policy || {} }, null, 2);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_hall_model_routes.py -k "access_policy or access_capabilities" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/control_hall.py tests/test_control_hall_model_routes.py
git commit -m "feat: add BossGate access policy routes"
```

### Task 5: Render the Radial BossGate Presence UI

**Files:**
- Modify: `ui/control_hall.py`
- Test: `tests/test_control_hall_model_routes.py`

- [ ] **Step 1: Write the failing UI-shape regression test**

```python
def test_model_travel_map_payload_can_drive_presence_ui(self) -> None:
    payload = {
        "ok": True,
        "map": {
            "node_presences": [
                {"presence_kind": "node", "node_id": "beacon-1", "color": "grey", "discovery_state": "unrevealed_beacon"}
            ],
            "agent_presences": [
                {"presence_kind": "agent", "agent_name": "promethius", "color": "green", "inspection_state": "origin_forge_required"}
            ],
        },
    }
    assert payload["map"]["node_presences"][0]["color"] == "grey"
    assert payload["map"]["agent_presences"][0]["agent_name"] == "promethius"
```

- [ ] **Step 2: Run test to verify the current UI lacks the required behavior**

Run: `python -m pytest tests/test_control_hall_model_routes.py -q`
Expected: PASS on routes but manual gap remains: no radial menu, no grey-beacon card, no shared public card

- [ ] **Step 3: Write minimal implementation**

```javascript
// ui/control_hall.py inline JS
function renderBossGatePresenceCard(presence) {
    if (!presence || typeof presence !== 'object') return '';
    if (presence.presence_kind === 'agent') {
        return `
            <div class="bossgate-presence-card bossgate-presence-card-agent bossgate-color-${escapeHtml(presence.color)}">
                <div class="bossgate-presence-title">${escapeHtml(presence.agent_name || 'unknown agent')}</div>
                <div class="bossgate-presence-subtitle">Model card only while abroad</div>
            </div>
        `;
    }
    if (presence.discovery_state === 'unrevealed_beacon') {
        return `
            <div class="bossgate-presence-card bossgate-presence-card-beacon bossgate-color-grey">
                <div class="bossgate-presence-title">Unrevealed Beacon</div>
                <div class="bossgate-presence-subtitle">Identity withheld until visited</div>
            </div>
        `;
    }
    return `
        <div class="bossgate-presence-card bossgate-presence-card-node bossgate-color-${escapeHtml(presence.color)}">
            <div class="bossgate-presence-title">${escapeHtml(presence.display_name || presence.node_id || 'node')}</div>
            <div class="bossgate-presence-subtitle">${escapeHtml(presence.public_summary || '')}</div>
        </div>
    `;
}

function renderBossGateRadialMenu(presence, x, y) {
    const root = document.getElementById('bossgate_topology_overlay');
    if (!root) return;
    const actions = presence.presence_kind === 'agent'
        ? ['Send Message', 'Recall Home', 'Route Orders', 'View Model Card', 'Hold / Quarantine', 'Trade History']
        : (presence.discovery_state === 'unrevealed_beacon'
            ? ['Visit Beacon', 'Allow Unknown Messaging']
            : ['Send Message', 'Open Node Card', 'Trade History']);
    root.innerHTML = `<div class="bossgate-radial-menu" style="left:${x}px; top:${y}px;">${actions.map((label) => `<button>${escapeHtml(label)}</button>`).join('')}</div>`;
}
```

- [ ] **Step 4: Run verification for UI and routes**

Run: `python -m py_compile ui/control_hall.py`
Expected: no output

Run: `python -m pytest tests/test_control_hall_model_routes.py tests/test_bossgate_presence_view.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/control_hall.py tests/test_control_hall_model_routes.py tests/test_bossgate_presence_view.py
git commit -m "feat: add BossGate radial presence UI"
```

### Task 6: Full Verification and Installer-Safe Regression Pass

**Files:**
- Modify: `tests/test_model_gateway_agent.py`
- Modify: `tests/test_control_hall_model_routes.py`
- Modify: `tests/test_agentforge_service.py`

- [ ] **Step 1: Add final integration assertions**

```python
def test_remote_agent_presence_stays_sparse_in_bossgate_map(self) -> None:
    agent = ModelGatewayAgent(interval_seconds=1)
    snapshot = agent.bossgate_map_snapshot(refresh=False, timeout=2)
    presences = snapshot["map"]["agent_presences"]
    assert all("profile" not in item for item in presences)


def test_control_hall_policy_and_map_routes_can_coexist(self) -> None:
    map_res = self.client.get("/api/model/travel/map")
    policy_res = self.client.get("/api/bossgate/access/policy")
    assert map_res.status_code == 200
    assert policy_res.status_code == 200
```

- [ ] **Step 2: Run the focused suite**

Run: `python -m pytest tests/test_bossgate_presence_view.py tests/test_model_gateway_agent.py tests/test_control_hall_model_routes.py tests/test_agentforge_service.py -q`
Expected: PASS

- [ ] **Step 3: Run syntax verification for the Control Hall UI**

Run: `python -m py_compile ui/control_hall.py`
Expected: no output

- [ ] **Step 4: Inspect final diff for scope discipline**

Run: `git diff -- core/bossgate/presence_view.py core/security/bossgate_presence_policy.py core/agents/model_gateway_agent.py modules/model_gateway/api_adapter.py ui/control_hall.py tests/test_bossgate_presence_view.py tests/test_model_gateway_agent.py tests/test_control_hall_model_routes.py`
Expected: only BossGate presence/trust/discovery changes

- [ ] **Step 5: Commit**

```bash
git add core/bossgate/presence_view.py core/security/bossgate_presence_policy.py core/agents/model_gateway_agent.py modules/model_gateway/api_adapter.py ui/control_hall.py tests/test_bossgate_presence_view.py tests/test_model_gateway_agent.py tests/test_control_hall_model_routes.py tests/test_agentforge_service.py
git commit -m "feat: add BossGate presence trust and discovery UI"
```

## Self-Review

### Spec coverage

- Shared presence model: covered by Task 1 and Task 3
- Local unknown-message policy: covered by Task 2 and Task 4
- Grey unrevealed beacons requiring visit: covered by Task 1 and Task 6
- Sparse away-agent identity only: covered by Task 1, Task 3, and Task 6
- Map radial menu: covered by Task 5
- Access / history consistency: covered by Task 3, Task 4, and Task 5

### Placeholder scan

- No `TBD`, `TODO`, or deferred implementation markers remain in this plan.

### Type consistency

- Shared property names used consistently: `presence_kind`, `trust_state`, `discovery_state`, `color`, `accept_unknown_messages`, `inspection_state`

