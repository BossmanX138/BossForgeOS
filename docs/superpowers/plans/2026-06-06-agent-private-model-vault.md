# Agent Private Model Vault Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every newly forged LLM-enabled agent own a complete, verified, encrypted model package that is created atomically and bound to its capsule and portable runner.

**Architecture:** Add a focused `core.model_vault` package for source inspection, streaming AES-256-GCM chunk encryption, package verification, ownership isolation, and sealed descriptors. AgentForge calls the same local creation service in integrated and standalone modes; a trusted entitlement provider restricts unsubscribed standalone creation to local-only Skilled and Normalized agents, while subscribed standalone may unlock Prime and travel-capable creation.

**Tech Stack:** Python 3.11+, `cryptography.hazmat.primitives.ciphers.aead.AESGCM`, `hashlib`, `json`, `pathlib`, `shutil`, `secrets`, `unittest`, existing AgentForge, Model Gateway, runner, and capsule contracts.

---

## Scope Boundaries

Included:
- Immediate packaging during AgentForge creation.
- Complete source-tree inventory with model-category validation.
- Adapter plus resolved base-model packaging.
- Bounded streaming encryption and verification.
- Atomic activation and fail-closed cleanup.
- Unique package ownership and runner/capsule binding.
- Focused tests, regression tests, and documentation updates.
- Standalone creation without running BossForgeOS services.
- Deny-by-default standalone subscription enforcement.

Deferred:
- Production HSM or operating-system key custody.
- Runtime decryption/mounting and model loading from the vault.
- Dream-created weight checkpoints.
- BossGate network transfer and source retirement.
- Billing, checkout, subscription issuance, and production entitlement-server
  implementation.

## File Map

- Create `core/model_vault/__init__.py`: public model-vault API.
- Create `core/model_vault/private_model_vault.py`: source inspection, key-provider contract, streaming encryption, manifests, verification, activation, cleanup, and descriptor validation.
- Create `tests/test_private_model_vault.py`: focused package, security, tamper, adapter, streaming, atomicity, and isolation tests.
- Create `modules/agentforge/entitlements.py`: trusted deployment-context and
  subscription capability decisions.
- Create `tests/test_agentforge_entitlements.py`: standalone/integrated,
  subscribed/unsubscribed, expiry, and payload-bypass tests.
- Modify `core/runner/bossforge_ai_runner.py`: add and validate the sealed private-model descriptor in runner bootstrap metadata.
- Modify `tests/test_bossforge_ai_runner.py`: descriptor binding and tamper tests.
- Modify `core/schemas/agent_capsule.py`: bind the model vault ciphertext reference to the package descriptor.
- Modify `tests/test_agent_capsule_schema.py`: capsule binding and disclosure tests.
- Modify `core/agents/model_gateway_agent.py`: configure model-vault storage, package before publication, and roll back on failure.
- Modify `tests/test_model_gateway_agent.py`: successful creation, failed creation, and sibling isolation tests.
- Modify `modules/agentforge/service.py`: accept `model_source_path`, optional `model_base_source_path`, and runtime requirements.
- Modify `tests/test_agentforge_service.py`: payload forwarding and creation failure tests.
- Modify `ui/control_hall.py`: include model source fields already present in the creation form, or add minimal fields if absent.
- Modify `modules/agentforge/manifest.json`: declare standalone local-only
  defaults and entitlement-gated capabilities.
- Modify `docs/bossforge_ai_runner_todo.md`: mark the remaining Stage 2 package item complete after verification.
- Modify `docs/AgentForge_readme.md`, `docs/agentforge_requirements.md`, `docs/agentmaker_requirements.md`, `docs/agents_bossgate_agentforge_schema_guide.txt`, `docs/bossgate_connector.md`, and `docs/bossgate_protocol.md`: document the implemented package and future travel boundary.

### Task 1: Build Source Inspection And Deterministic Inventory

**Files:**
- Create: `core/model_vault/__init__.py`
- Create: `core/model_vault/private_model_vault.py`
- Create: `tests/test_private_model_vault.py`

- [ ] **Step 1: Write failing source-inspection tests**

