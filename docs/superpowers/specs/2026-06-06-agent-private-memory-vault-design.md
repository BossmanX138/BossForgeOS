# Agent Private Memory Vault Design

Date: 2026-06-06
Status: Approved design for BossForgeOS AI Runner Stage 3

## Goal

Give every agent an encrypted, independently owned memory vault that preserves
full session history, distilled learning, relationships, and important events
without retaining long-lived plaintext memory files.

Memory remains part of the agent and travels with the complete capsule.

## Governing Decisions

1. Every memory event is encrypted immediately.
2. Active sessions use an append-only encrypted journal.
3. Search, relationship, topic, and importance indexes update as events occur.
4. Sessions commit automatically every four hours.
5. Manual and session-close commits are also supported.
6. Commit produces a compressed full transcript plus distilled memories and
   indexes.
7. Deep recall selectively decrypts and rehydrates only relevant material.
8. Existing SQLite, JSON agent-memory, and RuneForge relationship records are
   imported, verified, and retired from active plaintext storage.
9. Important events are detected automatically and may also be marked
   manually by a human or agent.

## Scope

This stage implements:

1. Per-agent encrypted memory-vault packages.
2. Append-only encrypted active-session journals.
3. Live encrypted search, topic, relationship, and importance indexes.
4. Four-hour and explicit commit boundaries.
5. Compressed permanent session bundles.
6. Distilled memory records for learning and normal recall.
7. Selective detailed rehydration for deep recall.
8. Migration from existing plaintext memory stores.
9. Capsule and runner memory-vault bindings.
10. Public and authenticated profile-view redaction.

This stage does not implement:

1. Dream training or weight updates.
2. Automatic long-term memory deletion policy.
3. Semantic vector-database infrastructure.
4. Full-capsule BossGate transport.
5. Production HSM or operating-system key custody.

## Source Memory Systems

Stage 3 converges:

1. `core/state/agent_memory_store.py`
   - agents
   - interactions
   - human, employer, project, and agent relationships
2. `core/memory/agent_memory.py`
   - events
   - social logs
   - refusals
   - retirements
3. RuneForge relationship memory
   - session stance and trust
   - recent modes and signals
   - user preferences and topics

After migration, these sources may remain as compatibility adapters, but they
must not remain authoritative plaintext stores.

## Vault Layout

```text
<memory-vault-root>/
`-- <agent-id>/
    |-- vault.attestation.json
    |-- vault.manifest.enc
    |-- active/
    |   `-- <session-id>/
    |       |-- journal/
    |       |   `-- <sequence>.event.enc
    |       |-- search.index.enc
    |       |-- important.index.enc
    |       |-- relationship.index.enc
    |       `-- session.state.enc
    `-- committed/
        `-- <session-id>/
            |-- transcript.bundle.enc
            |-- distilled.memories.enc
            |-- search.index.enc
            |-- important.index.enc
            |-- relationship.index.enc
            `-- commit.attestation.json
