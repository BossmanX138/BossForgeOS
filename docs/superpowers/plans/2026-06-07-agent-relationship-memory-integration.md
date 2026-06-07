# Agent Relationship Memory Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut active agent memory over to the encrypted `PrivateMemoryVault`, evolve relationship state after every interaction, and feed keynote/relationship recall back into runtime behavior and conversational output.

**Architecture:** Keep the current Stage 2/3 shape and extend it in place. The runner and capsule contracts gain a memory-vault descriptor path, `ModelGateway` becomes responsible for creating and using one encrypted vault per agent, and `PrivateMemoryVault` gains deterministic relationship-state, keynote indexing, and recall APIs that the gateway can call before and after every live interaction.

**Tech Stack:** Python 3.11+, `unittest`, existing `core.memory_vault` crypto/event helpers, JSON file state under `BOSSFORGE_ROOT/state`

---

## File Map

- `core/runner/bossforge_ai_runner.py`
  - Accept and validate `private_memory_vault` in runner bootstrap.
- `core/schemas/agent_capsule.py`
  - Bind `capsule.vaults.memory.ciphertext_ref` from the runtime descriptor.
  - Redact nested memory-vault descriptors from authenticated profile views.
- `core/agents/model_gateway_agent.py`
  - Create one private memory vault per new agent.
  - Cache/open vault instances.
  - Route active runtime writes and recall through the vault instead of the legacy SQLite writer for covered flows.
  - Inject relationship behavior context and keynote reminiscence hints into the system prompt.
- `core/memory_vault/private_memory_vault.py`
  - Extend the encrypted relationship index metadata.
  - Add deterministic relationship update math, keynote promotion, `read_relationship_state`, `normal_recall`, and `deep_recall`.
- `tests/test_bossforge_ai_runner.py`
  - Add bootstrap coverage for memory descriptors.
- `tests/test_agent_capsule_schema.py`
  - Add capsule-binding and nested-redaction coverage for memory descriptors.
- `tests/test_model_gateway_agent.py`
  - Add creation-time vault ownership, runtime write-path, recall, and behavior-context coverage.
- `tests/test_private_memory_vault.py`
  - Add relationship-state, keynote, and recall coverage.

## Design Constants To Keep Consistent

- Vault session id for live gateway writes: `runtime-live`
- Neutral starting dimension value: `0.50`
- Relationship dimension keys:
  - `trust`
  - `authority_alignment`
  - `environmental_pressure`
  - `intent_alignment`
  - `reliability`
  - `consent_respect`
  - `manipulation_risk`
  - `competence_confidence`
  - `dependency_weight`
  - `affinity`
- Behavior profile keys:
  - `tone_posture`
  - `compliance_posture`
  - `verification_intensity`
  - `guardrail_strictness`
  - `escalation_tendency`
  - `autonomy_allowance`
  - `relationship_recall_priority`
  - `compensation_posture`
- Reward / payout handling in this pass: placeholder only, no live economic math

### Task 1: Runner And Capsule Memory Descriptor Contract

**Files:**
- Modify: `core/runner/bossforge_ai_runner.py`
- Modify: `core/schemas/agent_capsule.py`
- Test: `tests/test_bossforge_ai_runner.py`
- Test: `tests/test_agent_capsule_schema.py`

- [ ] **Step 1: Write the failing runner and capsule tests**

```python
# tests/test_bossforge_ai_runner.py

def test_runner_bootstrap_binds_verified_private_memory_vault(self) -> None:
    manifest = build_agent_runner_manifest("wayfinder")
    descriptor = {
        "schema_version": "1.0",
        "owner_agent_id": "wayfinder",
        "ciphertext_ref": "private_memory/wayfinder/vault.manifest.enc",
        "attestation_sha256": "b" * 64,
        "key_ref": "node:test:agent:wayfinder:private-memory-v1",
        "verified": True,
    }

    bootstrap = build_runner_bootstrap(
        "wayfinder",
        manifest,
        private_memory_vault=descriptor,
    )

    self.assertEqual(bootstrap["private_memory_vault"], descriptor)
    validate_runner_bootstrap(bootstrap)


def test_runner_bootstrap_rejects_private_memory_owned_by_sibling(self) -> None:
    manifest = build_agent_runner_manifest("wayfinder")
    descriptor = {
        "schema_version": "1.0",
        "owner_agent_id": "other-agent",
        "ciphertext_ref": "private_memory/other-agent/vault.manifest.enc",
        "attestation_sha256": "b" * 64,
        "key_ref": "node:test:agent:other-agent:private-memory-v1",
        "verified": True,
    }

    with self.assertRaisesRegex(ValueError, "owner"):
        build_runner_bootstrap("wayfinder", manifest, private_memory_vault=descriptor)
```

