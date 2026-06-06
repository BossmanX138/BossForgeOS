# Agent Private Memory Vault Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every agent an independently owned encrypted memory vault with immediate event sealing, live indexes, verified four-hour commits, selective recall, and fail-closed migration from all existing plaintext memory stores.

**Architecture:** Add a focused `core/memory_vault` package that owns cryptography, journals, indexes, commits, recall, descriptors, and migration. Model Gateway, the legacy `AgentMemory` API, and RuneForge become clients or compatibility adapters; none remains an authoritative plaintext memory store. Runner and capsule schemas bind the verified memory descriptor while all public and authenticated profile views redact nested memory details.

**Tech Stack:** Python 3.11+, `cryptography` AES-256-GCM, HMAC-SHA256 development attestations, deterministic gzip, JSON/JSONL, SQLite migration reads, `unittest`, atomic `pathlib.Path.replace`.

---

## File Map

**Create**

- `core/memory_vault/__init__.py` - stable public exports for vault construction, append, commit, recall, descriptor validation, and migration.
- `core/memory_vault/crypto.py` - canonical JSON, key derivation, AES-GCM envelopes, hashes, and HMAC attestations.
- `core/memory_vault/events.py` - normalized event schema, token/topic extraction, relationship extraction, and deterministic importance classification.
- `core/memory_vault/private_memory_vault.py` - per-agent vault ownership, append-only encrypted journal, encrypted live indexes, verified commit, and recall.
- `core/memory_vault/migration.py` - inventory, normalization, verification, attestation, and retirement for SQLite, `AgentMemory` JSON, and RuneForge JSON.
- `modules/runeforge_provider/memory_adapter.py` - RuneForge-specific conversion between session/user state and RuneForge's private vault.
- `tests/test_private_memory_vault.py` - journal, index, commit, recall, ownership, corruption, and trigger tests.
- `tests/test_memory_vault_migration.py` - all three legacy-source migrations and fail-closed retirement tests.
- `tests/test_runeforge_memory_adapter.py` - RuneForge read/write compatibility and plaintext-retirement tests.

**Modify**

- `core/runner/bossforge_ai_runner.py` - bind and validate a verified private-memory descriptor.
- `core/schemas/agent_capsule.py` - bind the memory vault ciphertext reference and recursively redact sealed runtime data.
- `core/agents/model_gateway_agent.py` - create vaults, append interactions, expose normal/deep recall, run commit triggers, and migrate legacy memory.
- `core/state/agent_memory_store.py` - add deterministic export, count, and retirement operations; stop being authoritative after migration.
- `core/memory/agent_memory.py` - preserve its public methods as a vault-backed compatibility adapter.
- `modules/runeforge_provider/runeforge_inference_server.py` - replace plaintext load/save with the RuneForge memory adapter.
- `tests/test_bossforge_ai_runner.py` - descriptor ownership and bootstrap binding coverage.
- `tests/test_agent_capsule_schema.py` - memory ciphertext binding and nested redaction coverage.
- `tests/test_model_gateway_agent.py` - creation, interaction, recall, commit, travel, shutdown, and migration integration coverage.
- `docs/bossforge_ai_runner_todo.md` - mark Stage 3 items only after the complete verification command passes.
- `docs/AgentForge_readme.md` - document memory ownership and profile-view behavior.
- `docs/agentforge_requirements.md` - require private memory vault creation and redaction.
- `docs/agentmaker_requirements.md` - document creation-time memory-vault guarantees.
- `docs/agents_bossgate_agentforge_schema_guide.txt` - add the memory descriptor and travel pre-commit contract.
- `docs/bossgate_connector.md` - document pre-travel commit and complete-capsule memory handling.
- `docs/bossgate_protocol.md` - document memory quiescence and non-copy movement expectations.

### Task 1: Cryptographic Envelope And Normalized Events

**Files:**
- Create: `core/memory_vault/crypto.py`
- Create: `core/memory_vault/events.py`
- Create: `core/memory_vault/__init__.py`
- Create: `tests/test_private_memory_vault.py`

- [ ] **Step 1: Write failing crypto and event tests**

Add tests that prove encryption round-trips, wrong AAD fails, plaintext is absent, event IDs are stable, and importance/relationship rules are deterministic:

```python
class PrivateMemoryCryptoTests(unittest.TestCase):
    def test_event_envelope_requires_matching_aad(self) -> None:
        key = derive_memory_key("node-1", "scribe")
        aad = event_aad("scribe", "session-1", 1, "event-1", "decision", "2026-06-06T12:00:00+00:00", "")
        blob = encrypt_bytes(b"proprietary decision", key, aad)

        self.assertNotIn(b"proprietary decision", canonical_json(blob))
        self.assertEqual(decrypt_bytes(blob, key, aad), b"proprietary decision")
        with self.assertRaisesRegex(ValueError, "authentication"):
            decrypt_bytes(blob, key, aad + b"-tampered")

    def test_normalize_event_classifies_importance_and_relationships(self) -> None:
        event = normalize_memory_event(
            agent_id="scribe",
            session_id="session-1",
            sequence=1,
            event_type="decision",
            payload={"text": "We decided to ship Project Anvil.", "project": "Anvil", "user": "Boss"},
            timestamp="2026-06-06T12:00:00+00:00",
        )

        self.assertEqual(event["importance"]["level"], "high")
        self.assertIn("decision", event["importance"]["reason_codes"])
        self.assertIn({"type": "project", "key": "Anvil"}, event["relationships"])
        self.assertIn("anvil", event["search_terms"])
```

