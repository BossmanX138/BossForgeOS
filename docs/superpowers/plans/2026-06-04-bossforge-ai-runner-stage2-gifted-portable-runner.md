# BossForge AI Runner Stage 2 Gifted Portable Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a signed, neutral BossForgeOS AI runner contract so RuneForge remains personalized while every newly forged LLM/BossGate agent receives an independent, agent-local runner manifest derived from RuneForge's gifted runtime template.

**Architecture:** Create a focused `core.runner` module that owns the portable runner template, deterministic signing, verification, descendant manifest creation, and bootstrap payload validation. Integrate that contract into `core.schemas.agent_schema`, `core.agents.model_gateway_agent`, and the RuneForge provider profile without loading model weights or implementing dreams yet. Stage 2 stores only runner metadata and bootstrap contracts; private model packaging, memory vaults, and dream checkpoints remain later stages.

**Tech Stack:** Python 3.11+, standard-library `hashlib`/`hmac`, `unittest`, JSON metadata, existing BossForgeOS agent schema, Model Gateway, and RuneForge provider files.

---

## Scope Boundaries

Included:
- Neutral portable runner template.
- RuneForge personalized-origin manifest.
- Signed gifted runtime template metadata.
- Descendant runner manifest copied from the gifted template and detached after creation.
- Per-agent runner bootstrap metadata for Model Gateway-created agents.
- Documentation/tracker updates for Stage 2.

Deferred:
- Actual model-weight copying.
- Runtime process supervisor.
- Private memory vault persistence.
- Dream training, signed checkpoints, and rollback.
- Full BossGate move-only capsule transport.

## File Map

- Create `core/runner/__init__.py`: exports Stage 2 runner contract helpers.
- Create `core/runner/bossforge_ai_runner.py`: neutral runner template, signing, verification, descendant manifest, RuneForge origin manifest, bootstrap builder, validators.
- Create `tests/test_bossforge_ai_runner.py`: contract tests for signing, tamper rejection, RuneForge separation, descendant detachment, and bootstrap payloads.
- Modify `core/schemas/agent_schema.py`: normalize and validate `runtime.bossforge_ai_runner`.
- Modify `core/schemas/__init__.py`: export runner helper only if needed by public schema consumers.
- Modify `tests/test_agent_capsule_schema.py`: prove canonical profiles include valid runner metadata while RuneForge remains origin.
- Modify `core/agents/model_gateway_agent.py`: attach runner manifests to lightweight profile creation/load/import.
- Modify `tests/test_model_gateway_agent.py`: prove created agents receive independent runner bootstrap metadata.
- Modify `modules/runeforge_provider/runeforge_agent.profile.json`: mark RuneForge as the personalized runner origin and update sparse public card fields.
- Modify `modules/runeforge_provider/provider_manifest.json`: publish the gifted template version/signature metadata.
- Modify `docs/bossforge_ai_runner_todo.md`: mark Stage 2 items as completed only after verification.
- Modify `docs/AgentForge_readme.md`: add Stage 2 policy version `v1.13.0`.
- Modify `docs/agents_bossgate_agentforge_schema_guide.txt`: append current Stage 2 implementation boundary.

### Task 1: Add Portable Runner Contract Module

**Files:**
- Create: `core/runner/__init__.py`
- Create: `core/runner/bossforge_ai_runner.py`
- Create: `tests/test_bossforge_ai_runner.py`

- [ ] **Step 1: Write failing portable-runner contract tests**

Create `tests/test_bossforge_ai_runner.py`:

```python
import unittest

from core.runner.bossforge_ai_runner import (
    GIFTED_TEMPLATE_VERSION,
    RUNEFORGE_AGENT_ID,
    build_agent_runner_manifest,
    build_runner_bootstrap,
    build_runeforge_origin_manifest,
    build_signed_gifted_template,
    validate_agent_runner_manifest,
    validate_runner_bootstrap,
    verify_signed_template,
)


class BossForgeAIRunnerTests(unittest.TestCase):
    def test_gifted_template_is_signed_and_verifiable(self) -> None:
        template = build_signed_gifted_template()
        self.assertEqual(template["template_id"], "bossforge-ai-runner-neutral")
        self.assertEqual(template["version"], GIFTED_TEMPLATE_VERSION)
        self.assertEqual(template["gifted_by"], RUNEFORGE_AGENT_ID)
        self.assertTrue(template["signature"])
        self.assertTrue(verify_signed_template(template))

    def test_template_signature_rejects_tampering(self) -> None:
        template = build_signed_gifted_template()
        tampered = dict(template)
        tampered["runtime_requirements"] = dict(template["runtime_requirements"])
        tampered["runtime_requirements"]["python"] = "3.99"
        self.assertFalse(verify_signed_template(tampered))

    def test_runeforge_origin_manifest_stays_personalized(self) -> None:
        manifest = build_runeforge_origin_manifest()
        self.assertEqual(manifest["agent_id"], RUNEFORGE_AGENT_ID)
        self.assertEqual(manifest["runner_role"], "personalized_origin")
        self.assertEqual(manifest["source_template"]["ancestor_id"], "")
        self.assertFalse(manifest["depends_on_runeforge_online"])
        validate_agent_runner_manifest(manifest)

    def test_descendant_manifest_is_detached_copy(self) -> None:
        manifest = build_agent_runner_manifest("wayfinder")
        self.assertEqual(manifest["agent_id"], "wayfinder")
        self.assertEqual(manifest["runner_role"], "descendant")
        self.assertEqual(manifest["source_template"]["ancestor_id"], RUNEFORGE_AGENT_ID)
        self.assertEqual(manifest["source_template"]["version"], GIFTED_TEMPLATE_VERSION)
        self.assertTrue(manifest["source_template"]["signature"])
        self.assertTrue(manifest["detached_after_creation"])
        self.assertFalse(manifest["depends_on_runeforge_online"])
        validate_agent_runner_manifest(manifest)

    def test_runner_bootstrap_references_agent_local_runner_and_vaults(self) -> None:
        manifest = build_agent_runner_manifest("wayfinder")
        bootstrap = build_runner_bootstrap("wayfinder", manifest)
        self.assertEqual(bootstrap["agent_id"], "wayfinder")
        self.assertEqual(bootstrap["runner_manifest"]["agent_id"], "wayfinder")
        self.assertEqual(bootstrap["wake_contract"], "bossforge-ai-runner-wake-v1")
        self.assertEqual(bootstrap["vault_bindings"]["runner"], "capsule.vaults.runner")
        self.assertEqual(bootstrap["vault_bindings"]["model"], "capsule.vaults.model")
        validate_runner_bootstrap(bootstrap)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bossforge_ai_runner -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.runner'`.

- [ ] **Step 3: Implement the runner contract module**

Create `core/runner/bossforge_ai_runner.py`:

```python
from __future__ import annotations

import hashlib
import hmac
import json
from copy import deepcopy
from typing import Any


RUNNER_CONTRACT_VERSION = "1.0"
GIFTED_TEMPLATE_VERSION = "gifted-runtime-v1"
RUNEFORGE_AGENT_ID = "runeforge"
_SIGNING_KEY = b"bossforge-ai-runner-stage2-dev-signing-key"


def _text(value: Any, default: str = "") -> str:
    return str(value or "").strip() or default


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in payload.items() if key != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign_payload(payload: dict[str, Any]) -> str:
    return hmac.new(_SIGNING_KEY, _canonical_payload(payload), hashlib.sha256).hexdigest()


def build_neutral_runner_template() -> dict[str, Any]:
    return {
        "template_id": "bossforge-ai-runner-neutral",
        "version": GIFTED_TEMPLATE_VERSION,
        "contract_version": RUNNER_CONTRACT_VERSION,
        "gifted_by": RUNEFORGE_AGENT_ID,
        "runner_kind": "bossforge_ai_runner",
        "runtime_requirements": {
            "python": "3.11+",
            "api_style": "openai-compatible",
            "supports_local_model": True,
            "supports_tools": True,
            "supports_state_machine": True,
        },
        "bootstrap_contracts": {
            "wake": "bossforge-ai-runner-wake-v1",
            "install": "bossforge-ai-runner-install-v1",
            "attestation": "bossforge-ai-runner-attestation-v1",
        },
        "sealed_capabilities": [
            "runner_config",
            "model_loader",
            "tool_mediation",
            "state_machine",
            "wake_controls",
        ],
    }


def build_signed_gifted_template() -> dict[str, Any]:
    template = build_neutral_runner_template()
    template["signature"] = _sign_payload(template)
    return template


def verify_signed_template(template: dict[str, Any]) -> bool:
    if not isinstance(template, dict):
        return False
    signature = _text(template.get("signature"))
    if not signature:
        return False
    expected = _sign_payload(template)
    return hmac.compare_digest(signature, expected)


def build_runeforge_origin_manifest() -> dict[str, Any]:
    template = build_signed_gifted_template()
    return {
        "agent_id": RUNEFORGE_AGENT_ID,
        "runner_role": "personalized_origin",
        "runner_contract_version": RUNNER_CONTRACT_VERSION,
        "independent_runner_version": "runeforge-personalized-v1",
        "source_template": {
            "template_id": template["template_id"],
            "version": template["version"],
            "ancestor_id": "",
            "signature": template["signature"],
        },
        "detached_after_creation": True,
        "depends_on_runeforge_online": False,
        "sealed": True,
    }


def build_agent_runner_manifest(agent_id: str, template: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_id = _text(agent_id).lower()
    if not normalized_id:
        raise ValueError("agent_id is required for runner manifest")
    signed_template = deepcopy(template) if isinstance(template, dict) else build_signed_gifted_template()
    if not verify_signed_template(signed_template):
        raise ValueError("gifted runner template signature is invalid")
    if normalized_id == RUNEFORGE_AGENT_ID:
        return build_runeforge_origin_manifest()
    return {
        "agent_id": normalized_id,
        "runner_role": "descendant",
        "runner_contract_version": RUNNER_CONTRACT_VERSION,
        "independent_runner_version": f"{normalized_id}-runner-v1",
        "source_template": {
            "template_id": signed_template["template_id"],
            "version": signed_template["version"],
            "ancestor_id": RUNEFORGE_AGENT_ID,
            "signature": signed_template["signature"],
        },
        "detached_after_creation": True,
        "depends_on_runeforge_online": False,
        "sealed": True,
    }


def validate_agent_runner_manifest(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("runner manifest must be an object")
    agent_id = _text(manifest.get("agent_id")).lower()
    if not agent_id:
        raise ValueError("runner manifest agent_id is required")
    if manifest.get("sealed") is not True:
        raise ValueError("runner manifest must be sealed")
    if manifest.get("depends_on_runeforge_online") is not False:
        raise ValueError("runner manifest must not depend on RuneForge being online")
    role = _text(manifest.get("runner_role")).lower()
    if role not in {"personalized_origin", "descendant"}:
        raise ValueError("runner_role must be personalized_origin or descendant")
    source = manifest.get("source_template")
    if not isinstance(source, dict):
        raise ValueError("runner manifest source_template is required")
    if role == "personalized_origin" and source.get("ancestor_id") != "":
        raise ValueError("RuneForge origin manifest must not declare an ancestor")
    if role == "descendant" and source.get("ancestor_id") != RUNEFORGE_AGENT_ID:
        raise ValueError("descendant runner manifests must record RuneForge ancestry")
    if not _text(source.get("version")) or not _text(source.get("signature")):
        raise ValueError("runner manifest source_template version and signature are required")


def build_runner_bootstrap(agent_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    validate_agent_runner_manifest(manifest)
    normalized_id = _text(agent_id).lower()
    if manifest["agent_id"] != normalized_id:
        raise ValueError("runner bootstrap agent_id must match manifest")
    return {
        "agent_id": normalized_id,
        "wake_contract": "bossforge-ai-runner-wake-v1",
        "install_contract": "bossforge-ai-runner-install-v1",
        "attestation_contract": "bossforge-ai-runner-attestation-v1",
        "runner_manifest": deepcopy(manifest),
        "vault_bindings": {
            "runner": "capsule.vaults.runner",
            "model": "capsule.vaults.model",
            "memory": "capsule.vaults.memory",
            "capability": "capsule.vaults.capability",
        },
    }


def validate_runner_bootstrap(bootstrap: dict[str, Any]) -> None:
    if not isinstance(bootstrap, dict):
        raise ValueError("runner bootstrap must be an object")
    agent_id = _text(bootstrap.get("agent_id")).lower()
    if not agent_id:
        raise ValueError("runner bootstrap agent_id is required")
    manifest = bootstrap.get("runner_manifest")
    validate_agent_runner_manifest(manifest)
    if manifest["agent_id"] != agent_id:
        raise ValueError("runner bootstrap agent_id must match manifest")
    if bootstrap.get("wake_contract") != "bossforge-ai-runner-wake-v1":
        raise ValueError("runner bootstrap wake contract is invalid")
    vault_bindings = bootstrap.get("vault_bindings")
    if not isinstance(vault_bindings, dict):
        raise ValueError("runner bootstrap vault_bindings are required")
    for key in ("runner", "model", "memory", "capability"):
        if not _text(vault_bindings.get(key)):
            raise ValueError(f"runner bootstrap vault binding is required: {key}")
```