```

The sparse attestations contain only non-secret package identity, owner,
schema, encrypted-artifact hashes, timestamps, and verification state.

## Event Journal

Each event is independently encrypted with AES-256-GCM using a fresh nonce and
authenticated metadata:

1. Agent ID
2. Session ID
3. Sequence number
4. Event ID
5. Event type
6. Timestamp
7. Previous-event ciphertext hash

The previous-event hash forms a tamper-evident append chain. Missing,
reordered, substituted, or replayed events fail verification.

An event may contain:

1. Human or agent message
2. Task action
3. Tool result
4. Decision
5. Commitment
6. Discovery
7. Failure
8. Refusal
9. Security event
10. Relationship change
11. Promotion or lifecycle event
12. Manual importance marker

Only the event currently being processed exists briefly as plaintext.

## Live Indexing

Indexing occurs as each event is appended.

### Search Index

Stores normalized terms, topics, entities, event references, and session
references. The index itself remains encrypted at rest.

### Important Event Index

An event is marked important when automatic rules or a manual marker identify:

1. Commitments and promises
2. Decisions and policy changes
3. Relationship or trust changes
4. Promotions, death, retirement, or ownership changes
5. Refusals and safety boundaries
6. Failures and recoveries
7. Security events
8. Significant discoveries
9. Project milestones
10. Explicit human or agent importance marking

The index records importance level, reason codes, event references, and
distilled summaries.

### Relationship Index

Tracks relationships with:

1. Humans
2. Agents
3. Employers
4. Projects
5. Organizations

Relationship records include interaction counts, trust or stance when
available, last-seen timestamps, significant-event references, and sealed
metadata.

## Four-Hour Commit

A session commit occurs:

1. Every four hours from session start.
2. On explicit `commit_to_memory`.
3. On orderly session close.
4. Before travel quiescence.
5. Before dream eligibility.
6. Before shutdown when policy allows sufficient time.

Commit flow:

1. Quiesce journal appends for the session.
2. Verify the complete event chain.
3. Decrypt events in bounded batches.
4. Build a full transcript.
5. Compress the transcript.
6. Produce distilled memories and summaries.
7. Finalize search, important-event, and relationship indexes.
8. Encrypt all permanent bundle artifacts.
9. Write and verify the commit attestation.
10. Atomically activate the committed bundle.
11. Retire the active encrypted journal only after verification.
12. Start a new active session journal if work continues.

Compression uses a standard deterministic lossless format. Distillation never
replaces the full compressed transcript.

## Recall

### Normal Recall

Normal recall:

1. Searches encrypted indexes.
2. Decrypts only matching index pages.
3. Returns distilled memory summaries and relationship context.
4. Keeps recalled plaintext bounded and transient.

### Deep Recall

Deep recall:

1. Selects one or more relevant committed bundles.
2. Verifies bundle attestations.
3. Decrypts and decompresses only selected transcript fragments.
4. Returns detailed context for the current authorized task.
5. Clears transient plaintext buffers after use.

Recall results must not be written into public profile views or ordinary logs.

## Migration

Migration is per agent and fail-closed:

1. Inventory records from all legacy stores.
2. Normalize them into memory events.
3. Preserve original timestamps and source provenance.
4. Import into an encrypted migration session.
5. Build indexes and committed bundles.
6. Verify record counts, hashes, ownership, and relationship totals.
7. Record a signed migration attestation.
8. Retire plaintext originals only after successful verification.

Retirement means:

1. Remove migrated rows from the shared authoritative database.
2. Remove migrated per-agent plaintext JSON files.
3. Remove RuneForge plaintext relationship records after her vault verifies.
4. Retain only non-proprietary migration audit metadata.
5. Quarantine, rather than delete, any source that cannot be verified.

## Ownership And Isolation

1. Each vault belongs to exactly one normalized agent ID.
2. Sibling agents cannot share vault paths, keys, journals, bundles, or
   indexes.
3. Runner, capsule, vault manifest, and attestations must identify the same
   agent.
4. Hidden and non-hidden profile views never expose memory content, indexes,
   relationships, keys, or ciphertext paths.
5. Host-wide databases may provide compatibility queries but cannot be the
   authoritative memory after migration.

## Failure Handling

1. Failed event encryption does not advance the sequence number.
2. Failed index updates leave the encrypted event journal authoritative and
   trigger index rebuild.
3. Failed commits leave the active journal intact.
4. Partial committed bundles are never activated.
5. Migration failure leaves plaintext sources untouched.
6. Plaintext retirement failure marks migration incomplete and prevents the
   source from being reported as fully sealed.
7. Corrupt bundles are quarantined and excluded from recall.

## Learning Boundary

Memory-first learning consumes:

1. Distilled memories
2. Relationship state
3. Important events
4. Repeated preferences
5. Successful and failed task patterns
6. Refusals and safety boundaries

Stage 3 provides these encrypted learning inputs. Stage 4 dreams decide when
and how they may influence model weights or sigils.

## Testing Strategy

Tests must prove:

1. Every appended event is encrypted immediately.
2. Plaintext messages do not appear in journal or index files.
3. Event-chain tampering and replay are rejected.
4. Live indexes update for search, relationships, topics, and importance.
5. Automatic and manual importance marking both work.
6. Four-hour, manual, close, travel, dream, and shutdown commits use the same
   verified commit flow.
7. Full transcript compression is lossless.
8. Distilled memories do not remove the full transcript.
9. Normal recall decrypts only selected index material.
10. Deep recall rehydrates selected detailed fragments.
11. Commit failure preserves the active journal.
12. Sibling vault rebinding is rejected.
13. Legacy SQLite, JSON, and RuneForge records migrate with counts and
    provenance preserved.
14. Plaintext sources retire only after successful migration verification.
15. Hidden and authenticated non-hidden views expose no memory details.
16. Existing AgentForge, Model Gateway, RuneForge, and BossGate tests remain
    green.

## Documentation Updates

Implementation updates:

1. `docs/bossforge_ai_runner_todo.md`
2. `docs/AgentForge_readme.md`
3. `docs/agentforge_requirements.md`
4. `docs/agentmaker_requirements.md`
5. `docs/agents_bossgate_agentforge_schema_guide.txt`
6. `docs/bossgate_connector.md`
7. `docs/bossgate_protocol.md`

