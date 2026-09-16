# BossForge AI Runner Stage 1 Capsule Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the testable sealed-capsule schema foundation for portable BossForgeOS agents: sparse public identity, encrypted vault layout, sealed RuneForge runtime lineage, immutable rarity, and validated lifecycle states.

**Architecture:** Add one focused `core.schemas.agent_capsule` contract module and make existing schema, registry, AgentForge, and Model Gateway seams consume it incrementally. The capsule manifest is an internal encrypted-package description; its public identity card is deliberately sparse and never exposes the BossGate address or sealed ancestry. This stage defines metadata and redaction policy only: encrypted capsule payload transport, dream execution, memory learning, and portable runner loading remain later stages.

**Tech Stack:** Python 3.11+, standard-library `unittest`, JSON Schema Draft 2020-12, existing BossForgeOS schema registry and Model Gateway modules.

---

## Scope Boundaries

This plan implements Stage 1 from `docs/superpowers/specs/2026-06-02-bossforge-ai-runner-sealed-agent-capsules-design.md`.

Included:
- Capsule schema version and encrypted vault references.
- Sparse public identity card.
- Runtime lineage sealed inside capsule metadata.
- Immutable rarity guard.
- Lifecycle state validation and transition guard.
- Canonical schema integration.
- AgentForge disclosure redaction.
- Model Gateway lightweight-profile bridge.
- Documentation and stage tracker.

Deferred to later plans:
- Portable runner loading and model-weight packaging.
- Private memory vault persistence and relationship learning.
- Dream training, signed checkpoints, rollback, and promotion workflow.
- Skills, tools, and sigil evolution workflows.
- Full BossGate move-only package transfer.

## File Map

- Create `core/schemas/agent_capsule.py`: focused Stage 1 capsule constants, builders, validators, transition guard, rarity guard, and authenticated-view redaction helper.
- Create `tests/test_agent_capsule_schema.py`: contract tests for sparse identity, vault layout, lineage sealing, lifecycle transitions, rarity immutability, and canonical-schema integration.
- Modify `core/schemas/agent_schema.py`: normalize and validate capsule metadata while delegating public-card construction to the focused capsule module.
- Modify `core/schemas/__init__.py`: export the new capsule helpers for registry and service consumers.
- Modify `core/schemas/bosscrafts_agent.schema.json`: describe the new public card, rarity, availability, sealed lineage, and capsule manifest fields.
- Modify `modules/agentforge/service.py`: remove address leakage and redact sealed internals from authenticated non-hidden views.
- Modify `tests/test_agentforge_service.py`: lock the disclosure boundary.
- Modify `core/agents/model_gateway_agent.py`: add Stage 1 capsule metadata to lightweight traveling profiles.
- Modify `tests/test_model_gateway_agent.py`: prove new lightweight profiles carry sealed capsule metadata.
- Create `docs/bossforge_ai_runner_todo.md`: stage tracker with Stage 1 evidence lines and later stages left open.
- Modify `docs/AgentForge_readme.md`: document the Stage 1 policy and increment policy version.
- Modify `docs/agentforge_requirements.md`: correct the canonical requirements link.
- Modify `docs/agentmaker_requirements.md`: correct the canonical requirements link.
- Modify `docs/agents_bossgate_agentforge_schema_guide.txt`: add the sealed-capsule foundation and current implementation boundary.

### Task 1: Add The Focused Capsule Contract

**Files:**
- Create: `core/schemas/agent_capsule.py`
- Create: `tests/test_agent_capsule_schema.py`

- [ ] **Step 1: Write failing capsule-contract tests**

Create `tests/test_agent_capsule_schema.py`:

```python
import unittest

from core.schemas.agent_capsule import (
    CAPSULE_LIFECYCLE_STATES,
    CAPSULE_VAULT_NAMES,
    assert_rarity_unchanged,
    build_authenticated_profile_view,
    build_capsule_manifest,
    build_public_identity_card,
    transition_lifecycle,
    validate_capsule_manifest,
)


class AgentCapsuleSchemaTests(unittest.TestCase):
    def _profile(self) -> dict:
        return {
            "id": "wayfinder",
            "name": "Wayfinder",
            "agent_class": "prime",
            "agent_type": "ranger",
            "rank": "captain",
            "rarity": "rare",
            "availability": "idle",
            "secure_address": "amber-slate-river-gate-north-star-ember",
            "skills": ["bossgate_travel_control"],
            "sigils": ["sigil_transporter"],
            "runtime_lineage": {
                "ancestor_id": "runeforge",
                "gifted_template_version": "gifted-runtime-v1",
                "sealed": True,
            },
        }

    def test_public_identity_card_is_sparse_and_address_free(self) -> None:
        card = build_public_identity_card(self._profile())
        self.assertEqual(
            card,
            {
                "name": "Wayfinder",
                "public_id": "wayfinder",
                "agent_class": "prime",
                "agent_type": "ranger",
                "rank": "captain",
                "rarity": "rare",
                "availability": "idle",
            },
        )
        self.assertNotIn("secure_address", card)
        self.assertNotIn("runtime_lineage", card)
        self.assertNotIn("skills", card)
        self.assertNotIn("sigils", card)

    def test_capsule_manifest_contains_only_encrypted_vault_descriptors(self) -> None:
        manifest = build_capsule_manifest(self._profile())
        self.assertEqual(set(manifest["vaults"]), set(CAPSULE_VAULT_NAMES))
        self.assertTrue(all(vault["encrypted"] is True for vault in manifest["vaults"].values()))
        self.assertEqual(manifest["runtime_lineage"]["ancestor_id"], "runeforge")
        self.assertTrue(manifest["runtime_lineage"]["sealed"])
        validate_capsule_manifest(manifest)

    def test_invalid_lifecycle_transition_is_rejected(self) -> None:
        self.assertIn("sealed", CAPSULE_LIFECYCLE_STATES)
        self.assertEqual(transition_lifecycle("sealed", "installed"), "installed")
        with self.assertRaisesRegex(ValueError, "invalid capsule lifecycle transition"):
            transition_lifecycle("sealed", "dreaming")

    def test_rarity_cannot_change_after_creation(self) -> None:
        assert_rarity_unchanged({"rarity": "rare"}, {"rarity": "rare"})
        with self.assertRaisesRegex(ValueError, "agent rarity is immutable"):
            assert_rarity_unchanged({"rarity": "rare"}, {"rarity": "legendary"})

    def test_authenticated_view_redacts_address_lineage_and_capsule(self) -> None:
        profile = self._profile()
        profile["gate_file"] = "state/agent_gates/wayfinder.bossgate"
        profile["capsule"] = build_capsule_manifest(profile)
        view = build_authenticated_profile_view(profile)
        self.assertNotIn("secure_address", view)
        self.assertNotIn("gate_file", view)
        self.assertNotIn("runtime_lineage", view)
        self.assertNotIn("capsule", view)
        self.assertEqual(view["skills"], ["bossgate_travel_control"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the capsule tests and verify the import fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_capsule_schema -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.schemas.agent_capsule'`.

- [ ] **Step 3: Implement the capsule contract**

Create `core/schemas/agent_capsule.py`:

```python
from __future__ import annotations

from copy import deepcopy
from typing import Any


CAPSULE_SCHEMA_VERSION = "1.0"
DEFAULT_RARITY = "common"
DEFAULT_AVAILABILITY = "available"
CAPSULE_VAULT_NAMES = (
    "identity",
    "runner",
    "model",
    "memory",
    "capability",
    "dream",
    "bossgate",
)
CAPSULE_LIFECYCLE_STATES = (
    "sealed",
    "installed",
    "waking",
    "idle",
    "active",
    "travel_pending",
    "traveling",
    "dream_eligible",
    "dreaming",
    "dream_validating",
    "rollback",
    "offline",
    "dead",
    "retired",
)
_LIFECYCLE_TRANSITIONS = {
    "sealed": {"installed"},
    "installed": {"waking", "offline"},
    "waking": {"idle", "offline"},
    "idle": {"active", "dream_eligible", "travel_pending", "offline", "dead", "retired"},
    "active": {"idle", "offline", "dead"},
    "travel_pending": {"traveling", "idle", "offline"},
    "traveling": {"installed", "offline"},
    "dream_eligible": {"dreaming", "idle", "offline"},
    "dreaming": {"dream_validating", "rollback", "offline"},
    "dream_validating": {"idle", "rollback", "offline"},
    "rollback": {"idle", "offline"},
    "offline": {"waking", "dead", "retired"},
    "dead": {"retired"},
    "retired": set(),
}
_SEALED_PROFILE_VIEW_FIELDS = {
    "secure_address",
    "gate_file",
    "runtime_lineage",
    "capsule",
    "private_model",
    "memory_vault",
    "capability_vault",
    "dream_vault",
    "bossgate_vault",
}


def _text(value: Any, default: str = "") -> str:
    return str(value or "").strip() or default


def normalize_rarity(value: Any) -> str:
    return _text(value, DEFAULT_RARITY).lower()


def normalize_availability(value: Any) -> str:
    return _text(value, DEFAULT_AVAILABILITY).lower()


def normalize_lifecycle_state(value: Any) -> str:
    state = _text(value, "sealed").lower()
    if state not in CAPSULE_LIFECYCLE_STATES:
        raise ValueError(f"invalid capsule lifecycle state: {state}")
    return state


def build_public_identity_card(profile: dict[str, Any]) -> dict[str, str]:
    public_id = _text(profile.get("public_id"), _text(profile.get("id")))
    return {
        "name": _text(profile.get("name")),
        "public_id": public_id,
        "agent_class": _text(profile.get("agent_class"), "normalized").lower(),
        "agent_type": _text(profile.get("agent_type"), "worker").lower(),
        "rank": _text(profile.get("rank"), "cadet").lower(),
        "rarity": normalize_rarity(profile.get("rarity")),
        "availability": normalize_availability(profile.get("availability")),
    }


def build_runtime_lineage(profile: dict[str, Any]) -> dict[str, Any]:
    raw = profile.get("runtime_lineage")
    lineage = dict(raw) if isinstance(raw, dict) else {}
    agent_id = _text(profile.get("id")).lower()
    default_ancestor = "" if agent_id == "runeforge" else "runeforge"
    return {
        "ancestor_id": _text(lineage.get("ancestor_id"), default_ancestor).lower(),
        "gifted_template_version": _text(lineage.get("gifted_template_version"), "gifted-runtime-v1"),
        "sealed": True,
    }


def build_capsule_manifest(profile: dict[str, Any]) -> dict[str, Any]:
    vault_refs = profile.get("vault_refs")
    refs = dict(vault_refs) if isinstance(vault_refs, dict) else {}
    return {
        "schema_version": CAPSULE_SCHEMA_VERSION,
        "agent_id": _text(profile.get("id") or profile.get("name")).lower(),
        "public_identity_card": build_public_identity_card(profile),
        "runtime_lineage": build_runtime_lineage(profile),
        "lifecycle_state": normalize_lifecycle_state(profile.get("lifecycle_state")),
        "vaults": {
            name: {"encrypted": True, "ciphertext_ref": _text(refs.get(name))}
            for name in CAPSULE_VAULT_NAMES
        },
    }


def validate_capsule_manifest(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("capsule manifest must be an object")
    if _text(manifest.get("schema_version")) != CAPSULE_SCHEMA_VERSION:
        raise ValueError(f"capsule schema_version must be {CAPSULE_SCHEMA_VERSION}")
    if not _text(manifest.get("agent_id")):
        raise ValueError("capsule agent_id is required")
    card = manifest.get("public_identity_card")
    if not isinstance(card, dict) or set(card) != {
        "name", "public_id", "agent_class", "agent_type", "rank", "rarity", "availability"
    }:
        raise ValueError("capsule public_identity_card must use the sparse public contract")
    lineage = manifest.get("runtime_lineage")
    if not isinstance(lineage, dict) or lineage.get("sealed") is not True:
        raise ValueError("capsule runtime_lineage must be sealed")
    normalize_lifecycle_state(manifest.get("lifecycle_state"))
    vaults = manifest.get("vaults")
    if not isinstance(vaults, dict) or set(vaults) != set(CAPSULE_VAULT_NAMES):
        raise ValueError("capsule vaults must define the complete encrypted vault layout")
    for name in CAPSULE_VAULT_NAMES:
        vault = vaults.get(name)
        if not isinstance(vault, dict) or vault.get("encrypted") is not True:
            raise ValueError(f"capsule vault '{name}' must be encrypted")
        if not isinstance(vault.get("ciphertext_ref"), str):
            raise ValueError(f"capsule vault '{name}' ciphertext_ref must be a string")


def transition_lifecycle(current: Any, target: Any) -> str:
    current_state = normalize_lifecycle_state(current)
    target_state = normalize_lifecycle_state(target)
    if target_state not in _LIFECYCLE_TRANSITIONS[current_state]:
        raise ValueError(f"invalid capsule lifecycle transition: {current_state} -> {target_state}")
    return target_state


def assert_rarity_unchanged(previous: dict[str, Any], candidate: dict[str, Any]) -> None:
    if normalize_rarity(previous.get("rarity")) != normalize_rarity(candidate.get("rarity")):
        raise ValueError("agent rarity is immutable after creation")


def build_authenticated_profile_view(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in profile.items()
        if key not in _SEALED_PROFILE_VIEW_FIELDS
    }
```