Create test helpers and tests in `tests/test_private_model_vault.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from core.model_vault.private_model_vault import inspect_model_source


def write_complete_model(root: Path, marker: bytes = b"weights") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.json").write_text('{"model_type":"qwen2"}', encoding="utf-8")
    (root / "tokenizer.json").write_text('{"version":"1.0"}', encoding="utf-8")
    (root / "generation_config.json").write_text('{"max_new_tokens":128}', encoding="utf-8")
    (root / "model.safetensors").write_bytes(marker)
    (root / "requirements.txt").write_text("transformers\n", encoding="utf-8")


class PrivateModelVaultTests(unittest.TestCase):
    def test_inspector_returns_deterministic_complete_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write_complete_model(source)
            inspected = inspect_model_source(source)
            paths = [item["relative_path"] for item in inspected["files"]]
            self.assertEqual(paths, sorted(paths))
            self.assertEqual(
                set(inspected["required_categories"]),
                {"weights", "tokenizer", "model_config"},
            )
            self.assertIn("generation_config", inspected["present_categories"])

    def test_inspector_rejects_missing_weights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write_complete_model(source)
            (source / "model.safetensors").unlink()
            with self.assertRaisesRegex(ValueError, "model weights"):
                inspect_model_source(source)

    def test_inspector_rejects_missing_declared_shard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write_complete_model(source)
            (source / "model.safetensors").unlink()
            index = {"weight_map": {"layer": "model-00001-of-00002.safetensors"}}
            (source / "model.safetensors.index.json").write_text(json.dumps(index), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "declared shard"):
                inspect_model_source(source)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_model_vault -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.model_vault'`.

- [ ] **Step 3: Implement source inspection**

In `core/model_vault/private_model_vault.py`, implement:

```python
MODEL_VAULT_SCHEMA_VERSION = "1.0"
WEIGHT_NAMES = {
    "model.safetensors",
    "model.safetensors.index.json",
    "pytorch_model.bin",
    "pytorch_model.bin.index.json",
}


def _resolve_inside(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=True)
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f"model source path escapes root: {candidate}")
    return resolved


def _category(relative_path: str) -> str:
    name = Path(relative_path).name.lower()
    if name.endswith((".safetensors", ".bin", ".gguf")) or name.endswith(".index.json"):
        return "weights"
    if name.startswith(("tokenizer", "vocab", "merges", "special_tokens")):
        return "tokenizer"
    if name == "config.json":
        return "model_config"
    if name == "generation_config.json":
        return "generation_config"
    if name.startswith("adapter_"):
        return "adapter"
    if name in {"requirements.txt", "runtime_requirements.json"}:
        return "runtime_requirements"
    return "supporting"


def inspect_model_source(source_root: str | Path) -> dict[str, object]:
    root = Path(source_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("model source must be a directory")
    files = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if path.is_symlink():
            raise ValueError(f"model source links are not allowed: {path}")
        if not path.is_file():
            continue
        resolved = _resolve_inside(root, path)
        relative = resolved.relative_to(root).as_posix()
        files.append(
            {
                "source_path": str(resolved),
                "relative_path": relative,
                "size": resolved.stat().st_size,
                "category": _category(relative),
            }
        )
    present = {item["category"] for item in files}
    for required, message in (
        ("weights", "model weights are required"),
        ("tokenizer", "tokenizer assets are required"),
        ("model_config", "model configuration is required"),
    ):
        if required not in present:
            raise ValueError(message)
    # Parse each supported weight index and reject absent declared shards.
    _validate_declared_shards(root, files)
    return {
        "source_root": str(root),
        "files": files,
        "present_categories": sorted(present),
        "required_categories": ["model_config", "tokenizer", "weights"],
        "total_size": sum(int(item["size"]) for item in files),
    }
```

Add `_validate_declared_shards()` to parse `model.safetensors.index.json` and
`pytorch_model.bin.index.json`, normalize every `weight_map` value, and verify
the referenced file resolves inside `root` and exists.

Export `inspect_model_source` and `MODEL_VAULT_SCHEMA_VERSION` from
`core/model_vault/__init__.py`.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_model_vault -v
```

Expected: the three inspection tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add core/model_vault/__init__.py core/model_vault/private_model_vault.py tests/test_private_model_vault.py
git commit -m "feat: inspect complete private model sources"
```

### Task 2: Resolve Adapter Sources Into Self-Contained Inventories