- [ ] **Step 2: Run the focused tests and confirm the missing package failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_memory_vault.PrivateMemoryCryptoTests -v
```

Expected: `ERROR` with `ModuleNotFoundError: No module named 'core.memory_vault'`.

- [ ] **Step 3: Add authenticated encryption and attestation primitives**

Implement these exact public contracts in `core/memory_vault/crypto.py`:

```python
MEMORY_VAULT_SCHEMA_VERSION = "1.0"

def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

def derive_memory_key(node_secret: str, agent_id: str) -> bytes:
    normalized = normalize_agent_id(agent_id)
    if not str(node_secret or ""):
        raise ValueError("memory node secret is required")
    return hashlib.sha256(f"{node_secret}:{normalized}:private-memory-v1".encode("utf-8")).digest()

def encrypt_bytes(plaintext: bytes, key: bytes, aad: bytes) -> dict[str, object]:
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
    return {
        "version": 1,
        "alg": "AES-256-GCM",
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
        "ciphertext_sha256": hashlib.sha256(ciphertext).hexdigest(),
    }

def decrypt_bytes(blob: dict[str, object], key: bytes, aad: bytes) -> bytes:
    try:
        nonce = base64.b64decode(str(blob["nonce_b64"]), validate=True)
        ciphertext = base64.b64decode(str(blob["ciphertext_b64"]), validate=True)
        if hashlib.sha256(ciphertext).hexdigest() != blob["ciphertext_sha256"]:
            raise ValueError("memory ciphertext digest mismatch")
        return AESGCM(key).decrypt(nonce, ciphertext, aad)
    except (KeyError, InvalidTag, ValueError) as exc:
        raise ValueError("memory envelope authentication failed") from exc

def sign_attestation(payload: dict[str, object], key: bytes) -> str:
    return hmac.new(key, canonical_json(payload), hashlib.sha256).hexdigest()

def verify_attestation(payload: dict[str, object], signature: str, key: bytes) -> None:
    if not hmac.compare_digest(sign_attestation(payload, key), str(signature)):
        raise ValueError("memory attestation signature mismatch")
```

Also add `normalize_agent_id`, `event_aad`, encrypted JSON helpers, and atomic byte/JSON writers. Atomic writers must create a sibling temporary file, flush and `os.fsync`, then call `Path.replace`.

- [ ] **Step 4: Add normalized event and classifier contracts**

Implement `normalize_memory_event(...)` in `core/memory_vault/events.py` so the returned dictionary contains:

```python
{
    "schema_version": "1.0",
    "event_id": event_id,
    "agent_id": normalized_agent_id,
    "session_id": normalized_session_id,
    "sequence": sequence,
    "event_type": normalized_event_type,
    "timestamp": timestamp,
    "payload": payload,
    "search_terms": sorted(search_terms),
    "topics": sorted(topics),
    "relationships": relationships,
    "importance": {
        "level": "high" if reason_codes else "normal",
        "reason_codes": sorted(reason_codes),
        "manually_marked": bool(payload.get("important")),
    },
}
```

Use explicit reason codes for `commitment`, `decision`, `relationship_change`, `lifecycle`, `refusal`, `failure`, `recovery`, `security`, `discovery`, `milestone`, and `manual`. Extract only normalized alphanumeric search tokens of length at least three, and relationship records only from `user`, `agent`, `counterpart_agent`, `employer`, `project`, and `organization` payload fields.

- [ ] **Step 5: Export the stable API and run tests**

Export the Task 1 functions from `core/memory_vault/__init__.py`.

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_memory_vault.PrivateMemoryCryptoTests -v
```

Expected: all Task 1 tests pass.

- [ ] **Step 6: Commit Task 1**

```powershell
git add core/memory_vault tests/test_private_memory_vault.py
git commit -m "feat: add private memory crypto and events"
```

### Task 2: Encrypted Append-Only Journal And Live Indexes

**Files:**
- Create: `core/memory_vault/private_memory_vault.py`
- Modify: `core/memory_vault/__init__.py`
- Modify: `tests/test_private_memory_vault.py`

- [ ] **Step 1: Write failing journal and index tests**

Add tests that create a vault in `TemporaryDirectory`, append two events, and assert:

```python
descriptor = vault.initialize()
first = vault.append_event("session-1", "message", {"text": secret_text, "user": "Boss"})
second = vault.append_event(
    "session-1",
    "decision",
    {"text": "Use encrypted memory.", "project": "BossForgeOS", "important": True},
)

self.assertEqual(first["sequence"], 1)
self.assertEqual(second["sequence"], 2)
self.assertEqual(second["previous_ciphertext_sha256"], first["ciphertext_sha256"])
self.assertTrue(descriptor["verified"])
self.assertNotIn(secret_text.encode("utf-8"), b"".join(path.read_bytes() for path in vault.agent_root.rglob("*") if path.is_file()))

indexes = vault.read_active_indexes("session-1")
self.assertIn(second["event_id"], indexes["important"]["event_ids"])
self.assertEqual(indexes["relationships"]["project"]["BossForgeOS"]["interaction_count"], 1)
```