- [ ] **Step 4: Run the capsule tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_capsule_schema -v
```

Expected: `Ran 5 tests` and `OK`.

- [ ] **Step 5: Commit the focused capsule contract**

```powershell
git add core/schemas/agent_capsule.py tests/test_agent_capsule_schema.py
git commit -m "feat: add sealed agent capsule contract"
```

### Task 2: Integrate Capsules Into The Canonical Agent Schema

**Files:**
- Modify: `core/schemas/agent_schema.py`
- Modify: `core/schemas/__init__.py`
- Modify: `core/schemas/bosscrafts_agent.schema.json`
- Modify: `tests/test_agent_capsule_schema.py`

- [ ] **Step 1: Add failing canonical-schema integration tests**

Add these imports and methods to `tests/test_agent_capsule_schema.py`:

```python
from core.schemas.agent_schema import normalize_agent_profile, validate_agent_profile


    def test_canonical_profile_normalizes_capsule_fields_and_sparse_card(self) -> None:
        profile = normalize_agent_profile("scribe", {"name": "Scribe"})
        self.assertEqual(profile["public_id"], "scribe")
        self.assertEqual(profile["rarity"], "common")
        self.assertEqual(profile["availability"], "available")
        self.assertEqual(profile["runtime_lineage"]["ancestor_id"], "runeforge")
        self.assertTrue(profile["runtime_lineage"]["sealed"])
        self.assertEqual(profile["capsule"]["agent_id"], "scribe")
        self.assertEqual(
            set(profile["agent_card"]),
            {"name", "public_id", "agent_class", "agent_type", "rank", "rarity", "availability"},
        )
        validate_agent_profile(profile)

    def test_runeforge_is_origin_not_its_own_descendant(self) -> None:
        profile = normalize_agent_profile("runeforge", {"name": "RuneForge"})
        self.assertEqual(profile["runtime_lineage"]["ancestor_id"], "")
        validate_agent_profile(profile)
```

- [ ] **Step 2: Run the integration tests and verify the new assertions fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_capsule_schema -v
```

Expected: FAIL because canonical normalized profiles do not contain `public_id`, `rarity`, `runtime_lineage`, or `capsule`.

- [ ] **Step 3: Delegate public-card construction and normalize capsule metadata**

In `core/schemas/agent_schema.py`, add:

```python
from core.schemas.agent_capsule import (
    build_capsule_manifest,
    build_public_identity_card,
    build_runtime_lineage,
    normalize_availability,
    normalize_rarity,
    validate_capsule_manifest,
)
```

Replace `to_agent_card` with:

```python
def to_agent_card(profile: dict[str, Any]) -> dict[str, Any]:
    return build_public_identity_card(profile)
```

Immediately after `out["rank"]` is normalized in `normalize_agent_profile`, add:

```python
    out["public_id"] = str(raw.get("public_id", normalized_id)).strip() or normalized_id
    out["rarity"] = normalize_rarity(raw.get("rarity"))
    out["availability"] = normalize_availability(raw.get("availability"))
```

Immediately before `out["agent_card"] = to_agent_card(out)`, add:

```python
    out["runtime_lineage"] = build_runtime_lineage(out)
    out["capsule"] = build_capsule_manifest(out)
```

In `validate_agent_profile`, extend the object-field loop with `"runtime_lineage"` and `"capsule"`, then replace the existing `agent_card` validation block with:

```python
    agent_card = profile.get("agent_card") if isinstance(profile.get("agent_card"), dict) else {}
    expected_card = build_public_identity_card(profile)
    if agent_card != expected_card:
        raise ValueError("agent profile agent_card must match the sparse public identity contract")
    if str(agent_card.get("public_id", "")).strip() != agent_id:
        raise ValueError("agent profile agent_card.public_id must match profile id")

    runtime_lineage = profile.get("runtime_lineage")
    if not isinstance(runtime_lineage, dict) or runtime_lineage.get("sealed") is not True:
        raise ValueError("agent profile runtime_lineage must be sealed")
    validate_capsule_manifest(profile.get("capsule"))
```

- [ ] **Step 4: Export capsule helpers**

Replace `core/schemas/__init__.py` with:

```python
from .agent_capsule import (
    CAPSULE_LIFECYCLE_STATES,
    CAPSULE_SCHEMA_VERSION,
    CAPSULE_VAULT_NAMES,
    assert_rarity_unchanged,
    build_authenticated_profile_view,
    build_capsule_manifest,
    build_public_identity_card,
    build_runtime_lineage,
    transition_lifecycle,
    validate_capsule_manifest,
)
from .agent_schema import AGENT_SCHEMA_VERSION, get_agent_schema_path, normalize_agent_profile, to_agent_card, validate_agent_profile

__all__ = [
    "AGENT_SCHEMA_VERSION",
    "CAPSULE_LIFECYCLE_STATES",
    "CAPSULE_SCHEMA_VERSION",
    "CAPSULE_VAULT_NAMES",
    "assert_rarity_unchanged",
    "build_authenticated_profile_view",
    "build_capsule_manifest",
    "build_public_identity_card",
    "build_runtime_lineage",
    "get_agent_schema_path",
    "normalize_agent_profile",
    "to_agent_card",
    "transition_lifecycle",
    "validate_agent_profile",
    "validate_capsule_manifest",
]
```

- [ ] **Step 5: Update the JSON Schema contract**

Run this deterministic update script from the repository root:

```powershell
$script = @'
import copy
import json
from pathlib import Path

path = Path("core/schemas/bosscrafts_agent.schema.json")
schema = json.loads(path.read_text(encoding="utf-8"))
props = schema["properties"]

for field in ("public_id", "rarity", "availability", "runtime_lineage", "capsule"):
    if field not in schema["required"]:
        schema["required"].append(field)

class_enum = ["prime", "skilled", "normalized"]
type_enum = ["authority", "controller", "worker", "security", "tester", "ranger"]
rank_enum = ["cadet", "specialist", "lieutenant", "captain", "commander", "general", "admiral"]
public_card = {
    "type": "object",
    "required": ["name", "public_id", "agent_class", "agent_type", "rank", "rarity", "availability"],
    "properties": {
        "name": {"type": "string"},
        "public_id": {"type": "string"},
        "agent_class": {"type": "string", "enum": class_enum},
        "agent_type": {"type": "string", "enum": type_enum},
        "rank": {"type": "string", "enum": rank_enum},
        "rarity": {"type": "string"},
        "availability": {"type": "string"},
    },
    "additionalProperties": False,
}
lineage = {
    "type": "object",
    "required": ["ancestor_id", "gifted_template_version", "sealed"],
    "properties": {
        "ancestor_id": {"type": "string"},
        "gifted_template_version": {"type": "string"},
        "sealed": {"type": "boolean", "const": True},
    },
    "additionalProperties": False,
}
vault_descriptor = {
    "type": "object",
    "required": ["encrypted", "ciphertext_ref"],
    "properties": {
        "encrypted": {"type": "boolean", "const": True},
        "ciphertext_ref": {"type": "string"},
    },
    "additionalProperties": False,
}
vault_names = ["identity", "runner", "model", "memory", "capability", "dream", "bossgate"]
lifecycle_states = [
    "sealed", "installed", "waking", "idle", "active", "travel_pending", "traveling",
    "dream_eligible", "dreaming", "dream_validating", "rollback", "offline", "dead", "retired",
]

props["public_id"] = {"type": "string", "minLength": 1}
props["rarity"] = {"type": "string", "minLength": 1}
props["availability"] = {"type": "string", "minLength": 1}
props["agent_card"] = copy.deepcopy(public_card)
props["runtime_lineage"] = copy.deepcopy(lineage)
props["capsule"] = {
    "type": "object",
    "required": ["schema_version", "agent_id", "public_identity_card", "runtime_lineage", "lifecycle_state", "vaults"],
    "properties": {
        "schema_version": {"type": "string", "const": "1.0"},
        "agent_id": {"type": "string", "minLength": 1},
        "public_identity_card": copy.deepcopy(public_card),
        "runtime_lineage": copy.deepcopy(lineage),
        "lifecycle_state": {"type": "string", "enum": lifecycle_states},
        "vaults": {
            "type": "object",
            "required": vault_names,
            "properties": {name: copy.deepcopy(vault_descriptor) for name in vault_names},
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}

path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
'@
$script | .\.venv\Scripts\python.exe -
```