**Files:**
- Modify: `core/model_vault/private_model_vault.py`
- Modify: `tests/test_private_model_vault.py`

- [ ] **Step 1: Write failing adapter tests**

Add:

```python
    def test_adapter_inventory_includes_complete_base_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base"
            adapter = Path(tmp) / "adapter"
            write_complete_model(base, b"base-weights")
            adapter.mkdir()
            (adapter / "adapter_config.json").write_text(
                json.dumps({"base_model_name_or_path": str(base)}),
                encoding="utf-8",
            )
            (adapter / "adapter_model.safetensors").write_bytes(b"adapter")
            inspected = inspect_model_source(adapter)
            roots = {item["source_group"] for item in inspected["files"]}
            self.assertEqual(roots, {"adapter", "base"})

    def test_adapter_inventory_rejects_unresolved_base_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = Path(tmp) / "adapter"
            adapter.mkdir()
            (adapter / "adapter_config.json").write_text(
                '{"base_model_name_or_path":"missing"}',
                encoding="utf-8",
            )
            (adapter / "adapter_model.safetensors").write_bytes(b"adapter")
            with self.assertRaisesRegex(ValueError, "base model"):
                inspect_model_source(adapter)
```

- [ ] **Step 2: Run adapter tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_model_vault.PrivateModelVaultTests.test_adapter_inventory_includes_complete_base_model tests.test_private_model_vault.PrivateModelVaultTests.test_adapter_inventory_rejects_unresolved_base_model -v
```

Expected: FAIL because adapter/base composition is not implemented.

- [ ] **Step 3: Implement adapter/base composition**

Change the inspector signature to:

```python
def inspect_model_source(
    source_root: str | Path,
    base_source_root: str | Path | None = None,
) -> dict[str, object]:
```

Detect adapter-only sources using `adapter_config.json` plus
`adapter_model.safetensors`. Resolve the base from `base_source_root` first,
then from `base_model_name_or_path` only when it resolves to a local directory.
Inventory adapter paths under `adapter/<relative_path>` and base paths under
`base/<relative_path>`, tagging every item with `source_group`. Validate the
base with the same tokenizer/config/weight requirements.

- [ ] **Step 4: Run all vault tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_model_vault -v
```

Expected: all inspection and adapter tests pass.

- [ ] **Step 5: Commit Task 2**

```powershell
git add core/model_vault/private_model_vault.py tests/test_private_model_vault.py
git commit -m "feat: package adapter models with their base"
```

### Task 3: Add Streaming Authenticated Encryption And Package Verification

**Files:**
- Modify: `core/model_vault/private_model_vault.py`
- Modify: `core/model_vault/__init__.py`
- Modify: `tests/test_private_model_vault.py`

- [ ] **Step 1: Write failing encryption and streaming tests**

Add tests that call:

```python
package = build_private_model_package(
    agent_id="wayfinder",
    source_root=source,
    vault_root=Path(tmp) / "vaults",
    secret_key="wayfinder-secret",
    key_ref="agent-model-key:wayfinder",
    chunk_size=4,
)
self.assertTrue(package["verified"])
self.assertNotIn(b"weights", b"".join(path.read_bytes() for path in package_path.rglob("*.chunk")))
verified = verify_private_model_package(package_path, "wayfinder-secret")
self.assertEqual(verified["owner_agent_id"], "wayfinder")
```

Add a `TrackingReader` patch around `Path.open` and assert no binary
`read()` request exceeds the configured chunk size. Add tamper cases for
ciphertext bytes, nonce, owner ID, relative path, and chunk index; each must
raise `ValueError`.

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_model_vault -v
```

Expected: FAIL because package creation and verification do not exist.

- [ ] **Step 3: Implement streaming encrypted packages**

Add these public interfaces:

```python
def build_private_model_package(
    *,
    agent_id: str,
    source_root: str | Path,
    vault_root: str | Path,
    secret_key: str,
    key_ref: str,
    base_source_root: str | Path | None = None,
    runtime_requirements: dict[str, object] | None = None,
    chunk_size: int = 4 * 1024 * 1024,
) -> dict[str, object]:
    ...


def verify_private_model_package(
    package_root: str | Path,
    secret_key: str,
) -> dict[str, object]:
    ...