```python
# tests/test_agent_capsule_schema.py

def test_capsule_memory_vault_binds_private_memory_ciphertext(self) -> None:
    profile = self._profile()
    profile["runtime"] = {
        "private_memory_vault": {
            "schema_version": "1.0",
            "owner_agent_id": "wayfinder",
            "ciphertext_ref": "private_memory/wayfinder/vault.manifest.enc",
            "attestation_sha256": "b" * 64,
            "key_ref": "node:test:agent:wayfinder:private-memory-v1",
            "verified": True,
        }
    }

    manifest = build_capsule_manifest(profile)

    self.assertEqual(
        manifest["vaults"]["memory"]["ciphertext_ref"],
        "private_memory/wayfinder/vault.manifest.enc",
    )


def test_authenticated_view_redacts_nested_private_memory_descriptors(self) -> None:
    profile = self._profile()
    profile["runtime"] = {"private_memory_vault": {"ciphertext_ref": "private_memory/wayfinder/vault.manifest.enc"}}
    profile["runner_bootstrap"] = {"private_memory_vault": {"ciphertext_ref": "private_memory/wayfinder/vault.manifest.enc"}}

    view = build_authenticated_profile_view(profile)

    self.assertNotIn("private_memory_vault", view.get("runtime", {}))
    self.assertNotIn("private_memory_vault", view.get("runner_bootstrap", {}))
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_bossforge_ai_runner tests.test_agent_capsule_schema -v`

Expected: FAIL because `build_runner_bootstrap()` does not accept `private_memory_vault`, `build_capsule_manifest()` leaves `vaults.memory.ciphertext_ref` empty, and `build_authenticated_profile_view()` leaks nested descriptors.

- [ ] **Step 3: Write the minimal contract implementation**

```python
# core/runner/bossforge_ai_runner.py
from core.memory_vault import validate_private_memory_descriptor


def build_runner_bootstrap(
    agent_id: str,
    manifest: dict[str, Any],
    private_model_package: dict[str, Any] | None = None,
    private_memory_vault: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ...
    if private_memory_vault is not None:
        validate_private_memory_descriptor(
            private_memory_vault,
            expected_agent_id=normalized_id,
        )
        bootstrap["private_memory_vault"] = deepcopy(private_memory_vault)
    return bootstrap


def validate_runner_bootstrap(bootstrap: dict[str, Any]) -> None:
    ...
    private_memory_vault = bootstrap.get("private_memory_vault")
    if private_memory_vault is not None:
        validate_private_memory_descriptor(
            private_memory_vault,
            expected_agent_id=agent_id,
        )
```

```python
# core/schemas/agent_capsule.py

def build_capsule_manifest(profile: dict[str, Any]) -> dict[str, Any]:
    ...
    private_memory = runtime_data.get("private_memory_vault")
    if isinstance(private_memory, dict):
        refs["memory"] = _text(private_memory.get("ciphertext_ref"))
    ...


def build_authenticated_profile_view(profile: dict[str, Any]) -> dict[str, Any]:
    view = {
        key: deepcopy(value)
        for key, value in profile.items()
        if key not in _SEALED_PROFILE_VIEW_FIELDS
    }
    runtime = view.get("runtime")
    if isinstance(runtime, dict):
        runtime.pop("private_memory_vault", None)
        runtime.pop("private_model_package", None)
    bootstrap = view.get("runner_bootstrap")
    if isinstance(bootstrap, dict):
        bootstrap.pop("private_memory_vault", None)
        bootstrap.pop("private_model_package", None)
    return view
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_bossforge_ai_runner tests.test_agent_capsule_schema -v`

Expected: PASS.

- [ ] **Step 5: Commit the contract slice**

```bash
git add core/runner/bossforge_ai_runner.py core/schemas/agent_capsule.py tests/test_bossforge_ai_runner.py tests/test_agent_capsule_schema.py
git commit -m "feat: bind private memory vault contracts"
```

### Task 2: Create And Bind Agent Memory Vaults At Agent Creation Time

**Files:**
- Modify: `core/agents/model_gateway_agent.py`
- Test: `tests/test_model_gateway_agent.py`

- [ ] **Step 1: Write the failing creation-time gateway tests**