- [ ] **Step 6: Run canonical-schema tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_capsule_schema -v
```

Expected: `Ran 7 tests` and `OK`.

- [ ] **Step 7: Commit canonical-schema integration**

```powershell
git add core/schemas/agent_schema.py core/schemas/__init__.py core/schemas/bosscrafts_agent.schema.json tests/test_agent_capsule_schema.py
git commit -m "feat: integrate capsules into agent schema"
```

### Task 3: Harden AgentForge Disclosure Views

**Files:**
- Modify: `modules/agentforge/service.py`
- Modify: `tests/test_agentforge_service.py`

- [ ] **Step 1: Replace AgentForge disclosure expectations with failing security tests**

In `tests/test_agentforge_service.py`, replace `test_hidden_agent_view_returns_sealed_summary` with:

```python
    def test_hidden_agent_view_returns_sparse_public_identity_without_address(self) -> None:
        result = service.view_agent_profile("viewer", viewer_id="owner-1", viewer_channel="bossforgeos")
        self.assertTrue(result["ok"])
        self.assertTrue(result["sealed"])
        self.assertNotIn("profile", result)
        self.assertNotIn("secure_address", result)
        self.assertEqual(
            set(result["public_identity_card"]),
            {"name", "public_id", "agent_class", "agent_type", "rank", "rarity", "availability"},
        )
```

Add:

```python
    def test_authenticated_non_hidden_view_still_redacts_gate_and_lineage(self) -> None:
        service.set_agent_disclosure_posture("viewer", "non_hidden")
        result = service.view_agent_profile("viewer", viewer_id="owner-1", viewer_channel="bossforgeos")
        self.assertFalse(result["sealed"])
        self.assertNotIn("secure_address", result["profile"])
        self.assertNotIn("gate_file", result["profile"])
        self.assertNotIn("runtime_lineage", result["profile"])
        self.assertNotIn("capsule", result["profile"])
```

- [ ] **Step 2: Run the AgentForge tests and verify the address-leak test fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agentforge_service -v
```

Expected: FAIL because `_sealed_summary` exposes `secure_address` and the authenticated profile returns sealed fields.

- [ ] **Step 3: Redact both disclosure paths**

Add to `modules/agentforge/service.py`:

```python
from core.schemas.agent_capsule import build_authenticated_profile_view, build_public_identity_card
```

Replace `_sealed_summary` with:

```python
def _sealed_summary(name: str, profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "agent": name,
        "disclosure_posture": str(profile.get("disclosure_posture", "hidden")).strip().lower() or "hidden",
        "sealed": True,
        "public_identity_card": build_public_identity_card(profile),
    }
```

In the authenticated return branch of `view_agent_profile`, replace:

```python
        "profile": dict(profile),
```

with:

```python
        "profile": build_authenticated_profile_view(profile),
```