```

Implementation requirements:

1. Normalize `agent_id` to lowercase and reject empty or path-like IDs.
2. Derive the AES key with `hashlib.sha256(secret_key.encode("utf-8")).digest()`.
3. Create `<vault_root>/.staging/<agent-id>-<package-id>`.
4. Read each source file using `source.open("rb").read(chunk_size)`.
5. Encrypt each chunk with a fresh 12-byte nonce and `AESGCM.encrypt`.
6. Canonicalize associated data as compact sorted JSON containing
   `package_id`, `owner_agent_id`, `relative_path`, `chunk_index`, and
   `plaintext_size`.
7. Store each chunk as compact JSON containing Base64 nonce and ciphertext.
8. Record plaintext/ciphertext SHA-256 values and sizes in the sealed manifest.
9. Encrypt the complete manifest using AES-GCM into `package.manifest.enc`.
10. Write the sparse `package.attestation.json`.
11. Verify every staged chunk before atomic activation.
12. Rename staging to `<vault_root>/<agent-id>/<package-id>`.
13. Return the sealed descriptor, not the plaintext manifest.

Use `try/finally` to remove the operation's staging directory after any
failure. Never remove the source tree or another package directory.

- [ ] **Step 4: Run focused package tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_model_vault -v
```

Expected: encryption, streaming, round-trip, and tamper tests pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add core/model_vault/__init__.py core/model_vault/private_model_vault.py tests/test_private_model_vault.py
git commit -m "feat: encrypt agent model packages in streaming chunks"
```

### Task 4: Enforce Atomicity, Disk Preflight, And Sibling Isolation

**Files:**
- Modify: `core/model_vault/private_model_vault.py`
- Modify: `tests/test_private_model_vault.py`

- [ ] **Step 1: Write failing atomicity and isolation tests**

Add tests that:

1. Patch `shutil.disk_usage` below the required estimate and expect
   `ValueError("insufficient disk space")` before any staging chunks exist.
2. Patch `AESGCM.encrypt` to fail on the second chunk and assert no active
   package exists.
3. Build two agents from identical source bytes and assert different package
   IDs, paths, nonces, key references, and ciphertext.
4. Copy an attestation from agent A into agent B and assert verification fails
   ownership/path validation.
5. Create a symlink or junction inside the source when supported and assert it
   is rejected; skip only when the operating system denies link creation.

- [ ] **Step 2: Run the new tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_model_vault -v
```

Expected: the new disk, cleanup, and isolation tests fail.

- [ ] **Step 3: Implement preflight and ownership registry checks**

Before staging:

```python
required_bytes = max(inventory["total_size"] * 2, inventory["total_size"] + 16 * 1024 * 1024)
free_bytes = shutil.disk_usage(vault_root).free
if free_bytes < required_bytes:
    raise ValueError("insufficient disk space for encrypted model package")
```

Add `validate_private_model_descriptor()` and verify:

- descriptor owner equals the expected agent;
- resolved package path is beneath `<vault_root>/<agent-id>`;
- attestation owner/package ID matches the descriptor;
- active package directory does not already exist;
- no symlink, hard-link alias, or reparse-point escape is accepted;
- `key_ref` is non-empty and bound to the expected owner by the provided key
  registry callback.

- [ ] **Step 4: Run all vault tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_model_vault -v
```

Expected: all vault tests pass with platform-specific link tests either PASS
or explicitly SKIP.

- [ ] **Step 5: Commit Task 4**

```powershell
git add core/model_vault/private_model_vault.py tests/test_private_model_vault.py
git commit -m "feat: enforce atomic private model ownership"
```

### Task 5: Bind The Package To Runner And Capsule Contracts

**Files:**
- Modify: `core/runner/bossforge_ai_runner.py`
- Modify: `core/schemas/agent_capsule.py`
- Modify: `tests/test_bossforge_ai_runner.py`
- Modify: `tests/test_agent_capsule_schema.py`

- [ ] **Step 1: Write failing binding tests**

Add tests that create a descriptor:

```python
descriptor = {
    "schema_version": "1.0",
    "package_id": "pkg-123",
    "owner_agent_id": "wayfinder",
    "ciphertext_ref": "private_models/wayfinder/pkg-123",
    "attestation_sha256": "a" * 64,
    "key_ref": "agent-model-key:wayfinder",
    "verified": True,
}
```

Assert `build_runner_bootstrap("wayfinder", manifest, descriptor)` includes
it under `private_model_package`; assert owner/package tampering is rejected.
Assert `build_capsule_manifest()` places `ciphertext_ref` in
`capsule["vaults"]["model"]` and authenticated non-hidden profile views do not
expose the descriptor.

- [ ] **Step 2: Run binding tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bossforge_ai_runner tests.test_agent_capsule_schema -v
```