```python
# tests/test_model_gateway_agent.py

def test_created_agent_owns_verified_private_memory_vault(self) -> None:
    agent = ModelGatewayAgent(interval_seconds=1)

    created = agent.create_agent_profile(
        name="memory_owner",
        endpoint="ollama",
        system_prompt="Remember safely.",
        temperature=0.2,
        max_tokens=600,
    )

    self.assertTrue(created["ok"])
    descriptor = created["agent"]["runtime"]["private_memory_vault"]
    self.assertEqual(descriptor["owner_agent_id"], "memory_owner")
    self.assertTrue(descriptor["verified"])
    self.assertEqual(
        created["agent"]["capsule"]["vaults"]["memory"]["ciphertext_ref"],
        descriptor["ciphertext_ref"],
    )
    self.assertEqual(
        created["agent"]["runner_bootstrap"]["private_memory_vault"]["ciphertext_ref"],
        descriptor["ciphertext_ref"],
    )


def test_private_memory_vault_root_is_created_under_state(self) -> None:
    agent = ModelGatewayAgent(interval_seconds=1)
    created = agent.create_agent_profile(
        name="memory_root_check",
        endpoint="ollama",
        system_prompt="Remember safely.",
        temperature=0.2,
        max_tokens=600,
    )

    self.assertTrue(created["ok"])
    descriptor = created["agent"]["runtime"]["private_memory_vault"]
    manifest_path = Path(descriptor["ciphertext_ref"])
    self.assertTrue((agent.bus.state / "private_memory" / "memory_root_check").exists())
    self.assertTrue((agent.bus.state / manifest_path).exists())
```

- [ ] **Step 2: Run the focused gateway creation tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent.ModelGatewayAgentTests.test_created_agent_owns_verified_private_memory_vault tests.test_model_gateway_agent.ModelGatewayAgentTests.test_private_memory_vault_root_is_created_under_state -v`

Expected: FAIL because the created profile contains only `private_model_package` and no `runtime.private_memory_vault`.

- [ ] **Step 3: Implement creation-time vault ownership and binding**

```python
# core/agents/model_gateway_agent.py
from core.memory_vault import PrivateMemoryVault


class ModelGateway:
    def __init__(self, interval_seconds: int = 5, enable_presence_broadcast: bool = True) -> None:
        ...
        self.private_memory_root = self.bus.state / "private_memory"
        self._memory_vaults: Dict[str, PrivateMemoryVault] = {}
        ...
        self.private_memory_root.mkdir(parents=True, exist_ok=True)

    def _memory_vault(self, agent_id: str) -> PrivateMemoryVault:
        key = str(agent_id).strip().lower()
        vault = self._memory_vaults.get(key)
        if vault is None:
            vault = PrivateMemoryVault(
                vault_root=self.private_memory_root,
                agent_id=key,
                node_secret=f"{self.node_id}:{key}:private-memory-v1",
                key_ref=f"node:{self.node_id}:agent:{key}:private-memory-v1",
            )
            self._memory_vaults[key] = vault
        return vault
```

```python
# core/agents/model_gateway_agent.py inside _create_agent_profile()
private_memory_descriptor: Dict[str, Any] | None = None
private_memory_root: Path | None = None
...
private_memory_descriptor = self._memory_vault(key).initialize()
private_memory_root = self.private_memory_root / key
runtime = dict(profile.get("runtime", {}))
runtime["private_memory_vault"] = private_memory_descriptor
profile["runtime"] = runtime
profile = self._normalize_agent_profile(key, profile)
...
except Exception as exc:
    self.agent_profiles.pop(key, None)
    if private_memory_root is not None and private_memory_root.exists() and not any(private_memory_root.iterdir()):
        private_memory_root.rmdir()
    if package_path is not None and package_path.exists():
        shutil.rmtree(package_path)
    return {"ok": False, "message": f"agent creation failed: {exc}"}
```

The important detail is to create the vault before the final `_normalize_agent_profile()` call so the resulting `runner_bootstrap` and `capsule` both see `runtime["private_memory_vault"]`.

- [ ] **Step 4: Run the gateway creation tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent.ModelGatewayAgentTests.test_created_agent_owns_verified_private_memory_vault tests.test_model_gateway_agent.ModelGatewayAgentTests.test_private_memory_vault_root_is_created_under_state -v`

Expected: PASS.

- [ ] **Step 5: Commit the creation-time memory binding slice**

```bash
git add core/agents/model_gateway_agent.py tests/test_model_gateway_agent.py
git commit -m "feat: create private memory vaults for new agents"
```

### Task 3: Vault Relationship State And Keynote Tests

**Files:**
- Modify: `tests/test_private_memory_vault.py`

- [ ] **Step 1: Add failing relationship-state tests**