Add separate tests that delete event `000001`, swap event filenames, replay event `000001` as `000003`, and corrupt an encrypted index. `verify_active_session` must reject the journal attacks; `read_active_indexes` must rebuild a corrupt index from the authoritative journal.

- [ ] **Step 2: Run tests and confirm `PrivateMemoryVault` is missing**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_memory_vault.PrivateMemoryJournalTests -v
```

Expected: `ImportError` for `PrivateMemoryVault`.

- [ ] **Step 3: Implement vault initialization and descriptors**

Create:

```python
class PrivateMemoryVault:
    def __init__(self, *, vault_root: Path, agent_id: str, node_secret: str, key_ref: str) -> None:
        self.vault_root = Path(vault_root)
        self.agent_id = normalize_agent_id(agent_id)
        self.agent_root = self.vault_root / self.agent_id
        self.key = derive_memory_key(node_secret, self.agent_id)
        self.key_ref = str(key_ref).strip()
        if not self.key_ref:
            raise ValueError("memory key_ref is required")

    def initialize(self) -> dict[str, object]:
        self.agent_root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": MEMORY_VAULT_SCHEMA_VERSION,
            "owner_agent_id": self.agent_id,
            "key_ref": self.key_ref,
            "created_at": utc_now(),
        }
        write_encrypted_json_atomic(self.agent_root / "vault.manifest.enc", manifest, self.key, vault_aad(self.agent_id))
        attestation = self._write_vault_attestation(manifest)
        return self.descriptor(attestation)
```

The descriptor must contain `schema_version`, `owner_agent_id`, `ciphertext_ref`, `attestation_sha256`, `key_ref`, and `verified: True`. `validate_private_memory_descriptor` must reject mixed-case IDs, sibling ownership, unverified descriptors, missing key refs, and paths outside `<vault_root>/<owner>`.

- [ ] **Step 4: Implement append with sequence locking and hash chaining**

Use one `threading.RLock` per vault instance. Under the lock:

1. Read and authenticate `session.state.enc`, or initialize sequence `0`.
2. Build the normalized event at `sequence + 1`.
3. Include the previous event ciphertext hash in AAD.
4. Write `<sequence>.event.enc` atomically.
5. Decrypt/update/write all indexes atomically.
6. Advance `session.state.enc` only after all writes succeed.

Return only sparse metadata:

```python
{
    "event_id": event["event_id"],
    "sequence": sequence,
    "ciphertext_sha256": envelope["ciphertext_sha256"],
    "previous_ciphertext_sha256": previous_hash,
    "important": event["importance"]["level"] != "normal",
}
```

If index writing fails after the event is durable, mark `indexes_need_rebuild: True` in session state and keep the event authoritative. If event encryption or writing fails, do not advance sequence.

- [ ] **Step 5: Implement encrypted live indexes and rebuild**

Maintain these encrypted payloads:

```python
search_index = {
    "terms": {"encrypted": ["event-id"]},
    "topics": {"security": ["event-id"]},
    "events": {"event-id": {"sequence": 2, "timestamp": "...", "event_type": "decision"}},
}
important_index = {
    "event_ids": ["event-id"],
    "events": {"event-id": {"level": "high", "reason_codes": ["decision"], "summary": "Use encrypted memory."}},
}
relationship_index = {
    "project": {
        "BossForgeOS": {
            "interaction_count": 1,
            "last_seen_at": "...",
            "significant_event_ids": ["event-id"],
            "metadata": {},
        }
    }
}
```

`read_active_indexes` authenticates all three files. If any is missing or corrupt, call `rebuild_active_indexes`, which verifies and decrypts the journal in sequence and rewrites all indexes.

- [ ] **Step 6: Run journal tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_memory_vault.PrivateMemoryJournalTests -v
```

Expected: all journal, tamper, replay, plaintext, relationship, and rebuild tests pass.

- [ ] **Step 7: Commit Task 2**

```powershell
git add core/memory_vault tests/test_private_memory_vault.py
git commit -m "feat: add encrypted memory journals and indexes"
```

### Task 3: Verified Commit, Compression, And Selective Recall

**Files:**
- Modify: `core/memory_vault/private_memory_vault.py`
- Modify: `core/memory_vault/__init__.py`
- Modify: `tests/test_private_memory_vault.py`

- [ ] **Step 1: Write failing commit and recall tests**

Cover:

```python
result = vault.commit_session("session-1", reason="manual")
self.assertTrue(result["verified"])
self.assertFalse((vault.agent_root / "active" / "session-1").exists())
self.assertTrue((vault.agent_root / "committed" / "session-1" / "transcript.bundle.enc").exists())

transcript = vault.deep_recall(query="encrypted memory", limit=5)
self.assertEqual(transcript["events"][0]["payload"]["text"], "Use encrypted memory.")

normal = vault.normal_recall(query="BossForgeOS", limit=5)
self.assertIn("relationships", normal)
self.assertNotIn("full_transcript", normal)
```