Expected: FAIL because the descriptor is not part of either contract.

- [ ] **Step 3: Implement binding validators**

Change:

```python
def build_runner_bootstrap(
    agent_id: str,
    manifest: dict[str, Any],
    private_model_package: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

When supplied, validate the descriptor and require its owner to match the
runner agent ID. Update `validate_runner_bootstrap()` to validate the same
binding.

In `build_capsule_manifest()`, read
`profile["runtime"]["private_model_package"]` when present and use its
`ciphertext_ref` for the model vault. In `validate_capsule_manifest()`, require
the model vault reference to match the runtime descriptor when supplied.
Add `private_model_package` to `_SEALED_PROFILE_VIEW_FIELDS`.

- [ ] **Step 4: Run runner and capsule tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bossforge_ai_runner tests.test_agent_capsule_schema -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 5**

```powershell
git add core/runner/bossforge_ai_runner.py core/schemas/agent_capsule.py tests/test_bossforge_ai_runner.py tests/test_agent_capsule_schema.py
git commit -m "feat: bind private models to runner capsules"
```

### Task 6: Package Models During Model Gateway Creation

**Files:**
- Modify: `core/agents/model_gateway_agent.py`
- Modify: `tests/test_model_gateway_agent.py`

- [ ] **Step 1: Write failing creation transaction tests**

Add tests using `write_complete_model()` or a local equivalent:

```python
created = agent.create_agent_profile(
    name="wayfinder",
    endpoint="ollama",
    system_prompt="Navigate.",
    temperature=0.2,
    max_tokens=600,
    model_source_path=str(source),
)
self.assertTrue(created["ok"])
descriptor = created["agent"]["runtime"]["private_model_package"]
self.assertTrue(descriptor["verified"])
self.assertEqual(descriptor["owner_agent_id"], "wayfinder")
self.assertEqual(
    created["agent"]["capsule"]["vaults"]["model"]["ciphertext_ref"],
    descriptor["ciphertext_ref"],
)
```

Add failure tests proving:

- missing/incomplete source returns `ok=False`;
- no profile is persisted;
- no presence event or memory registration occurs;
- activated package is removed if gate-file creation or profile save fails;
- two agents from one source receive distinct descriptors and ciphertext.

- [ ] **Step 2: Run creation tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent -v
```

Expected: new tests fail because creation has no model-source parameters.

- [ ] **Step 3: Integrate the package transaction**

Extend public and private creation signatures with:

```python
model_source_path: str | None = None,
model_base_source_path: str | None = None,
model_runtime_requirements: Dict[str, Any] | None = None,
```

Initialize:

```python
self.private_model_root = self.bus.root / "state" / "private_models"
self.private_model_root.mkdir(parents=True, exist_ok=True)
```

For every final `llm_enabled` agent, require `model_source_path`, derive the
development key from `f"{self.node_id}:{key}:private-model-v1"`, and use
`key_ref=f"node:{self.node_id}:agent:{key}:private-model-v1"`.

Build the package before `_ensure_agent_gate_file()`. Store its descriptor at
`profile["runtime"]["private_model_package"]`, then re-normalize so runner and
capsule bindings are rebuilt. Wrap all later creation operations in a
transaction that removes only the newly activated package if profile
publication fails.

Keep loading existing profiles backward compatible: profiles created before
this stage may load without a package descriptor, but new LLM-agent creation
must fail closed without one.