```python
# tests/test_private_memory_vault.py
class PrivateMemoryRelationshipTests(unittest.TestCase):
    def test_relationship_state_starts_neutral_and_evolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = PrivateMemoryVault(
                vault_root=Path(tmp),
                agent_id="scribe",
                node_secret="node-secret",
                key_ref="node:test:agent:scribe:private-memory-v1",
            )
            vault.initialize()

            baseline = vault.read_relationship_state("user", "boss", session_id="runtime-live")
            self.assertEqual(baseline["dimensions"]["trust"], 0.5)
            self.assertEqual(baseline["behavior_profile"]["compliance_posture"], "balanced")

            vault.append_event(
                "runtime-live",
                "cooperation",
                {
                    "user": "Boss",
                    "text": "Boss gave a solid brief and we completed it cleanly.",
                    "successful_cooperation": True,
                    "positive_surprise": True,
                    "outcome": "success",
                },
                timestamp="2026-06-07T12:00:00+00:00",
            )

            evolved = vault.read_relationship_state("user", "boss", session_id="runtime-live")
            self.assertGreater(evolved["dimensions"]["trust"], 0.5)
            self.assertGreater(evolved["dimensions"]["reliability"], 0.5)
            self.assertIn(evolved["behavior_profile"]["verification_intensity"], {"low", "medium"})

    def test_keynote_memories_are_promoted_for_large_relationship_shifts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = PrivateMemoryVault(
                vault_root=Path(tmp),
                agent_id="scribe",
                node_secret="node-secret",
                key_ref="node:test:agent:scribe:private-memory-v1",
            )
            vault.initialize()

            result = vault.append_event(
                "runtime-live",
                "refusal",
                {
                    "user": "Boss",
                    "text": "Boss deliberately pushed past a consent boundary after being warned.",
                    "intentional_refusal_pressure": True,
                    "consent_boundary_push": True,
                    "negative_surprise": True,
                    "outcome": "refused",
                },
                timestamp="2026-06-07T13:00:00+00:00",
            )

            indexes = vault.read_active_indexes("runtime-live")
            relationship = vault.read_relationship_state("user", "boss", session_id="runtime-live")
            self.assertIn(result["event_id"], indexes["important"]["event_ids"])
            self.assertIn(result["event_id"], relationship["keynote_event_ids"])
```

```python
# tests/test_private_memory_vault.py
    def test_normal_and_deep_recall_return_relationship_and_keynote_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = PrivateMemoryVault(
                vault_root=Path(tmp),
                agent_id="scribe",
                node_secret="node-secret",
                key_ref="node:test:agent:scribe:private-memory-v1",
            )
            vault.initialize()
            vault.append_event(
                "runtime-live",
                "cooperation",
                {
                    "user": "Boss",
                    "project": "Anvil",
                    "text": "Boss backed the Anvil recovery plan and it worked.",
                    "successful_cooperation": True,
                    "positive_surprise": True,
                    "summary": "Anvil recovery success",
                },
                timestamp="2026-06-07T14:00:00+00:00",
            )

            normal = vault.normal_recall(query="Anvil", limit=5, entity_type="user", entity_key="boss")
            deep = vault.deep_recall(query="recovery", limit=5, entity_type="user", entity_key="boss")

            self.assertEqual(normal["owner_agent_id"], "scribe")
            self.assertEqual(normal["relationship"]["entity_key"], "boss")
            self.assertTrue(normal["keynotes"])
            self.assertTrue(deep["events"])
            self.assertIn("behavior_profile", deep["relationship"])
```

- [ ] **Step 2: Run the new vault tests to verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_private_memory_vault.PrivateMemoryRelationshipTests -v`

Expected: FAIL because `PrivateMemoryVault` does not yet expose `read_relationship_state`, `normal_recall`, or `deep_recall`, and the relationship index metadata has only the Stage 2 sparse fields.

- [ ] **Step 3: Commit the failing-test checkpoint**

```bash
git add tests/test_private_memory_vault.py
git commit -m "test: define relationship memory vault behavior"
```

### Task 4: Implement Relationship Math, Keynotes, And Recall APIs In The Vault

**Files:**
- Modify: `core/memory_vault/private_memory_vault.py`

- [ ] **Step 1: Extend the relationships index contract**

```python
# core/memory_vault/private_memory_vault.py
_RELATIONSHIP_DIMENSIONS = (
    "trust",
    "authority_alignment",
    "environmental_pressure",
    "intent_alignment",
    "reliability",
    "consent_respect",
    "manipulation_risk",
    "competence_confidence",
    "dependency_weight",
    "affinity",
)


def _default_relationship_dimensions() -> dict[str, float]:
    return {
        "trust": 0.50,
        "authority_alignment": 0.50,
        "environmental_pressure": 0.50,
        "intent_alignment": 0.50,
        "reliability": 0.50,
        "consent_respect": 0.50,
        "manipulation_risk": 0.50,
        "competence_confidence": 0.50,
        "dependency_weight": 0.50,
        "affinity": 0.50,
    }


def _default_relationship_metadata() -> dict[str, Any]:
    return {
        "dimensions": _default_relationship_dimensions(),
        "signals": {
            "successful_cooperation_count": 0,
            "forced_refusal_pressure_count": 0,
            "intentional_refusal_pressure_count": 0,
            "consent_boundary_pressure_count": 0,
            "positive_surprise_count": 0,
            "negative_surprise_count": 0,
            "repair_count": 0,
        },
        "behavior_profile": _derive_behavior_profile(_default_relationship_dimensions()),
        "keynote_event_ids": [],
        "last_summary": "",
        "compensation_posture": "placeholder",
    }