- [ ] **Step 4: Run AgentForge tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agentforge_service -v
```

Expected: `Ran 4 tests` and `OK`.

- [ ] **Step 5: Commit AgentForge disclosure hardening**

```powershell
git add modules/agentforge/service.py tests/test_agentforge_service.py
git commit -m "fix: seal agent address in AgentForge views"
```

### Task 4: Bridge Model Gateway Lightweight Profiles

**Files:**
- Modify: `core/agents/model_gateway_agent.py`
- Modify: `tests/test_model_gateway_agent.py`

- [ ] **Step 1: Add a failing Model Gateway capsule test**

Add imports to `tests/test_model_gateway_agent.py`:

```python
from core.schemas.agent_capsule import CAPSULE_VAULT_NAMES
```

Add:

```python
    def test_created_agent_carries_stage1_capsule_metadata(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="capsule_runner",
            endpoint="ollama",
            system_prompt="Travel safely.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])
        profile = agent.agent_profiles["capsule_runner"]
        self.assertEqual(profile["public_id"], "capsule_runner")
        self.assertEqual(profile["rarity"], "common")
        self.assertEqual(profile["availability"], "available")
        self.assertEqual(profile["runtime_lineage"]["ancestor_id"], "runeforge")
        self.assertTrue(profile["runtime_lineage"]["sealed"])
        self.assertEqual(profile["capsule"]["lifecycle_state"], "sealed")
        self.assertEqual(set(profile["capsule"]["vaults"]), set(CAPSULE_VAULT_NAMES))
```

- [ ] **Step 2: Run the new Model Gateway test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent.ModelGatewayAgentTests.test_created_agent_carries_stage1_capsule_metadata -v
```

Expected: FAIL because Model Gateway lightweight profiles do not yet contain `public_id`.

- [ ] **Step 3: Normalize Stage 1 metadata in Model Gateway**

Add to `core/agents/model_gateway_agent.py`:

```python
from core.schemas.agent_capsule import (
    build_capsule_manifest,
    build_runtime_lineage,
    normalize_availability,
    normalize_rarity,
)
```

At the end of `_normalize_profile`, immediately before `return normalized`, add:

```python
        normalized["public_id"] = str(normalized.get("public_id", key)).strip() or key
        normalized["rarity"] = normalize_rarity(normalized.get("rarity"))
        normalized["availability"] = normalize_availability(normalized.get("availability"))
        normalized["runtime_lineage"] = build_runtime_lineage({"id": key, **normalized})
        normalized["capsule"] = build_capsule_manifest({"id": key, **normalized})
```

- [ ] **Step 4: Run Model Gateway tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent -v
```

Expected: all `tests.test_model_gateway_agent` tests pass.

- [ ] **Step 5: Commit the lightweight-profile bridge**

```powershell
git add core/agents/model_gateway_agent.py tests/test_model_gateway_agent.py
git commit -m "feat: attach capsule metadata to gateway profiles"
```

### Task 5: Add The AI Runner Tracker And Update Requirements Docs

**Files:**
- Create: `docs/bossforge_ai_runner_todo.md`
- Modify: `docs/AgentForge_readme.md`
- Modify: `docs/agentforge_requirements.md`
- Modify: `docs/agentmaker_requirements.md`
- Modify: `docs/agents_bossgate_agentforge_schema_guide.txt`

- [ ] **Step 1: Create the staged AI runner tracker**

Create `docs/bossforge_ai_runner_todo.md`:

```markdown
# BossForgeOS AI Runner Completion Tracker

This tracker records implementation status for the sealed portable-agent work designed in `docs/superpowers/specs/2026-06-02-bossforge-ai-runner-sealed-agent-capsules-design.md`.

## Stage 1: Capsule Schema And Identity

- [x] Define sparse public identity card without BossGate address.
- [x] Define encrypted identity, runner, model, memory, capability, dream, and BossGate vault descriptors.
- [x] Seal RuneForge gifted-runtime lineage inside capsule metadata.
- [x] Add immutable-rarity guard.
- [x] Add lifecycle state and transition validation.
- [x] Integrate canonical agent schema, AgentForge views, and Model Gateway lightweight profiles.
- [ ] Verification: run the Stage 1 and BossGate regression suites before closing this stage.

## Stage 2: Gifted Portable AI Runner

- [ ] Extract the portable BossForgeOS runner contract from RuneForge-specific provider behavior.
- [ ] Keep RuneForge personalized while recording her gifted runtime as direct ancestor for descendants.
- [ ] Package each agent runtime and complete private model weights independently.

## Stage 3: Private Memory Vault

- [ ] Store encrypted private memory and relationship records inside the capsule.
- [ ] Add memory-first learning inputs without exposing private records through public views.

## Stage 4: Dreams And Signed Checkpoints

- [ ] Run policy-controlled dream training only while agents are inactive and safe.
- [ ] Validate signed checkpoints before activation.
- [ ] Roll back rejected dream checkpoints safely.

## Stage 5: Capability Evolution

- [ ] Add empty-slot and class/type constraints for skill learning between consenting agents.
- [ ] Add Forge, dead-agent recovery, and consenting live-agent trade rules for tools.
- [ ] Add signed-lineage sigil evolution while preserving explicit promotion-only rank and immutable rarity.

## Stage 6: Full Capsule BossGate Movement

- [ ] Move the complete encrypted capsule rather than copying it.
- [ ] Restrict address enumeration to Prime BossGates at BossForgeOS, A.S.S., and Bridgebase Alpha.
- [ ] Prove secure return travel using the agent seven-word identifier.
```

- [ ] **Step 2: Update canonical AgentForge requirements**

In `docs/AgentForge_readme.md`:

1. Change current policy version from `v1.11.0` to `v1.12.0`.
2. Add a `## Sealed Agent Capsule Foundation` section before `## Policy Versioning`.
3. Use this text:

```markdown
## Sealed Agent Capsule Foundation

- Each agent carries a sealed capsule manifest with encrypted vault descriptors for identity, runner, model, memory, capability, dreams, and BossGate material.
- The public identity card is intentionally sparse: `name`, `public_id`, `agent_class`, `agent_type`, `rank`, `rarity`, and `availability`.
- The public card never reveals the BossGate seven-word address, runtime ancestry, skills, sigils, tools, private runner details, model material, memory, dream state, or travel state.
- RuneForge remains the runtime origin. Descendant capsules seal the gifted runtime template version and direct `runeforge` ancestry inside private capsule metadata.
- Rarity is assigned at creation and immutable. Rank remains explicit-promotion only.
- Capsule lifecycle metadata uses validated states and transitions. Full encrypted movement, dream training, and capability evolution are staged follow-up work.
```

4. Add:

```markdown
- v1.12.0 (2026-06-02): added the Stage 1 sealed portable-agent capsule foundation: sparse public identity, encrypted vault descriptors, sealed RuneForge runtime lineage, immutable rarity guard, lifecycle metadata, and address-safe AgentForge views.
- Impacted modules for v1.12.0: `core/schemas/agent_capsule.py`, `core/schemas/agent_schema.py`, `core/schemas/bosscrafts_agent.schema.json`, `core/agents/model_gateway_agent.py`, `modules/agentforge/service.py`
```

- [ ] **Step 3: Correct legacy alias links**

In both `docs/agentforge_requirements.md` and `docs/agentmaker_requirements.md`, replace:

```markdown
(docs/AgentForge_readme.md)
```

with:

```markdown
(./AgentForge_readme.md)
```

- [ ] **Step 4: Add current-reality capsule notes to the unified guide**

Append this section to `docs/agents_bossgate_agentforge_schema_guide.txt`:

```text
13) Sealed Portable-Agent Capsule Foundation (Implemented Stage 1)

Stage 1 establishes the metadata contract for the BossForgeOS AI runner capsule.

Implemented:
- sparse public identity card: name, public_id, agent_class, agent_type, rank, rarity, availability
- address-safe public and authenticated AgentForge profile views
- encrypted descriptor layout for identity, runner, model, memory, capability, dream, and BossGate vaults
- sealed RuneForge gifted-runtime lineage metadata
- immutable rarity guard
- validated capsule lifecycle states and transitions
- Model Gateway lightweight-profile capsule metadata

Not yet implemented:
- portable runtime loading and full model-weight packaging
- private relationship-memory persistence and learning
- dream training, signed checkpoint activation, and rollback
- skill, tool, and sigil evolution workflows
- full move-only capsule travel over BossGate
```

- [ ] **Step 5: Verify documentation contains the Stage 1 boundary**

Run:

```powershell
rg -n "v1\.12\.0|Sealed Agent Capsule Foundation|Stage 2: Gifted Portable AI Runner|move-only capsule travel" docs
```

Expected: matches in `docs/AgentForge_readme.md`, `docs/bossforge_ai_runner_todo.md`, and `docs/agents_bossgate_agentforge_schema_guide.txt`.

- [ ] **Step 6: Commit documentation**

```powershell
git add docs/AgentForge_readme.md docs/agentforge_requirements.md docs/agentmaker_requirements.md docs/agents_bossgate_agentforge_schema_guide.txt docs/bossforge_ai_runner_todo.md
git commit -m "docs: track sealed AI runner capsule stages"
```

### Task 6: Run Regression Verification

**Files:**
- Verify: `core/schemas/agent_capsule.py`
- Verify: `core/schemas/agent_schema.py`
- Verify: `modules/agentforge/service.py`
- Verify: `core/agents/model_gateway_agent.py`
- Verify: `docs/bossforge_ai_runner_todo.md`

- [ ] **Step 1: Compile modified Python modules**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile core/schemas/agent_capsule.py core/schemas/agent_schema.py modules/agentforge/service.py core/agents/model_gateway_agent.py
```

Expected: exit code `0` with no output.

- [ ] **Step 2: Run focused Stage 1 tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_capsule_schema tests.test_agentforge_service tests.test_model_gateway_agent -v
```

Expected: all capsule, AgentForge, and Model Gateway tests pass.

- [ ] **Step 3: Run BossGate regression tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bossgate_agent tests.test_bossgate_authorization tests.test_bossgate_connector -v
```

Expected: all BossGate command, authorization, encryption, beacon, and connector tests pass.

- [ ] **Step 4: Check whitespace**

Run:

```powershell
git diff --check
```

Expected: exit code `0` with no whitespace errors introduced by this stage.

- [ ] **Step 5: Record verification evidence**

In `docs/bossforge_ai_runner_todo.md`, replace the unchecked Stage 1 verification line with:

```markdown
- [x] Verification: passed on 2026-06-02 with `python -m unittest tests.test_agent_capsule_schema tests.test_agentforge_service tests.test_model_gateway_agent -v` and BossGate regression suite.
```

- [ ] **Step 6: Commit verification evidence**

```powershell
git add docs/bossforge_ai_runner_todo.md
git commit -m "docs: record AI runner stage1 verification"
```