- [ ] **Step 4: Run Model Gateway tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent -v
```

Expected: all Model Gateway tests pass after existing creation fixtures are
updated to provide tiny complete model sources where required.

- [ ] **Step 5: Commit Task 6**

```powershell
git add core/agents/model_gateway_agent.py tests/test_model_gateway_agent.py
git commit -m "feat: forge agents with private model packages"
```

### Task 7: Enforce Standalone AgentForge Entitlements

**Files:**
- Create: `modules/agentforge/entitlements.py`
- Create: `tests/test_agentforge_entitlements.py`
- Modify: `modules/agentforge/manifest.json`

- [ ] **Step 1: Write failing entitlement-policy tests**

Create `tests/test_agentforge_entitlements.py`:

```python
import unittest
from datetime import datetime, timedelta, timezone

from modules.agentforge.entitlements import (
    AgentForgeRuntimeContext,
    StaticEntitlementProvider,
    authorize_creation_request,
)


class AgentForgeEntitlementTests(unittest.TestCase):
    def test_unsubscribed_standalone_rejects_prime(self) -> None:
        context = AgentForgeRuntimeContext(mode="standalone", installation_id="local-1")
        provider = StaticEntitlementProvider(subscribed=False)
        with self.assertRaisesRegex(PermissionError, "Prime"):
            authorize_creation_request(
                context=context,
                entitlement_provider=provider,
                agent_class="prime",
                bossgate_enabled=False,
                travel_capable=False,
            )

    def test_unsubscribed_standalone_forces_local_only(self) -> None:
        context = AgentForgeRuntimeContext(mode="standalone", installation_id="local-1")
        decision = authorize_creation_request(
            context=context,
            entitlement_provider=StaticEntitlementProvider(subscribed=False),
            agent_class="skilled",
            bossgate_enabled=True,
            travel_capable=True,
        )
        self.assertFalse(decision["bossgate_enabled"])
        self.assertFalse(decision["travel_capable"])
        self.assertEqual(decision["creation_authority"], "standalone_local")

    def test_subscribed_standalone_allows_prime_and_travel(self) -> None:
        context = AgentForgeRuntimeContext(mode="standalone", installation_id="local-1")
        decision = authorize_creation_request(
            context=context,
            entitlement_provider=StaticEntitlementProvider(
                subscribed=True,
                capabilities={"agent.create.prime", "agent.create.travel"},
            ),
            agent_class="prime",
            bossgate_enabled=True,
            travel_capable=True,
        )
        self.assertTrue(decision["bossgate_enabled"])
        self.assertTrue(decision["travel_capable"])
        self.assertEqual(decision["creation_authority"], "standalone_subscribed")

    def test_expired_entitlement_is_unsubscribed(self) -> None:
        expired = datetime.now(timezone.utc) - timedelta(minutes=1)
        provider = StaticEntitlementProvider(
            subscribed=True,
            capabilities={"agent.create.prime", "agent.create.travel"},
            expires_at=expired,
        )
        context = AgentForgeRuntimeContext(mode="standalone", installation_id="local-1")
        with self.assertRaises(PermissionError):
            authorize_creation_request(
                context=context,
                entitlement_provider=provider,
                agent_class="prime",
                bossgate_enabled=True,
                travel_capable=True,
            )

    def test_integrated_mode_uses_bossforgeos_authority(self) -> None:
        context = AgentForgeRuntimeContext(mode="integrated", installation_id="bossforgeos")
        decision = authorize_creation_request(
            context=context,
            entitlement_provider=StaticEntitlementProvider(subscribed=False),
            agent_class="prime",
            bossgate_enabled=True,
            travel_capable=True,
        )
        self.assertEqual(decision["creation_authority"], "bossforgeos")
```

- [ ] **Step 2: Run entitlement tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agentforge_entitlements -v
```

Expected: FAIL with `ModuleNotFoundError` for
`modules.agentforge.entitlements`.

- [ ] **Step 3: Implement deny-by-default entitlement enforcement**

Create immutable runtime context and entitlement decision types. Implement:

```python
@dataclass(frozen=True)
class AgentForgeRuntimeContext:
    mode: str
    installation_id: str


class EntitlementProvider(Protocol):
    def resolve(self, context: AgentForgeRuntimeContext) -> dict[str, Any]:
        ...


def authorize_creation_request(
    *,
    context: AgentForgeRuntimeContext,
    entitlement_provider: EntitlementProvider,
    agent_class: str,
    bossgate_enabled: bool,
    travel_capable: bool,
) -> dict[str, Any]:
    ...
```