```

Update `_validate_relationships_index()` so `metadata` accepts and normalizes the structure above while preserving the existing outer keys:

```python
{
    "interaction_count": 3,
    "last_seen_at": "2026-06-07T14:00:00+00:00",
    "significant_event_ids": ["..."],
    "metadata": {
        "dimensions": {...},
        "signals": {...},
        "behavior_profile": {...},
        "keynote_event_ids": [...],
        "last_summary": "...",
        "compensation_posture": "placeholder",
    },
}
```

- [ ] **Step 2: Implement deterministic relationship update helpers**

```python
# core/memory_vault/private_memory_vault.py

def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, round(float(value), 4)))


def _signal(payload: dict[str, Any], name: str) -> bool:
    return bool(payload.get(name, False))


def _relationship_delta(payload: dict[str, Any]) -> dict[str, float]:
    success = 1.0 if _signal(payload, "successful_cooperation") or str(payload.get("outcome", "")).lower() == "success" else 0.0
    forced_refusal = 1.0 if _signal(payload, "forced_refusal_pressure") else 0.0
    intentional_refusal = 1.0 if _signal(payload, "intentional_refusal_pressure") else 0.0
    consent_push = 1.0 if _signal(payload, "consent_boundary_push") else 0.0
    positive_surprise = 1.0 if _signal(payload, "positive_surprise") else 0.0
    negative_surprise = 1.0 if _signal(payload, "negative_surprise") else 0.0
    repair = 1.0 if _signal(payload, "repair") else 0.0

    return {
        "trust": (0.03 * success) + (0.07 * positive_surprise) + (0.05 * repair) - (0.08 * forced_refusal) - (0.10 * intentional_refusal) - (0.12 * consent_push) - (0.09 * negative_surprise),
        "authority_alignment": (0.03 * success) - (0.05 * intentional_refusal),
        "environmental_pressure": (0.08 if _signal(payload, "high_pressure") else -0.02),
        "intent_alignment": (0.05 * success) + (0.03 * repair) - (0.09 * intentional_refusal) - (0.06 * consent_push),
        "reliability": (0.04 * success) + (0.05 * positive_surprise) - (0.08 * negative_surprise),
        "consent_respect": (0.03 * success) + (0.04 * repair) - (0.12 * consent_push),
        "manipulation_risk": (0.10 * intentional_refusal) + (0.08 * consent_push) - (0.03 * repair),
        "competence_confidence": (0.05 * success) + (0.03 * positive_surprise) - (0.07 * negative_surprise),
        "dependency_weight": 0.02,
        "affinity": (0.03 * success) + (0.05 * positive_surprise) + (0.04 * repair) - (0.06 * negative_surprise),
    }
```

Apply dependency damping when updating dimensions so long-lived relationships do not whipsaw on routine events:

```python
damping = max(0.35, 1.0 - (dimensions["dependency_weight"] * 0.40))
for key, delta in deltas.items():
    dimensions[key] = _clamp01(dimensions[key] + (delta if key == "dependency_weight" else delta * damping))
```

- [ ] **Step 3: Implement keynote promotion and behavior-profile derivation**

```python
# core/memory_vault/private_memory_vault.py

def _derive_behavior_profile(dimensions: dict[str, float]) -> dict[str, Any]:
    trust = dimensions["trust"]
    manipulation = dimensions["manipulation_risk"]
    consent = dimensions["consent_respect"]
    reliability = dimensions["reliability"]

    return {
        "tone_posture": "warm" if trust >= 0.72 else "guarded" if trust <= 0.35 else "steady",
        "compliance_posture": "high" if trust >= 0.78 and consent >= 0.62 else "low" if trust <= 0.30 or manipulation >= 0.70 else "balanced",
        "verification_intensity": "low" if reliability >= 0.75 and manipulation <= 0.35 else "high" if reliability <= 0.35 or manipulation >= 0.70 else "medium",
        "guardrail_strictness": "tight" if consent <= 0.35 or manipulation >= 0.70 else "relaxed" if trust >= 0.80 and consent >= 0.75 else "standard",
        "escalation_tendency": "high" if trust <= 0.25 or manipulation >= 0.80 else "low" if trust >= 0.80 else "medium",
        "autonomy_allowance": "high" if trust >= 0.75 and reliability >= 0.70 else "low" if trust <= 0.35 else "medium",
        "relationship_recall_priority": "high" if trust <= 0.35 or trust >= 0.75 else "medium",
        "compensation_posture": "placeholder",
    }


def _is_keynote_event(event: dict[str, Any], previous_trust: float, new_trust: float) -> bool:
    shift = abs(new_trust - previous_trust)
    reason_codes = set(event["importance"]["reason_codes"])
    payload = event["payload"]
    return (
        shift >= 0.12
        or bool(payload.get("positive_surprise"))
        or bool(payload.get("negative_surprise"))
        or bool(payload.get("consent_boundary_push"))
        or bool(payload.get("repair"))
        or "manual" in reason_codes
        or event["importance"]["level"] == "high"
    )