Create `core/runner/__init__.py`:

```python
from .bossforge_ai_runner import (
    GIFTED_TEMPLATE_VERSION,
    RUNEFORGE_AGENT_ID,
    RUNNER_CONTRACT_VERSION,
    build_agent_runner_manifest,
    build_neutral_runner_template,
    build_runner_bootstrap,
    build_runeforge_origin_manifest,
    build_signed_gifted_template,
    validate_agent_runner_manifest,
    validate_runner_bootstrap,
    verify_signed_template,
)

__all__ = [
    "GIFTED_TEMPLATE_VERSION",
    "RUNEFORGE_AGENT_ID",
    "RUNNER_CONTRACT_VERSION",
    "build_agent_runner_manifest",
    "build_neutral_runner_template",
    "build_runner_bootstrap",
    "build_runeforge_origin_manifest",
    "build_signed_gifted_template",
    "validate_agent_runner_manifest",
    "validate_runner_bootstrap",
    "verify_signed_template",
]
```

- [ ] **Step 4: Run runner tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bossforge_ai_runner -v
```

Expected: `Ran 5 tests` and `OK`.

- [ ] **Step 5: Commit exact Task 1 files**

```powershell
git add core/runner/__init__.py core/runner/bossforge_ai_runner.py tests/test_bossforge_ai_runner.py
git commit -m "feat: add BossForge AI runner contract"
```

### Task 2: Attach Runner Manifests To Canonical Agent Profiles

**Files:**
- Modify: `core/schemas/agent_schema.py`
- Modify: `tests/test_agent_capsule_schema.py`

- [ ] **Step 1: Add failing canonical-runner tests**

Append to `tests/test_agent_capsule_schema.py`:

```python
    def test_canonical_profile_includes_descendant_runner_manifest(self) -> None:
        profile = normalize_agent_profile("scribe", {"name": "Scribe", "llm": {"enabled": True, "model": {"model_name": "qwen"}}})
        runner = profile["runtime"]["bossforge_ai_runner"]
        self.assertEqual(runner["agent_id"], "scribe")
        self.assertEqual(runner["runner_role"], "descendant")
        self.assertEqual(runner["source_template"]["ancestor_id"], "runeforge")
        self.assertFalse(runner["depends_on_runeforge_online"])
        validate_agent_profile(profile)

    def test_canonical_runeforge_profile_is_personalized_origin_runner(self) -> None:
        profile = normalize_agent_profile(
            "runeforge",
            {
                "name": "RuneForge",
                "agent_class": "prime",
                "agent_type": "controller",
                "rank": "commander",
                "skills": ["command"],
                "sigils": ["sigil_transporter"],
                "llm": {"enabled": True, "model": {"model_name": "Runeforge_Alpha-7b"}},
            },
        )
        runner = profile["runtime"]["bossforge_ai_runner"]
        self.assertEqual(runner["runner_role"], "personalized_origin")
        self.assertEqual(runner["source_template"]["ancestor_id"], "")
        self.assertFalse(runner["depends_on_runeforge_online"])
        validate_agent_profile(profile)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_capsule_schema -v