Also test deterministic lossless compression, four-hour due calculation, commit failure preserving `active/session-1`, corruption quarantine, and that normal recall does not call the transcript decrypt helper.

- [ ] **Step 2: Run commit tests and confirm missing methods**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_memory_vault.PrivateMemoryCommitTests -v
```

Expected: `AttributeError` for `commit_session`.

- [ ] **Step 3: Implement deterministic transcript and distillation**

Serialize verified events as canonical JSONL in sequence order, then compress exactly with:

```python
def compress_transcript(events: list[dict[str, object]]) -> bytes:
    raw = b"\n".join(canonical_json(event) for event in events) + b"\n"
    return gzip.compress(raw, compresslevel=9, mtime=0)
```

`decompress_transcript` must restore every event byte-for-byte at the canonical JSON level. Distilled records must preserve `event_id`, `timestamp`, `event_type`, a bounded 400-character summary, topics, relationships, importance, and provenance; they never replace the transcript.

- [ ] **Step 4: Implement one verified commit flow for every trigger**

`commit_session(session_id, reason, committed_at=None)` must:

1. Acquire the session lock.
2. Verify the complete chain.
3. Decrypt events in batches of at most 100.
4. Build transcript, distilled records, and finalized indexes.
5. Write all encrypted artifacts beneath `.staging/<session-id>-<token>`.
6. Write `commit.attestation.json` with artifact SHA-256 values, event count, first/last sequence, reason, owner, and HMAC signature.
7. Re-open and verify every staged artifact.
8. Atomically move staging to `committed/<session-id>`.
9. Remove the active encrypted journal only after activation.

On any exception, delete only staging and leave active data untouched.

Add:

```python
def commit_if_due(self, session_id: str, now: datetime | None = None) -> dict[str, object]:
    state = self.read_session_state(session_id)
    current = now or datetime.now(timezone.utc)
    started = datetime.fromisoformat(str(state["started_at"]))
    if current - started < timedelta(hours=4):
        return {"ok": True, "committed": False, "reason": "not_due"}
    return self.commit_session(session_id, reason="four_hour")
```

- [ ] **Step 5: Implement normal and deep recall**

`normal_recall(query, limit, session_ids=None)` must search only encrypted committed index and distilled-memory artifacts and return bounded summaries plus relationships. `deep_recall(query, limit, session_ids=None)` must:

1. Use indexes to select event IDs and session IDs.
2. Verify each selected commit attestation.
3. Decrypt only selected transcript bundles.
4. Decompress and filter to selected event IDs.
5. Return at most `limit` events.

Do not write recall plaintext to disk or logger calls.

- [ ] **Step 6: Run commit and recall tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_memory_vault.PrivateMemoryCommitTests -v
```

Expected: all commit, compression, recall, corruption, and failure-preservation tests pass.

- [ ] **Step 7: Commit Task 3**

```powershell
git add core/memory_vault tests/test_private_memory_vault.py
git commit -m "feat: commit and recall encrypted agent memory"
```

### Task 4: Runner And Capsule Memory Ownership

**Files:**
- Modify: `core/runner/bossforge_ai_runner.py`
- Modify: `core/schemas/agent_capsule.py`
- Modify: `tests/test_bossforge_ai_runner.py`
- Modify: `tests/test_agent_capsule_schema.py`

- [ ] **Step 1: Write failing binding and redaction tests**

Add a valid descriptor:

```python
memory_descriptor = {
    "schema_version": "1.0",
    "owner_agent_id": "wayfinder",
    "ciphertext_ref": "private_memory/wayfinder",
    "attestation_sha256": "b" * 64,
    "key_ref": "node:alpha:agent:wayfinder:private-memory-v1",
    "verified": True,
}
```

Assert `build_runner_bootstrap(..., private_memory_vault=memory_descriptor)` stores it, sibling ownership fails, and `build_capsule_manifest` binds `vaults.memory.ciphertext_ref`.

Add a nested redaction test where the profile contains the descriptor under top-level `memory_vault`, `runtime.private_memory_vault`, and `runner_bootstrap.private_memory_vault`. `build_authenticated_profile_view` must expose none of those fields or ciphertext paths.