Rules:

1. Accept runtime modes only from the constructed context, never payload.
2. Integrated mode returns BossForgeOS authority and preserves requested
   capabilities for later schema/security checks.
3. Standalone with absent, invalid, unverified, or expired entitlement is
   unsubscribed.
4. Unsubscribed standalone rejects `prime`, allows `skilled` and `normalized`,
   and returns both travel flags as `False`.
5. Subscribed standalone requires `agent.create.prime` for Prime and
   `agent.create.travel` for either travel flag.
6. Return `creation_authority` for sealed profile policy metadata.

`StaticEntitlementProvider` exists for tests and local development only.
The default production provider returns unsubscribed until a real subscription
validator is configured.

Update `modules/agentforge/manifest.json` with:

```json
"standalone_policy": {
  "default_tier": "local",
  "allowed_agent_classes": ["skilled", "normalized"],
  "prime_requires": "agent.create.prime",
  "travel_requires": "agent.create.travel"
}
```

- [ ] **Step 4: Run entitlement tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agentforge_entitlements -v
```

Expected: all five entitlement tests pass.

- [ ] **Step 5: Commit Task 7**

```powershell
git add modules/agentforge/entitlements.py modules/agentforge/manifest.json tests/test_agentforge_entitlements.py
git commit -m "feat: enforce standalone AgentForge entitlements"
```

### Task 8: Wire AgentForge Payloads, Runtime Mode, And Creation UI

**Files:**
- Modify: `modules/agentforge/service.py`
- Modify: `tests/test_agentforge_service.py`
- Modify: `ui/control_hall.py`

- [ ] **Step 1: Write failing AgentForge forwarding tests**

Patch the gateway and call:

```python
result = service.create_agent_profile(
    {
        "name": "wayfinder",
        "endpoint": "ollama",
        "model_source_path": "F:/models/qwen",
        "model_base_source_path": "",
        "model_runtime_requirements": {"transformers": "local"},
    }
)
```

Assert the gateway receives those three named arguments unchanged. Add tests
that:

- runtime mode is injected through service configuration, not accepted from
  payload keys;
- unsubscribed standalone rejects Prime even when a modified payload claims
  `subscribed=true` or `mode=integrated`;
- unsubscribed standalone forces both travel flags off;
- subscribed standalone forwards allowed Prime/travel requests;
- an LLM-enabled request without `model_source_path` returns a clear failure.

- [ ] **Step 2: Run AgentForge tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agentforge_service -v
```

Expected: forwarding assertions fail.

- [ ] **Step 3: Forward payload fields and expose them in Control Hall**

In `modules/agentforge/service.py`, parse:

```python
model_source_path = str(payload.get("model_source_path", "")).strip() or None
model_base_source_path = str(payload.get("model_base_source_path", "")).strip() or None
requirements_raw = payload.get("model_runtime_requirements")
model_runtime_requirements = requirements_raw if isinstance(requirements_raw, dict) else None
```

Pass them as named arguments to `gateway.create_agent_profile()`.

Add a configured runtime-context provider:

```python
def _runtime_context() -> AgentForgeRuntimeContext:
    mode = os.getenv("AGENTFORGE_RUNTIME_MODE", "standalone").strip().lower()
    installation_id = os.getenv("AGENTFORGE_INSTALLATION_ID", "local").strip()
    return AgentForgeRuntimeContext(mode=mode, installation_id=installation_id)
```

The integrated BossForgeOS adapter must explicitly set `integrated`; standalone
defaults to `standalone`. Call `authorize_creation_request()` before invoking
the local gateway object. Pass only the authorized class and travel flags.
Store `creation_authority` in sealed policy metadata.

The standalone path may instantiate shared core classes in-process, but tests
must prove it does not contact or require a running Model Gateway daemon,
BossGate service, RuneForge service, or BossForgeOS process.

In the AgentForge creation form and payload builder in `ui/control_hall.py`,
add:

- `Model source directory` required when LLM is enabled;
- `Adapter base-model directory` optional;
- helper text stating the source remains at the Forge while a complete
  encrypted agent-owned package is created immediately.
- standalone tier status and disabled Prime/travel controls when unsubscribed;
- an explanation that subscribed standalone unlocks those controls after a
  verified entitlement.