```

Expected: FAIL with `KeyError: 'bossforge_ai_runner'`.

- [ ] **Step 3: Normalize and validate runtime runner manifests**

In `core/schemas/agent_schema.py`, add imports:

```python
from core.runner import build_agent_runner_manifest, validate_agent_runner_manifest
```

Replace:

```python
    runtime = raw.get("runtime")
    out["runtime"] = runtime if isinstance(runtime, dict) else {}
```

with:

```python
    runtime = raw.get("runtime")
    runtime_out = dict(runtime) if isinstance(runtime, dict) else {}
    runner_manifest = runtime_out.get("bossforge_ai_runner")
    if not isinstance(runner_manifest, dict):
        runner_manifest = build_agent_runner_manifest(normalized_id)
    validate_agent_runner_manifest(runner_manifest)
    runtime_out["bossforge_ai_runner"] = runner_manifest
    out["runtime"] = runtime_out
```

In `validate_agent_profile`, immediately after the object-field loop for `runtime`, add:

```python
    runtime_profile = profile.get("runtime") if isinstance(profile.get("runtime"), dict) else {}
    runner_manifest = runtime_profile.get("bossforge_ai_runner")
    validate_agent_runner_manifest(runner_manifest)
```

- [ ] **Step 4: Run canonical capsule tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_capsule_schema tests.test_bossforge_ai_runner -v
```

Expected: all runner and capsule schema tests pass.

- [ ] **Step 5: Commit exact Task 2 files**

```powershell
git add core/schemas/agent_schema.py tests/test_agent_capsule_schema.py
git commit -m "feat: attach runner manifests to agent schema"
```

### Task 3: Attach Runner Bootstrap To Model Gateway Profiles

**Files:**
- Modify: `core/agents/model_gateway_agent.py`
- Modify: `tests/test_model_gateway_agent.py`

- [ ] **Step 1: Add failing Model Gateway bootstrap test**

Append to `tests/test_model_gateway_agent.py` near `test_created_agent_carries_stage1_capsule_metadata`:

```python
    def test_created_agent_carries_agent_local_runner_bootstrap(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="portable_runner",
            endpoint="ollama",
            system_prompt="Run locally.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])
        profile = agent.agent_profiles["portable_runner"]
        runner = profile["runtime"]["bossforge_ai_runner"]
        bootstrap = profile["runner_bootstrap"]
        self.assertEqual(runner["agent_id"], "portable_runner")
        self.assertEqual(runner["runner_role"], "descendant")
        self.assertFalse(runner["depends_on_runeforge_online"])
        self.assertEqual(bootstrap["runner_manifest"]["agent_id"], "portable_runner")
        self.assertEqual(bootstrap["wake_contract"], "bossforge-ai-runner-wake-v1")
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent.ModelGatewayAgentTests.test_created_agent_carries_agent_local_runner_bootstrap -v
```

Expected: FAIL with `KeyError: 'runtime'` or `KeyError: 'runner_bootstrap'`.

- [ ] **Step 3: Add runner manifest and bootstrap normalization**

In `core/agents/model_gateway_agent.py`, add imports:

```python
from core.runner import build_agent_runner_manifest, build_runner_bootstrap
```

In `_normalize_profile`, immediately before `normalized["runtime_lineage"] = ...`, add:

```python
        runtime = normalized.get("runtime")
        runtime_out = dict(runtime) if isinstance(runtime, dict) else {}
        runner_manifest = runtime_out.get("bossforge_ai_runner")
        if not isinstance(runner_manifest, dict):
            runner_manifest = build_agent_runner_manifest(key)
        runtime_out["bossforge_ai_runner"] = runner_manifest
        normalized["runtime"] = runtime_out
        normalized["runner_bootstrap"] = build_runner_bootstrap(key, runner_manifest)
```