- [ ] **Step 2: Run schema tests and confirm signature failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bossforge_ai_runner tests.test_agent_capsule_schema -v
```

Expected: failures because the runner does not accept `private_memory_vault` and the capsule does not bind it.

- [ ] **Step 3: Bind the descriptor to the runner**

Change the signature to:

```python
def build_runner_bootstrap(
    agent_id: str,
    manifest: dict[str, Any],
    private_model_package: dict[str, Any] | None = None,
    private_memory_vault: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

Validate with `validate_private_memory_descriptor(..., expected_agent_id=normalized_id)`, copy it into the bootstrap, and repeat validation in `validate_runner_bootstrap`.

- [ ] **Step 4: Bind memory to capsule and sanitize nested views**

In `build_capsule_manifest`, set `refs["memory"]` from `runtime.private_memory_vault.ciphertext_ref`.

Replace shallow authenticated-view copying with a recursive sanitizer that:

1. Removes all keys in `_SEALED_PROFILE_VIEW_FIELDS`.
2. Removes `private_memory_vault`, `memory_vault`, and `vault_bindings`.
3. Removes dictionary values whose key ends with `_key`, `_key_ref`, `_ciphertext_ref`, or `ciphertext_ref`.
4. Preserves ordinary skills, sigils, rank, and non-secret runtime capability metadata.

- [ ] **Step 5: Run schema tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bossforge_ai_runner tests.test_agent_capsule_schema -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 4**

```powershell
git add core/runner/bossforge_ai_runner.py core/schemas/agent_capsule.py tests/test_bossforge_ai_runner.py tests/test_agent_capsule_schema.py
git commit -m "feat: bind private memory to agent capsules"
```

### Task 5: Model Gateway Vault Lifecycle

**Files:**
- Modify: `core/agents/model_gateway_agent.py`
- Modify: `tests/test_model_gateway_agent.py`

- [ ] **Step 1: Write failing Model Gateway integration tests**

Add tests proving:

1. Agent creation creates `state/private_memory/<agent-id>` and binds the descriptor to runtime, runner bootstrap, and capsule.
2. `_run_agent_profile` appends an encrypted interaction with user/employer/project/counterpart relationships.
3. `recall_agent_memory(..., mode="normal")` returns summaries without `memory_db` or paths.
4. `mode="deep"` returns selected event detail.
5. `commit_agent_memory` performs manual commit.
6. `bossgate_package_agent` commits active memory with reason `travel`.
7. `_stop_all_servers` commits active memory with reason `shutdown`.
8. A sibling descriptor causes profile creation/normalization failure.

Patch `_invoke_endpoint` so no provider process is needed.

- [ ] **Step 2: Run focused integration tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent.ModelGatewayAgentTests.test_created_agent_owns_private_memory_vault tests.test_model_gateway_agent.ModelGatewayAgentTests.test_run_agent_writes_encrypted_memory tests.test_model_gateway_agent.ModelGatewayAgentTests.test_travel_commits_private_memory -v
```

Expected: failures because the vault lifecycle is not wired.

- [ ] **Step 3: Add vault construction and agent creation**

In `ModelGateway.__init__` add:

```python
self.private_memory_root = self.bus.state / "private_memory"
self.private_memory_root.mkdir(parents=True, exist_ok=True)
self._memory_vaults: Dict[str, PrivateMemoryVault] = {}
```

Add:

```python
def _memory_vault(self, agent_id: str) -> PrivateMemoryVault:
    key = agent_id.strip().lower()
    vault = self._memory_vaults.get(key)
    if vault is None:
        vault = PrivateMemoryVault(
            vault_root=self.private_memory_root,
            agent_id=key,
            node_secret=self.node_id,
            key_ref=f"node:{self.node_id}:agent:{key}:private-memory-v1",
        )
        self._memory_vaults[key] = vault
    return vault
```

During new-agent creation, initialize the vault before persisting the profile, place the descriptor at `runtime["private_memory_vault"]`, pass it to `build_runner_bootstrap`, and rebuild the capsule. If any later creation step fails, remove only the newly created empty memory vault directory along with the new model package.

- [ ] **Step 4: Replace SQLite writes and recall**

Replace `memory_store.record_interaction` with:

```python
self._memory_vault(key).append_event(
    session_id=str(ctx.get("session_id") or f"gateway-{datetime.now(timezone.utc).date().isoformat()}"),
    event_type="task_action" if result.get("ok") else "failure",
    payload={
        "task": task,
        "text": str(result.get("text") or result.get("message") or "")[:400],
        "success": bool(result.get("ok")),
        "endpoint": endpoint,
        "user": str(ctx.get("user", "")).strip(),
        "employer": str(ctx.get("employer", "")).strip(),
        "project": str(ctx.get("project", "")).strip(),
        "counterpart_agent": str(ctx.get("counterpart_agent", "")).strip(),
        "details": {
            "usage": result.get("usage", {}),
            "provider": result.get("provider", ""),
            "model": result.get("model", ""),
        },
    },
)
```

Change recall to:

```python
def recall_agent_memory(self, name: str, query: str = "", limit: int = 25, mode: str = "normal") -> Dict[str, Any]:
    vault = self._memory_vault(name)
    recalled = vault.deep_recall(query=query, limit=limit) if mode == "deep" else vault.normal_recall(query=query, limit=limit)
    return {"ok": True, "agent": name.strip().lower(), "mode": mode, **recalled}
```

- [ ] **Step 5: Add explicit and lifecycle commit hooks**

Add `commit_agent_memory(name, reason="manual", session_id="")`, `commit_due_memories(now=None)`, and `commit_all_active_memories(reason)`.

Call the same commit flow:

- before `bossgate_package_agent` with `reason="travel"`;
- before a future dream transition through `prepare_agent_for_dream(name)` with `reason="dream"`;
- in `_stop_all_servers` with `reason="shutdown"`;
- on a new command `commit_agent_memory`;
- once per main loop iteration via `commit_due_memories`.

If pre-travel commit fails, return failure and do not package the agent.

- [ ] **Step 6: Run all Model Gateway tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit Task 5**

```powershell
git add core/agents/model_gateway_agent.py tests/test_model_gateway_agent.py
git commit -m "feat: wire private memory through model gateway"
```

### Task 6: Legacy SQLite And AgentMemory JSON Migration

**Files:**
- Create: `core/memory_vault/migration.py`
- Modify: `core/memory_vault/__init__.py`
- Modify: `core/state/agent_memory_store.py`
- Modify: `core/memory/agent_memory.py`
- Create: `tests/test_memory_vault_migration.py`

- [ ] **Step 1: Write failing migration tests**

Create a temporary SQLite database with one agent, two interactions, and relationships plus a plaintext `<agent>_memory.json` containing events, social logs, refusals, and retirements.

Assert:

```python
result = migrate_agent_memory(
    agent_id="scribe",
    vault=vault,
    sqlite_store=store,
    json_memory_path=json_path,
)
self.assertTrue(result["verified"])
self.assertEqual(result["source_counts"]["sqlite_interactions"], 2)
self.assertEqual(result["source_counts"]["json_refusals"], 1)
self.assertFalse(json_path.exists())
self.assertEqual(store.count_agent_records("scribe")["interactions"], 0)
self.assertEqual(vault.verify_committed_session(result["session_id"])["event_count"], result["imported_event_count"])
```

Add failure tests where commit verification is mocked to fail and where plaintext retirement fails. Verification failure must leave all source data untouched. Retirement failure must report `verified: False`, retain or quarantine the source, and never report the agent fully sealed.

- [ ] **Step 2: Run migration tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_memory_vault_migration.LegacyMemoryMigrationTests -v
```

Expected: import failures for migration APIs.

- [ ] **Step 3: Add deterministic SQLite export and retirement**

Add:

```python
def export_agent_records(self, agent_name: str) -> dict[str, list[dict[str, Any]]]:
    key = (agent_name or "").strip().lower()
    with self._connection() as con:
        agent_rows = con.execute(
            "SELECT agent_name, agent_class, has_llm, created_at, updated_at FROM agents WHERE agent_name = ?",
            (key,),
        ).fetchall()
        interaction_rows = con.execute(
            "SELECT * FROM interactions WHERE agent_name = ? ORDER BY id",
            (key,),
        ).fetchall()
        relationship_rows = con.execute(
            "SELECT * FROM relationships WHERE agent_name = ? ORDER BY relation_type, relation_key",
            (key,),
        ).fetchall()
    return {
        "agents": [dict(row) for row in agent_rows],
        "interactions": [dict(row) for row in interaction_rows],
        "relationships": [dict(row) for row in relationship_rows],
    }

def count_agent_records(self, agent_name: str) -> dict[str, int]:
    key = (agent_name or "").strip().lower()
    with self._connection() as con:
        return {
            table: int(con.execute(f"SELECT COUNT(*) FROM {table} WHERE agent_name = ?", (key,)).fetchone()[0])
            for table in ("agents", "interactions", "relationships")
        }

def retire_agent_records(self, agent_name: str, expected_counts: dict[str, int]) -> None:
    key = (agent_name or "").strip().lower()
    with self._connection() as con:
        con.execute("BEGIN IMMEDIATE")
        actual = {
            table: int(con.execute(f"SELECT COUNT(*) FROM {table} WHERE agent_name = ?", (key,)).fetchone()[0])
            for table in ("agents", "interactions", "relationships")
        }
        if actual != expected_counts:
            con.rollback()
            raise ValueError("legacy memory source changed during migration")
        con.execute("DELETE FROM relationships WHERE agent_name = ?", (key,))
        con.execute("DELETE FROM interactions WHERE agent_name = ?", (key,))
        con.execute("DELETE FROM agents WHERE agent_name = ?", (key,))
        con.commit()
```

The export must decode JSON fields but preserve original timestamp strings and database row IDs in provenance. Do not `VACUUM` the shared database inside the per-agent transaction.

- [ ] **Step 4: Implement inventory, normalization, verification, and signed attestation**

`migrate_agent_memory` must:

1. Export all available sources without mutation.
2. Hash each canonical source record.
3. Normalize records into event types `legacy_interaction`, `relationship_change`, `legacy_event`, `relationship_change`, `refusal`, and `lifecycle`.
4. Append them to session `migration-<UTC timestamp>`.
5. Commit with reason `migration`.
6. Verify imported count, source hashes, relationship totals, owner, and committed attestation.
7. Write `migration.attestation.json` containing source counts/hashes, committed session, result, and HMAC signature.
8. Retire sources only after step 7 verifies.

If retirement fails, move a JSON source to `<name>.migration-quarantine` only when the rename itself succeeds; leave SQLite rows intact if their guarded delete fails. Record `retirement_complete: False`.

- [ ] **Step 5: Convert `AgentMemory` into a vault-backed adapter**

Keep `record_event`, `add_social_log`, `record_refusal`, and `retire_agent` signatures. Accept an optional `vault`; when provided, route each method to `append_event`. If a legacy plaintext file exists, require `migrate_legacy()` before accepting new writes. `save`, `compress`, and `archive` must raise a clear `RuntimeError` explaining that plaintext persistence is disabled, rather than silently writing JSON.

- [ ] **Step 6: Run migration tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_memory_vault_migration -v
```

Expected: all SQLite, JSON, provenance, verification, quarantine, and retirement tests pass.

- [ ] **Step 7: Commit Task 6**

```powershell
git add core/memory_vault core/state/agent_memory_store.py core/memory/agent_memory.py tests/test_memory_vault_migration.py
git commit -m "feat: migrate legacy agent memory into vaults"
```

### Task 7: RuneForge Private Memory Adapter

**Files:**
- Create: `modules/runeforge_provider/memory_adapter.py`
- Modify: `modules/runeforge_provider/runeforge_inference_server.py`
- Create: `tests/test_runeforge_memory_adapter.py`
- Modify: `tests/test_runeforge_agent.py`

- [ ] **Step 1: Write failing RuneForge adapter tests**

Test that:

1. Existing `runeforge_memory_store.json` sessions/users migrate into RuneForge's vault with original stance, trust, turns, preferences, topics, and timestamps.
2. The plaintext file is removed only after verified commit.
3. `get_session` and `get_user` rehydrate current state through normal recall.
4. `update_memory_from_signal` appends encrypted `relationship_change` and `preference` events.
5. A failed vault write leaves in-memory state unchanged and does not create plaintext.

- [ ] **Step 2: Run adapter tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_runeforge_memory_adapter -v
```

Expected: `ModuleNotFoundError` for `modules.runeforge_provider.memory_adapter`.

- [ ] **Step 3: Implement the RuneForge adapter**

Create:

```python
class RuneForgeMemoryAdapter:
    def __init__(self, vault: PrivateMemoryVault, legacy_path: Path) -> None:
        self.vault = vault
        self.legacy_path = Path(legacy_path)
        self.sessions: dict[str, dict[str, object]] = {}
        self.users: dict[str, dict[str, object]] = {}

    def load(self) -> None:
        if self.legacy_path.exists():
            migrate_runeforge_memory(vault=self.vault, source_path=self.legacy_path)
        recalled = self.vault.normal_recall(query="", limit=200)
        self.sessions, self.users = rebuild_runeforge_state(recalled)

    def persist_session(self, session_id: str) -> None:
        self.vault.append_event(
            session_id=f"runeforge-{session_id}",
            event_type="relationship_change",
            payload={"session_id": session_id, **self.sessions[session_id]},
        )

    def persist_user(self, user_id: str) -> None:
        self.vault.append_event(
            session_id=f"runeforge-user-{user_id}",
            event_type="preference",
            payload={"user": user_id, **self.users[user_id]},
        )
```

`migrate_runeforge_memory` must use the same migration verification and attestation primitives from Task 6, not a RuneForge-only weaker path.

- [ ] **Step 4: Replace plaintext server load/save**

Initialize RuneForge's vault from:

```python
RUNEFORGE_MEMORY_VAULT_ROOT = Path(os.getenv("RUNEFORGE_MEMORY_VAULT_ROOT", str(Path(WORKSPACE_ROOT) / "state" / "private_memory")))
RUNEFORGE_MEMORY_NODE_SECRET = os.getenv("RUNEFORGE_MEMORY_NODE_SECRET", "runeforge-local-development-key")
```

Keep `session_state` and `user_state` only as bounded process caches. `load_memory_store()` calls adapter `load()`. Remove `save_memory_store()` file writes and replace its call sites with `persist_session` and/or `persist_user` after successful state updates.

The `/health` response may report `memory_vault_enabled: True` and `memory_vault_owner: "runeforge"` but must not expose paths, key refs, ciphertext refs, or the legacy store path.

- [ ] **Step 5: Run RuneForge tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_runeforge_memory_adapter tests.test_runeforge_agent tests.test_runeforge_runner_metadata tests.test_runeforge_voice_safety -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 7**

```powershell
git add modules/runeforge_provider tests/test_runeforge_memory_adapter.py tests/test_runeforge_agent.py
git commit -m "feat: seal runeforge relationship memory"
```

### Task 8: Migration Orchestration, Commands, And Trigger Coverage

**Files:**
- Modify: `core/agents/model_gateway_agent.py`
- Modify: `tests/test_model_gateway_agent.py`
- Modify: `tests/test_private_memory_vault.py`
- Modify: `tests/test_memory_vault_migration.py`

- [ ] **Step 1: Write failing orchestration tests**

Add tests for:

- startup inventory that identifies legacy records without retiring them;
- explicit `migrate_agent_memory` command;
- idempotent rerun returning the verified existing migration attestation;
- four-hour automatic commit;
- explicit close commit;
- travel, dream, and shutdown using the identical `commit_session` method;
- failed pre-travel commit blocking package creation;
- no profile, event bus record, health response, or command result containing `ciphertext_ref`, `key_ref`, vault path, or recalled plaintext.

- [ ] **Step 2: Run orchestration tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent tests.test_private_memory_vault tests.test_memory_vault_migration -v
```

Expected: new orchestration tests fail.

- [ ] **Step 3: Add explicit migration and commit commands**

Add command handlers:

```python
elif command == "commit_agent_memory":
    result = self.commit_agent_memory(
        name=str(args.get("name", "")),
        reason=str(args.get("reason", "manual")),
        session_id=str(args.get("session_id", "")),
    )
elif command == "migrate_agent_memory":
    result = self.migrate_agent_memory(name=str(args.get("name", "")))
elif command == "recall_agent_memory":
    result = self.recall_agent_memory(
        name=str(args.get("name", "")),
        query=str(args.get("query", "")),
        limit=int(args.get("limit", 25)),
        mode=str(args.get("mode", "normal")),
    )
```

Return sparse status fields only: `ok`, `agent`, `mode` or `reason`, counts, timestamps, and verification state.

- [ ] **Step 4: Make migration idempotent and fail closed**

Before import, read and verify any existing `migration.attestation.json`. If its source hashes still match, return it without duplicating events. If hashes differ, require a new migration session. Never auto-retire sources during ordinary startup; startup only reports `migration_required` so an operator can observe failures.

- [ ] **Step 5: Run the complete Stage 3 code suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_private_memory_vault tests.test_memory_vault_migration tests.test_runeforge_memory_adapter tests.test_bossforge_ai_runner tests.test_agent_capsule_schema tests.test_model_gateway_agent tests.test_agentforge_service tests.test_runeforge_agent tests.test_runeforge_runner_metadata tests.test_runeforge_voice_safety -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 8**

```powershell
git add core/agents/model_gateway_agent.py tests/test_model_gateway_agent.py tests/test_private_memory_vault.py tests/test_memory_vault_migration.py
git commit -m "feat: orchestrate private memory lifecycle"
```

### Task 9: Documentation And Final Verification

**Files:**
- Modify: `docs/bossforge_ai_runner_todo.md`
- Modify: `docs/AgentForge_readme.md`
- Modify: `docs/agentforge_requirements.md`
- Modify: `docs/agentmaker_requirements.md`
- Modify: `docs/agents_bossgate_agentforge_schema_guide.txt`
- Modify: `docs/bossgate_connector.md`
- Modify: `docs/bossgate_protocol.md`

- [ ] **Step 1: Update the memory-vault documentation**

Document these implemented contracts consistently:

- every event is AES-256-GCM encrypted before persistence;
- active memory is an encrypted chained journal, not plaintext RAM or a plaintext page file;
- live encrypted search, importance, and relationship indexes update per event;
- the single verified commit flow serves four-hour, manual, close, travel, dream-preparation, and shutdown triggers;
- committed memory retains both lossless compressed transcript and distilled records;
- normal recall uses distilled/index data and deep recall rehydrates selected details;
- SQLite, legacy `AgentMemory`, and RuneForge plaintext stores are migration inputs only;
- memory belongs to the agent, is capsule-bound, and is not copied or exposed in profile views;
- Stage 4 consumes Stage 3 learning inputs but does not alter weights in Stage 3.

- [ ] **Step 2: Run documentation consistency searches**

Run:

```powershell
rg -n "plaintext memory|gateway_memory.sqlite3|runeforge_memory_store|memory_db|Stage 3" docs core modules
```

Expected: remaining mentions of plaintext stores describe migration only; no documentation calls them authoritative.

- [ ] **Step 3: Run compilation and the full focused regression suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall -q core\memory_vault core\memory core\state core\runner core\schemas core\agents modules\runeforge_provider tests
.\.venv\Scripts\python.exe -m unittest tests.test_private_memory_vault tests.test_memory_vault_migration tests.test_runeforge_memory_adapter tests.test_bossforge_ai_runner tests.test_agent_capsule_schema tests.test_model_gateway_agent tests.test_agentforge_entitlements tests.test_agentforge_service tests.test_control_hall_model_routes tests.test_runeforge_agent tests.test_runeforge_runner_metadata tests.test_runeforge_voice_safety tests.test_bossgate_agent tests.test_bossgate_authorization tests.test_bossgate_connector -q
git diff --check
git status --short
```

Expected:

- compile command exits `0`;
- all listed tests pass;
- `git diff --check` prints nothing;
- `git status --short` lists only intended Stage 3 documentation edits before the final commit.

- [ ] **Step 4: Mark Stage 3 complete only after Step 3 passes**

Change both Stage 3 checklist entries in `docs/bossforge_ai_runner_todo.md` to `[x]` and add the exact verification command plus date `2026-06-06`.

- [ ] **Step 5: Commit Task 9**

```powershell
git add docs/bossforge_ai_runner_todo.md docs/AgentForge_readme.md docs/agentforge_requirements.md docs/agentmaker_requirements.md docs/agents_bossgate_agentforge_schema_guide.txt docs/bossgate_connector.md docs/bossgate_protocol.md
git commit -m "docs: complete private memory vault stage"
```

- [ ] **Step 6: Confirm clean completion**

Run:

```powershell
git status --short
git log -10 --oneline
```

Expected: clean status and nine Stage 3 commits ending with `docs: complete private memory vault stage`.