Service authorization remains authoritative when clients modify the form or
call the API directly.

- [ ] **Step 4: Run service and UI-adjacent tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agentforge_entitlements tests.test_agentforge_service tests.test_control_hall_model_routes -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 8**

```powershell
git add modules/agentforge/service.py tests/test_agentforge_service.py ui/control_hall.py tests/test_control_hall_model_routes.py
git commit -m "feat: select private models in AgentForge"
```

### Task 9: Update Documentation And Close Stage 2

**Files:**
- Modify: `docs/bossforge_ai_runner_todo.md`
- Modify: `docs/AgentForge_readme.md`
- Modify: `docs/agentforge_requirements.md`
- Modify: `docs/agentmaker_requirements.md`
- Modify: `docs/agents_bossgate_agentforge_schema_guide.txt`
- Modify: `docs/bossgate_connector.md`
- Modify: `docs/bossgate_protocol.md`

- [ ] **Step 1: Document the implemented boundary**

Document:

- every new LLM-enabled agent is packaged immediately;
- every package is encrypted, independently owned, and self-contained;
- adapter agents include their base model;
- the Forge source remains unchanged and is not an agent version;
- runtime decryption, dreams, and BossGate movement remain later stages;
- public and authenticated profile views do not disclose package contents.
- free standalone AgentForge creates only local Skilled/Normalized agents;
- subscribed standalone may unlock Prime and travel-capable creation;
- entitlement checks are service-side and deny by default.

- [ ] **Step 2: Run focused verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile core/model_vault/private_model_vault.py core/runner/bossforge_ai_runner.py core/schemas/agent_capsule.py core/agents/model_gateway_agent.py modules/agentforge/service.py
.\.venv\Scripts\python.exe -m unittest tests.test_private_model_vault tests.test_bossforge_ai_runner tests.test_agent_capsule_schema tests.test_model_gateway_agent tests.test_agentforge_entitlements tests.test_agentforge_service tests.test_control_hall_model_routes -v
```

Expected: compile exits `0`; all focused tests pass.

- [ ] **Step 3: Run BossGate regressions**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bossgate_agent tests.test_bossgate_authorization tests.test_bossgate_connector -v
git diff --check
```

Expected: BossGate tests pass and `git diff --check` exits `0` except harmless
Windows line-ending warnings.

- [ ] **Step 4: Stamp the completion tracker**

Change the remaining Stage 2 package item to:

```markdown
- [x] Package each agent runtime and complete private model weights independently.
```

Update the Stage 2 verification line with the exact commands and passing test
counts observed in Steps 2 and 3. Do not estimate counts.

- [ ] **Step 5: Commit documentation**

```powershell
git add docs/bossforge_ai_runner_todo.md docs/AgentForge_readme.md docs/agentforge_requirements.md docs/agentmaker_requirements.md docs/agents_bossgate_agentforge_schema_guide.txt docs/bossgate_connector.md docs/bossgate_protocol.md
git commit -m "docs: complete private model packaging stage"
```

### Task 10: Final Verification And Review

**Files:**
- Review all files changed by Tasks 1-8.

- [ ] **Step 1: Run the complete relevant suite**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_model_vault tests.test_bossforge_ai_runner tests.test_agent_capsule_schema tests.test_model_gateway_agent tests.test_agentforge_entitlements tests.test_agentforge_service tests.test_control_hall_model_routes tests.test_runeforge_runner_metadata tests.test_bossgate_agent tests.test_bossgate_authorization tests.test_bossgate_connector -v
```

Expected: all tests pass.

- [ ] **Step 2: Verify repository hygiene**

```powershell
git diff --check
git status --short
git log -10 --oneline
```

Expected: no whitespace errors; only intentional task files are part of the
new commits; pre-existing unrelated workspace changes remain untouched.

- [ ] **Step 3: Request code review**

Use `superpowers:requesting-code-review` with the design, this plan, and the
Task 1-9 commit range. Address only findings that are relevant to this stage.

- [ ] **Step 4: Re-run verification after review fixes**

Repeat Steps 1 and 2. Record the final evidence in
`docs/bossforge_ai_runner_todo.md` if review changes alter test counts.