- [ ] **Step 4: Run Model Gateway tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent -v
```

Expected: all Model Gateway tests pass.

- [ ] **Step 5: Commit exact Task 3 files**

```powershell
git add core/agents/model_gateway_agent.py tests/test_model_gateway_agent.py
git commit -m "feat: bootstrap agent-local AI runners"
```

### Task 4: Publish RuneForge Gifted Template Metadata

**Files:**
- Modify: `modules/runeforge_provider/runeforge_agent.profile.json`
- Modify: `modules/runeforge_provider/provider_manifest.json`
- Create or Modify: `tests/test_runeforge_runner_metadata.py`

- [ ] **Step 1: Add failing RuneForge metadata tests**

Create `tests/test_runeforge_runner_metadata.py`:

```python
import json
import unittest
from pathlib import Path

from core.runner import GIFTED_TEMPLATE_VERSION, RUNEFORGE_AGENT_ID, validate_agent_runner_manifest


class RuneForgeRunnerMetadataTests(unittest.TestCase):
    def test_runeforge_profile_declares_personalized_origin_runner(self) -> None:
        profile = json.loads(Path("modules/runeforge_provider/runeforge_agent.profile.json").read_text(encoding="utf-8"))
        runner = profile["runtime"]["bossforge_ai_runner"]
        self.assertEqual(runner["agent_id"], RUNEFORGE_AGENT_ID)
        self.assertEqual(runner["runner_role"], "personalized_origin")
        self.assertEqual(runner["source_template"]["ancestor_id"], "")
        self.assertFalse(runner["depends_on_runeforge_online"])
        validate_agent_runner_manifest(runner)

    def test_provider_manifest_publishes_gifted_template_reference(self) -> None:
        manifest = json.loads(Path("modules/runeforge_provider/provider_manifest.json").read_text(encoding="utf-8"))
        gifted = manifest["gifted_runtime_template"]
        self.assertEqual(gifted["gifted_by"], RUNEFORGE_AGENT_ID)
        self.assertEqual(gifted["version"], GIFTED_TEMPLATE_VERSION)
        self.assertTrue(gifted["signature"])
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_runeforge_runner_metadata -v
```

Expected: FAIL with `KeyError: 'bossforge_ai_runner'`.

- [ ] **Step 3: Generate signed metadata into provider files**

Run this deterministic script:

```powershell
$script = @'
import json
from pathlib import Path

from core.runner import build_runeforge_origin_manifest, build_signed_gifted_template
from core.schemas.agent_schema import normalize_agent_profile

profile_path = Path("modules/runeforge_provider/runeforge_agent.profile.json")
provider_path = Path("modules/runeforge_provider/provider_manifest.json")

profile = json.loads(profile_path.read_text(encoding="utf-8"))
normalized = normalize_agent_profile("runeforge", profile)
normalized["runtime"]["bossforge_ai_runner"] = build_runeforge_origin_manifest()
profile_path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")

provider = json.loads(provider_path.read_text(encoding="utf-8"))
template = build_signed_gifted_template()
provider["gifted_runtime_template"] = {
    "template_id": template["template_id"],
    "version": template["version"],
    "gifted_by": template["gifted_by"],
    "runner_kind": template["runner_kind"],
    "contract_version": template["contract_version"],
    "signature": template["signature"],
}
provider_path.write_text(json.dumps(provider, indent=2) + "\n", encoding="utf-8")
'@
$script | .\.venv\Scripts\python.exe -
```

- [ ] **Step 4: Run RuneForge metadata tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_runeforge_runner_metadata -v
```

Expected: `Ran 2 tests` and `OK`.

- [ ] **Step 5: Commit exact Task 4 files**

```powershell
git add modules/runeforge_provider/runeforge_agent.profile.json modules/runeforge_provider/provider_manifest.json tests/test_runeforge_runner_metadata.py
git commit -m "docs: publish RuneForge gifted runner metadata"
```

### Task 5: Update Stage 2 Documentation And Verification

**Files:**
- Modify: `docs/bossforge_ai_runner_todo.md`
- Modify: `docs/AgentForge_readme.md`
- Modify: `docs/agents_bossgate_agentforge_schema_guide.txt`