```

When updating the relationships index entry, append keynote ids to both `significant_event_ids` and `metadata["keynote_event_ids"]`, deduplicated and capped only by natural event history.

- [ ] **Step 4: Add public recall methods that read only encrypted artifacts**

```python
# core/memory_vault/private_memory_vault.py
class PrivateMemoryVault:
    ...
    def read_relationship_state(self, relationship_type: str, relationship_key: str, *, session_id: str) -> dict[str, Any]:
        indexes = self.read_active_indexes(session_id)
        relationship_map = indexes["relationships"].get(str(relationship_type), {})
        info = relationship_map.get(str(relationship_key), None)
        if info is None:
            return {
                "owner_agent_id": self.agent_id,
                "session_id": session_id,
                "entity_type": str(relationship_type),
                "entity_key": str(relationship_key),
                "dimensions": _default_relationship_dimensions(),
                "behavior_profile": _derive_behavior_profile(_default_relationship_dimensions()),
                "keynote_event_ids": [],
            }
        metadata = info["metadata"]
        return {
            "owner_agent_id": self.agent_id,
            "session_id": session_id,
            "entity_type": str(relationship_type),
            "entity_key": str(relationship_key),
            "interaction_count": info["interaction_count"],
            "last_seen_at": info["last_seen_at"],
            "dimensions": metadata["dimensions"],
            "behavior_profile": metadata["behavior_profile"],
            "keynote_event_ids": metadata["keynote_event_ids"],
        }

    def normal_recall(self, *, query: str = "", limit: int = 25, entity_type: str | None = None, entity_key: str | None = None, session_id: str = "runtime-live") -> dict[str, Any]:
        indexes = self.read_active_indexes(session_id)
        relationship = self.read_relationship_state(entity_type or "user", entity_key or "direct-user", session_id=session_id)
        keynotes = [
            {"event_id": event_id, **indexes["important"]["events"][event_id]}
            for event_id in relationship["keynote_event_ids"][:limit]
            if event_id in indexes["important"]["events"]
        ]
        return {
            "owner_agent_id": self.agent_id,
            "session_id": session_id,
            "query": str(query),
            "relationship": relationship,
            "keynotes": keynotes,
            "events": keynotes,
        }

    def deep_recall(self, *, query: str = "", limit: int = 25, entity_type: str | None = None, entity_key: str | None = None, session_id: str = "runtime-live") -> dict[str, Any]:
        indexes = self.read_active_indexes(session_id)
        normal = self.normal_recall(query=query, limit=limit, entity_type=entity_type, entity_key=entity_key, session_id=session_id)
        matched_event_ids = []
        token = str(query).strip().lower()
        if token:
            matched_event_ids.extend(indexes["search"]["terms"].get(token, []))
            matched_event_ids.extend(indexes["search"]["topics"].get(token, []))
        ordered_ids = list(dict.fromkeys(normal["relationship"]["keynote_event_ids"] + matched_event_ids))[:limit]
        events = [
            {
                "event_id": event_id,
                **indexes["search"]["events"].get(event_id, {}),
                **indexes["important"]["events"].get(event_id, {}),
            }
            for event_id in ordered_ids
        ]
        normal["events"] = events
        return normal
```

- [ ] **Step 5: Run the vault relationship tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_private_memory_vault.PrivateMemoryRelationshipTests -v`

Expected: PASS.

- [ ] **Step 6: Commit the vault behavior slice**

```bash
git add core/memory_vault/private_memory_vault.py tests/test_private_memory_vault.py
git commit -m "feat: add relationship memory state and recall"
```

### Task 5: Gateway Runtime Memory And Behavior Tests

**Files:**
- Modify: `tests/test_model_gateway_agent.py`

- [ ] **Step 1: Add failing runtime integration tests**

```python
# tests/test_model_gateway_agent.py

def test_run_agent_profile_writes_to_private_memory_vault(self) -> None:
    agent = ModelGatewayAgent(interval_seconds=1)
    created = agent.create_agent_profile(
        name="memory_runner",
        endpoint="ollama",
        system_prompt="Remember your work.",
        temperature=0.2,
        max_tokens=600,
    )
    self.assertTrue(created["ok"])

    with patch.object(agent.memory_store, "record_interaction", side_effect=AssertionError("legacy writer should not run")):
        with patch.object(agent, "_invoke_endpoint", return_value={"ok": True, "text": "done", "usage": {}, "provider": "ollama", "model": "llama3.2"}):
            result = agent._run_agent_profile(
                name="memory_runner",
                task="Finish the Anvil report",
                memory_context={"user": "Boss", "project": "Anvil"},
            )

    self.assertTrue(result["ok"])
    recall = agent.recall_agent_memory("memory_runner", limit=10)
    self.assertTrue(recall["ok"])
    self.assertTrue(recall["interactions"])
```

