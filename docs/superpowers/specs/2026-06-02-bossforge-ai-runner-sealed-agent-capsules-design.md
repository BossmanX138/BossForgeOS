# BossForgeOS AI Runner And Sealed Agent Capsules Design

Date: 2026-06-02
Status: Umbrella design for staged implementation

## Goal

Extract a portable BossForgeOS AI runner model from the current RuneForge-centered inference provider so every LLM-enabled traveling agent can operate autonomously as a sealed, self-contained capsule.

RuneForge remains a distinct personalized agent. Her runner is the direct ancestor of the gifted runtime template used to create descendant agents. Each descendant receives a private copy of its complete runtime and weights and may evolve independently without changing RuneForge or sibling agents.

## Governing Sources

The current policy source is:

- `docs/AgentForge_readme.md`

Compatibility aliases:

- `docs/agentforge_requirements.md`
- `docs/agentmaker_requirements.md`

Supporting technical guide:

- `docs/agents_bossgate_agentforge_schema_guide.txt`

The technical guide must be refreshed as staged implementation lands because portions of its rank-capacity matrix and BossGate status are stale.

## Core Principles

1. An agent travels as a whole. Travel is not a profile copy or endpoint reassignment.
2. Each traveling agent owns a complete private runtime and private model weights.
3. No destination-side shared-weight dependency, deduplicated weight shortcut, or remote runtime dependency is allowed.
4. Every agent carries BossGate protection.
5. RuneForge keeps her personalized runner and gifts a derived runtime template to newly forged descendants.
6. A descendant records RuneForge as a sealed direct runtime ancestor.
7. Memory, relationships, and learned history are part of agent identity and travel with the agent.
8. Dream training occurs only while an agent is inactive and policy-authorized.
9. Hidden agents expose only a sparse public identity card. All non-public agent material remains encrypted.

## Agent Capsule

Every traveling agent is packaged as a sealed capsule:

```text
agent capsule
|-- public_identity_card
|-- encrypted_identity_vault
|-- bossforge_ai_runner
|-- private_model
|-- memory_vault
|-- capability_vault
|-- dream_vault
`-- bossgate_vault
```

### Public Identity Card

The public identity card is the only unencrypted profile surface for a hidden agent.

Allowed fields:

1. `name`
2. `public_id`
3. `agent_class`
4. `agent_type`
5. `rank`
6. `rarity`
7. `availability`

The public identity card must not expose:

1. Seven-word BossGate address
2. Ancestry or lineage
3. Skills
4. Sigils
5. Tools or MCP servers
6. Runtime details
7. Model details or weights
8. Memory, relationships, refusals, or retirement history
9. Policies
10. Dream history or checkpoints
11. Travel metadata

### Encrypted Identity Vault

The encrypted identity vault contains the complete proprietary profile, including:

1. Internal agent ID
2. Seven-word BossGate address
3. Runtime ancestry
4. Class, type, rank, and immutable rarity records
5. Promotion history
6. Ownership and policy metadata
7. Disclosure posture

### BossForgeOS AI Runner

Each agent capsule carries a dedicated AI runner instance:

1. Portable inference-server runtime
2. Model-loader logic
3. Autonomous lifecycle loop
4. State-machine execution support
5. Memory-vault access
6. Tool mediation
7. Dream scheduler integration
8. Signed wake and dream controls
9. Local resource checks
10. BossGate install and wake bootstrap contract

The runner is agent-local after creation. It does not depend on RuneForge remaining online.

### Private Model

Each agent capsule contains its own complete encrypted model body:

1. Model weights
2. Tokenizer
3. Model configuration
4. Adapters
5. Generation configuration
6. Runtime requirements
7. Training provenance
8. Rollback checkpoints

Private model material is never shared between sibling agents after creation.

### Memory Vault

Memory is a first-class identity component and must travel with the agent:

1. Interaction memory
2. Human relationships
3. Agent relationships
4. Employer and project relationships
5. Social logs
6. Refusals
7. Retirement records
8. Learned preferences and continuity context
9. Dream-training corpus
10. Compression and archive metadata

Current implementation inputs to unify:

1. `core/state/agent_memory_store.py`
2. `core/memory/agent_memory.py`
3. RuneForge-specific relationship memory in `modules/runeforge_provider/runeforge_inference_server.py`

The staged implementation must converge these into encrypted per-agent vaults rather than a host-shared database as the authoritative copy.

### Capability Vault

The capability vault stores:

1. Skills
2. Sigils and evolution lineage
3. Tools and MCP server definitions
4. Tool provenance
5. Consent-trade records
6. Dead-agent inheritance records
7. Capacity-slot accounting

### Dream Vault

The dream vault stores:

1. Dream policy
2. Dream eligibility state
3. Training corpus snapshots
4. Pre-dream signed checkpoints
5. Post-dream candidate checkpoints
6. Evaluation results
7. Rollback history
8. Sigil-evolution events
9. Audit records

### BossGate Vault

The BossGate vault stores:

1. Seven-word address
2. Gate companion file
3. Transfer envelope metadata
4. Chunk manifest
5. Resume metadata
6. Replay protection state
7. Transport signing material
8. Install and wake attestation material

## Hidden Disclosure Boundary

When an agent has `hidden=true`, everything except the public identity card is encrypted at rest and in transit.

The existing AgentForge `hidden` and `non_hidden` disclosure posture remains a profile-view control:

1. `hidden` exposes only the sparse public identity card.
2. `non_hidden` may expose additional approved profile details to authenticated proprietary viewers.
3. Gate files and travel packages remain encrypted in both modes.
4. No view posture permits raw weight, private runner, memory-vault, relationship-vault, address, signing-key, or checkpoint disclosure through ordinary profile views.

## Prime BossGate Address Rule

Seven-word addresses are not public profile fields.

Only Prime BossGates may detect or enumerate agent addresses:

1. `bossforgeos`
2. `ass` (Anvil Secured Shuttle)
3. `bridgebase_alpha`

Ordinary gates:

1. May be validated travel targets.
2. May receive a specifically addressed capsule.
3. Must not enumerate agent addresses.
4. Must not initiate travel.

## RuneForge Runtime Lineage

RuneForge is the runtime ancestor of descendants forged from her gifted template.

### RuneForge

RuneForge retains:

1. Her personalized runner
2. Her own private weights
3. Her memory vault
4. Her capability vault
5. Her own independent dream history

### Gifted Runtime Template

AgentForge may use RuneForge's gifted runtime template as the creation baseline for new agents.

The template is:

1. Versioned
2. Signed
3. Read-only as a lineage source
4. Copied into a descendant capsule during forging
5. Detached after creation so descendants evolve independently

### Descendants

Each descendant records:

1. `runtime_ancestor_id=runeforge`
2. Gifted template version
3. Forge timestamp
4. Independent runner version after creation
5. Lineage events produced by later dream evolution

Lineage is sealed for hidden agents.

## Agent Evolution Rules

### Memory And Relationships

Memory and relationship state evolve continuously during active life.

Each meaningful interaction may update:

1. Historical interaction log
2. Human relationship state
3. Agent relationship state
4. Employer relationship state
5. Project relationship state
6. Social log
7. Refusal history
8. Dream-training eligibility corpus

### Dream Training

Weight evolution occurs only during dreams.

An agent may enter dreams automatically when:

1. Its signed dream policy permits automatic dreams.
2. The agent is inactive.
3. No task is running or queued for the agent.
4. No travel is pending or active.
5. Resource checks confirm safe CPU, RAM, GPU, VRAM, disk, and thermal headroom.
6. Security policy has not disabled dreams.
7. A pre-dream signed checkpoint has been created.

Security administrators may:

1. Disable automatic dreams.
2. Stop an active dream.
3. Require rollback.
4. Inspect dream audit history.

### Signed Checkpoints

A signed checkpoint is a tamper-evident secure save point created before dream training changes an agent.

It includes:

1. Agent identity reference
2. Current encrypted weights
3. Runner version
4. Memory-vault version
5. Sigil state and lineage
6. Training-input summary
7. Timestamp
8. Signature

After a dream:

1. Candidate weights are evaluated.
2. Unsafe or regressed candidates are rejected.
3. Accepted candidates become the new active checkpoint.
4. Rollback restores the verified pre-dream checkpoint.

### Skill Learning

Skills may be learned from other agents when:

1. The teaching agent possesses the skill.
2. The receiving agent has an available skill slot under its rank limit.
3. Class and type constraints permit the skill.
4. The teaching event is consented to and audited.
5. The updated capability vault is re-signed.

Skills may be unlearned only through authorized trainer-agent logic.

### Tool Issuance, Trading, And Inheritance

Tools and MCP definitions:

1. Originate from AgentForge.
2. May be inherited from dead agents.
3. May be traded between live agents only with mutual consent.
4. Must satisfy receiving-agent type and rank constraints.
5. Must retain provenance and trade history.
6. Must be re-signed after transfer.

Tool trading is transfer, not unauthorized duplication. Whether a specific tool license permits move, lease, or Forge-issued duplication is recorded in tool provenance.

### Sigil Evolution

Existing sigils may evolve automatically during dreams when:

1. The evolution follows a signed allowed lineage edge.
2. Class, type, and rank constraints remain valid.
3. A pre-dream checkpoint exists.
4. Evaluation passes.
5. The lineage event is audited.
6. Rollback remains available.

Unrelated new sigils require AgentForge issuance.

### Rank

Rank:

1. Is assigned at creation.
2. Does not change through dreams.
3. Changes only through an explicit authorized promotion.
4. Records promotion history in the encrypted identity vault.

### Rarity

Rarity:

1. Is assigned at creation.
2. Is part of immutable agent identity.
3. Does not change through dreams, promotion, travel, teaching, tool trade, inheritance, or sigil evolution.

## Lifecycle State Model

The portable runner must support at least:

1. `sealed`
2. `installed`
3. `waking`
4. `idle`
5. `active`
6. `travel_pending`
7. `traveling`
8. `dream_eligible`
9. `dreaming`
10. `dream_validating`
11. `rollback`
12. `offline`
13. `dead`
14. `retired`

Only allowed state transitions may occur. Dream state must never overlap active execution or travel.

## Full-Capsule Move Transport

BossGate travel packages must contain the complete encrypted agent capsule.

### Packaging

Before travel:

1. Quiesce the agent.
2. Prevent new tasks.
3. Flush memory and relationship state.
4. Persist capsule state.
5. Encrypt the complete capsule.
6. Build signed chunk manifests.
7. Record transfer audit metadata.

### Transfer

Transfer:

1. May be initiated only by approved super gates.
2. Uses resumable signed chunks.
3. Verifies destination policy.
4. Preserves encrypted capsule confidentiality.
5. Retains only non-proprietary audit metadata at the source.

### Installation And Wake

At the destination:

1. Verify envelope integrity, signature, expiry, replay protection, and policy.
2. Verify complete capsule manifest.
3. Decrypt into protected local storage.
4. Verify runner and model attestation.
5. Restore memory and relationship continuity.
6. Register the agent's address privately with the local Prime BossGate.
7. Wake the dedicated runner.
8. Acknowledge successful installation.

### Source Retirement

After acknowledged installation:

1. Remove source profile traces.
2. Remove source runtime copy.
3. Remove source private model and checkpoints.
4. Remove source memory vault.
5. Remove source capability vault.
6. Remove source package artifacts.
7. Retain non-proprietary movement audit metadata only.

## Security Model

1. Hidden capsules encrypt all non-public artifacts.
2. Each agent owns private keys or protected per-agent key references.
3. Travel packages are encrypted before leaving protected storage.
4. Prime BossGate address enumeration is role- and node-type-gated.
5. Dream training requires signed policy, resource clearance, checkpointing, evaluation, and rollback.
6. Skill teaching and live tool trading require consent and audit.
7. Dead-agent inheritance requires verified lifecycle state.
8. Promotion requires explicit authorization.
9. Rarity mutation is forbidden.
10. No successful move leaves a runnable duplicate at the source.

## Staged Specifications

This umbrella design is implemented through six focused specs.

### Stage 1: Capsule Schema And Identity Boundary

Define:

1. Capsule manifest schema
2. Public identity card
3. Encrypted vault layout
4. Rarity
5. Sealed runtime lineage
6. Lifecycle states

### Stage 2: Gifted Portable AI Runner

Extract:

1. Neutral portable runner template
2. RuneForge personalized runner separation
3. Template versioning and signing
4. Descendant creation flow
5. Dedicated per-agent runner bootstrap

### Stage 3: Private Memory Vault

Unify:

1. Existing SQLite interaction memory
2. Social logs
3. Refusals
4. Retirements
5. RuneForge relationship memory
6. Per-agent encryption and travel serialization

### Stage 4: Dreams And Checkpoints

Implement:

1. Dream eligibility scheduler
2. Resource checks
3. Signed checkpoints
4. Candidate-weight training
5. Evaluation
6. Rollback
7. Sigil-lineage evolution
8. Security-admin controls

### Stage 5: Capability Evolution

Implement:

1. Skill teaching with capacity checks
2. Trainer-authorized unlearning
3. Forge-issued tools
4. Mutual-consent live tool trades
5. Dead-agent inheritance
6. Explicit rank promotion
7. Immutable rarity enforcement

### Stage 6: Full-Capsule BossGate Move

Implement:

1. Full capsule packaging
2. Chunked encrypted transport
3. Destination install and wake
4. Prime-gate-only address discovery
5. Source secure retirement
6. End-to-end duplicate-residue tests

## Testing Strategy

Each stage requires test-first implementation and must prove:

1. Hidden public cards never leak sealed fields.
2. Hidden capsule artifacts are encrypted at rest and in transit.
3. Descendants retain sealed RuneForge ancestry.
4. Descendants do not depend on RuneForge after creation.
5. Dreams cannot start while active, queued, or traveling.
6. Dream rollback restores signed pre-dream state.
7. Skill teaching respects capacity and policy.
8. Tool trades require mutual consent.
9. Dead-agent inheritance rejects non-dead donors.
10. Promotions require authorization.
11. Rarity cannot mutate.
12. Ordinary gates cannot enumerate addresses.
13. Prime gates can privately resolve addresses.
14. Successful travel leaves no runnable source duplicate.
15. Memory and relationship continuity survive travel.

## Documentation Updates

As stages land, update:

1. `docs/AgentForge_readme.md`
2. `docs/agentforge_requirements.md`
3. `docs/agentmaker_requirements.md`
4. `docs/agents_bossgate_agentforge_schema_guide.txt`
5. `docs/bossgate_protocol.md`
6. `docs/bossgate_connector.md`
7. `docs/bossgate_connector_todo.md`