- [ ] **Step 1: Update Stage 2 tracker**

In `docs/bossforge_ai_runner_todo.md`, replace the Stage 2 checklist with:

```markdown
## Stage 2: Gifted Portable AI Runner

- [x] Extract the portable BossForgeOS runner contract from RuneForge-specific provider behavior.
- [x] Keep RuneForge personalized while recording her gifted runtime as direct ancestor for descendants.
- [ ] Package each agent runtime and complete private model weights independently.
- [x] Add signed gifted-template metadata and detached per-agent runner bootstrap manifests.
- [ ] Verification: run the Stage 2 and BossGate regression suites before closing this stage.
```

- [ ] **Step 2: Update AgentForge policy**

In `docs/AgentForge_readme.md`:

1. Change current policy version from `v1.12.0` to `v1.13.0`.
2. Add this paragraph to `## Sealed Agent Capsule Foundation`:

```markdown
- Stage 2 adds the BossForgeOS AI runner contract. RuneForge publishes a signed gifted runtime template, while descendants receive detached per-agent runner manifests and bootstrap payloads that do not require RuneForge to remain online.
```

3. Add changelog and impacted-module lines:

```markdown
- v1.13.0 (2026-06-06): added the Stage 2 gifted portable runner contract: signed neutral template metadata, RuneForge personalized-origin manifest, descendant detached runner manifests, and per-agent runner bootstrap metadata.
- Impacted modules for v1.13.0: `core/runner/bossforge_ai_runner.py`, `core/schemas/agent_schema.py`, `core/agents/model_gateway_agent.py`, `modules/runeforge_provider/runeforge_agent.profile.json`, `modules/runeforge_provider/provider_manifest.json`
```

- [ ] **Step 3: Append Stage 2 current-reality guide section**

Append to `docs/agents_bossgate_agentforge_schema_guide.txt`:

```text

====================================================================
18) Gifted Portable AI Runner (Implemented Stage 2 Slice)
====================================================================
Stage 2 establishes the metadata contract for agent-local BossForgeOS AI runners.

Implemented:
- neutral BossForgeOS AI runner template metadata
- deterministic Stage 2 template signing and verification
- RuneForge personalized-origin runner manifest
- detached descendant runner manifests with sealed RuneForge ancestry
- per-agent runner bootstrap payloads bound to capsule vault descriptors
- RuneForge provider gifted runtime template reference

Not yet implemented:
- process supervision for waking the runner
- complete model-weight copying into private model vaults
- memory-vault-backed learning
- dream training and signed checkpoints
- full move-only BossGate transport
```

- [ ] **Step 4: Run full Stage 2 verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile core/runner/bossforge_ai_runner.py core/schemas/agent_schema.py core/agents/model_gateway_agent.py
.\.venv\Scripts\python.exe -m unittest tests.test_bossforge_ai_runner tests.test_agent_capsule_schema tests.test_model_gateway_agent tests.test_runeforge_runner_metadata tests.test_agentforge_service -v
.\.venv\Scripts\python.exe -m unittest tests.test_bossgate_agent tests.test_bossgate_authorization tests.test_bossgate_connector -v
git diff --check
```

Expected:
- compile exits `0`
- Stage 2 focused suites pass
- BossGate regression suite passes
- `git diff --check` exits `0` except allowed CRLF warnings from Windows checkout

- [ ] **Step 5: Stamp tracker verification**

Replace the unchecked Stage 2 verification line with:

```markdown
- [x] Verification: passed on 2026-06-06 with `python -m unittest tests.test_bossforge_ai_runner tests.test_agent_capsule_schema tests.test_model_gateway_agent tests.test_runeforge_runner_metadata tests.test_agentforge_service -v` and BossGate regression suite.
```

- [ ] **Step 6: Commit exact documentation files**

```powershell
git add docs/bossforge_ai_runner_todo.md docs/AgentForge_readme.md docs/agents_bossgate_agentforge_schema_guide.txt
git commit -m "docs: record AI runner stage2 runner contract"
```