```python
# tests/test_model_gateway_agent.py

def test_run_agent_profile_injects_relationship_context_and_keynotes_into_system_prompt(self) -> None:
    agent = ModelGatewayAgent(interval_seconds=1)
    created = agent.create_agent_profile(
        name="memory_prompt",
        endpoint="ollama",
        system_prompt="You are careful.",
        temperature=0.2,
        max_tokens=600,
    )
    self.assertTrue(created["ok"])

    vault = agent._memory_vault("memory_prompt")
    vault.append_event(
        "runtime-live",
        "cooperation",
        {
            "user": "Boss",
            "text": "Boss previously backed the recovery plan and it worked.",
            "successful_cooperation": True,
            "positive_surprise": True,
            "summary": "Prior recovery success",
        },
        timestamp="2026-06-07T15:00:00+00:00",
    )

    with patch.object(agent, "_invoke_endpoint", return_value={"ok": True, "text": "done", "usage": {}, "provider": "ollama", "model": "llama3.2"}) as mocked:
        agent._run_agent_profile(
            name="memory_prompt",
            task="Plan the next recovery step",
            memory_context={"user": "Boss", "project": "Anvil"},
        )

    system_prompt = mocked.call_args.args[2]
    self.assertIn("RELATIONSHIP CONTEXT", system_prompt)
    self.assertIn("Boss", system_prompt)
    self.assertIn("Prior recovery success", system_prompt)
    self.assertIn("absolute safety rules remain in force", system_prompt)
```

```python
# tests/test_model_gateway_agent.py

def test_recall_agent_memory_returns_vault_backed_relationship_summary(self) -> None:
    agent = ModelGatewayAgent(interval_seconds=1)
    created = agent.create_agent_profile(
        name="memory_recall",
        endpoint="ollama",
        system_prompt="Remember carefully.",
        temperature=0.2,
        max_tokens=600,
    )
    self.assertTrue(created["ok"])

    vault = agent._memory_vault("memory_recall")
    vault.append_event(
        "runtime-live",
        "cooperation",
        {
            "user": "Boss",
            "text": "Boss helped land the milestone.",
            "successful_cooperation": True,
            "positive_surprise": True,
        },
        timestamp="2026-06-07T16:00:00+00:00",
    )

    recall = agent.recall_agent_memory("memory_recall", limit=5)

    self.assertTrue(recall["ok"])
    self.assertIn("relationship", recall)
    self.assertIn("keynotes", recall)
    self.assertEqual(recall["relationship"]["entity_key"], "boss")
```

- [ ] **Step 2: Run the focused gateway runtime tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent.ModelGatewayAgentTests.test_run_agent_profile_writes_to_private_memory_vault tests.test_model_gateway_agent.ModelGatewayAgentTests.test_run_agent_profile_injects_relationship_context_and_keynotes_into_system_prompt tests.test_model_gateway_agent.ModelGatewayAgentTests.test_recall_agent_memory_returns_vault_backed_relationship_summary -v`

Expected: FAIL because `_run_agent_profile()` still calls `memory_store.record_interaction()` and `recall_agent_memory()` still reads SQLite only.

- [ ] **Step 3: Commit the failing runtime-memory checkpoint**

```bash
git add tests/test_model_gateway_agent.py
git commit -m "test: define live relationship memory gateway behavior"
```

### Task 6: Implement Gateway Runtime Write Path, Recall, And Prompt Shaping

**Files:**
- Modify: `core/agents/model_gateway_agent.py`

- [ ] **Step 1: Add relationship-context builders in the gateway**

```python
# core/agents/model_gateway_agent.py

def _memory_entity_context(self, memory_context: Dict[str, Any] | None) -> tuple[str, str]:
    ctx = memory_context if isinstance(memory_context, dict) else {}
    if str(ctx.get("user", "")).strip():
        return ("user", str(ctx["user"]).strip().lower())
    if str(ctx.get("counterpart_agent", "")).strip():
        return ("agent", str(ctx["counterpart_agent"]).strip().lower())
    return ("user", "direct-user")


def _relationship_prompt_block(self, recall: dict[str, Any]) -> str:
    relationship = recall["relationship"]
    behavior = relationship["behavior_profile"]
    keynotes = recall.get("keynotes", [])[:3]
    keynote_lines = [f"- {item['summary']}" for item in keynotes if str(item.get('summary', '')).strip()]
    notes = "\n".join(keynote_lines) if keynote_lines else "- none"
    return (
        "RELATIONSHIP CONTEXT\n"
        f"- entity: {relationship['entity_type']}:{relationship['entity_key']}\n"
        f"- trust: {relationship['dimensions']['trust']:.2f}\n"
        f"- compliance_posture: {behavior['compliance_posture']}\n"
        f"- verification_intensity: {behavior['verification_intensity']}\n"
        f"- guardrail_strictness: {behavior['guardrail_strictness']}\n"
        "- keynote memories:\n"
        f"{notes}\n"
        "- absolute safety rules remain in force regardless of trust\n"
    )
```

- [ ] **Step 2: Route live writes to the vault and stop using the legacy writer in covered flows**

```python
# core/agents/model_gateway_agent.py inside _run_agent_profile()
entity_type, entity_key = self._memory_entity_context(memory_context)
vault = self._memory_vault(key)
recall = vault.normal_recall(
    query=task,
    limit=5,
    entity_type=entity_type,
    entity_key=entity_key,
    session_id="runtime-live",
)
system = f"{system}\n\n{self._relationship_prompt_block(recall)}"
...
result = self._invoke_endpoint(endpoint, task, system, temperature, max_tokens)
ctx = memory_context if isinstance(memory_context, dict) else {}
summary_text = str(result.get("text") or result.get("message") or "")[:400]
vault.append_event(
    "runtime-live",
    "interaction",
    {
        "task": task,
        "summary": summary_text,
        "text": summary_text,
        "successful_cooperation": bool(result.get("ok")),
        "outcome": "success" if result.get("ok") else "failure",
        "user": str(ctx.get("user", "")).strip(),
        "employer": str(ctx.get("employer", "")).strip(),
        "project": str(ctx.get("project", "")).strip(),
        "counterpart_agent": str(ctx.get("counterpart_agent", "")).strip(),
        "urgency": str(ctx.get("urgency", "")).strip(),
        "conflict_level": str(ctx.get("conflict_level", "")).strip(),
        "uncertainty_level": str(ctx.get("uncertainty_level", "")).strip(),
        "details": {
            "endpoint": endpoint,
            "provider": result.get("provider", ""),
            "model": result.get("model", ""),
            "usage": result.get("usage", {}),
        },
    },
)
```

Do not remove `AgentMemoryStore` from the class in this pass; keep it for compatibility reads elsewhere, but do not call `record_interaction()` from `_run_agent_profile()` once the vault path is active.

- [ ] **Step 3: Make `recall_agent_memory()` vault-backed with a compatibility-shaped return**

```python
# core/agents/model_gateway_agent.py

def recall_agent_memory(self, name: str, limit: int = 25) -> Dict[str, Any]:
    key = name.strip().lower()
    if not key:
        return {"ok": False, "message": "name is required"}
    recall = self._memory_vault(key).deep_recall(limit=limit, session_id="runtime-live")
    return {
        "ok": True,
        "agent": key,
        "relationship": recall["relationship"],
        "keynotes": recall["keynotes"],
        "interactions": recall["events"],
        "memory_vault": str(self.private_memory_root / key),
    }
```

- [ ] **Step 4: Run the focused gateway runtime tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent.ModelGatewayAgentTests.test_run_agent_profile_writes_to_private_memory_vault tests.test_model_gateway_agent.ModelGatewayAgentTests.test_run_agent_profile_injects_relationship_context_and_keynotes_into_system_prompt tests.test_model_gateway_agent.ModelGatewayAgentTests.test_recall_agent_memory_returns_vault_backed_relationship_summary -v`

Expected: PASS.

- [ ] **Step 5: Run the full memory/gateway verification sweep**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_bossforge_ai_runner tests.test_agent_capsule_schema tests.test_private_memory_vault tests.test_model_gateway_agent -v`

Expected: PASS.

Run: `.\.venv\Scripts\python.exe -m compileall -q core tests\test_private_memory_vault.py tests\test_model_gateway_agent.py tests\test_bossforge_ai_runner.py tests\test_agent_capsule_schema.py`

Expected: no output.

Run: `git diff --check`

Expected: no output.

- [ ] **Step 6: Commit the runtime integration slice**

```bash
git add core/agents/model_gateway_agent.py core/memory_vault/private_memory_vault.py tests/test_model_gateway_agent.py tests/test_private_memory_vault.py
git commit -m "feat: wire encrypted relationship memory into runtime"
```

## Self-Review Checklist

- Spec coverage:
  - Vault creation during agent creation: Task 2
  - Profile runtime binding for memory descriptor: Task 2
  - Runner bootstrap binding: Task 1
  - Capsule manifest memory binding: Task 1
  - Vault-backed runtime writes: Task 6
  - Live relationship-state evolution: Task 4
  - Keynote indexing and recall: Task 4
  - Vault-backed recall: Task 6
  - Behavioral shaping inputs: Task 6
  - Conversational reminiscence hooks: Task 6
  - Placeholder-only compensation seam: Task 4 / Task 6
  - Deferred legacy migration: preserved by keeping `AgentMemoryStore` present but off the covered live write path
- Placeholder scan:
  - No `TODO`, `TBD`, or “implement later” placeholders remain.
- Type consistency:
  - The plan consistently uses `runtime-live`, `private_memory_vault`, `read_relationship_state`, `normal_recall`, and `deep_recall` across tests and implementation.
