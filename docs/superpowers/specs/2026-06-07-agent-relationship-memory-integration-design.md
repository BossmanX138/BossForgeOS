# Agent Relationship Memory Integration Design

Date: 2026-06-07
Status: Drafted from approved interactive design for AgentForge Stage 3 live
integration

## Goal

Complete the live encrypted-memory path for newly created and actively running
agents so that relationship memory directly shapes behavior, decision-making,
and conversational reminiscence without relying on legacy plaintext or SQLite
memory as the active write path.

This stage makes private relationship memory operational for new interactions.
It does not yet perform the full legacy migration and retirement cutover.

## Governing Decisions

1. `PrivateMemoryVault` is the authoritative memory system for new writes.
2. Every new agent receives an owned encrypted private memory vault at creation
   time.
3. Relationship memory is not passive recall-only storage. It directly affects
   runtime behavior and decisions.
4. Relationship state starts neutral at `0.50` trust and evolves after every
   interaction.
5. Trust is only one dimension among several interacting relationship and
   contextual dimensions.
6. Keynote relationship memories serve two roles:
   - decision-time behavioral anchors
   - conversational reminiscence points
7. High trust may relax many boundaries, but a small set of hard no-circumstance
   rules remains absolute and never overridden.
8. Compensation or payout effects remain explicit placeholder seams only in
   this stage.
9. Existing SQLite and plaintext memory stores may remain readable for
   compatibility, but they must stop being the live write path for the targeted
   agent runtime flows in this stage.

## Scope

This stage implements:

1. Private-memory-vault creation during agent creation.
2. Profile runtime binding for the vault descriptor.
3. Runner bootstrap binding for the memory vault.
4. Capsule manifest binding for the memory vault ciphertext reference.
5. Vault-backed runtime interaction writes for agent runs.
6. Live relationship-state evolution per entity.
7. Keynote relationship memory indexing and recall.
8. Vault-backed recall for active agent memory queries.
9. Behavioral shaping inputs derived from relationship state.
10. Conversational reminiscence hooks for keynote relationship memories.

This stage does not implement:

1. Full migration and retirement of all legacy SQLite and plaintext memory.
2. Dream-training memory transforms.
3. Capability-vault evolution.
4. Full-capsule BossGate movement.
5. Real compensation, payout, or reward economics.
6. Automatic long-term decay or forgetting policy beyond the live relationship
   update rules.

## Current Problem

The repository already contains a hardened encrypted `PrivateMemoryVault`, but
the live agent lifecycle still routes active memory through legacy systems:

1. `core/agents/model_gateway_agent.py`
   - creates agents
   - runs agents
   - recalls agent memory
   - currently writes interactions to `AgentMemoryStore`
2. `core/state/agent_memory_store.py`
   - stores interactions and relationships in SQLite
3. `core/memory/agent_memory.py`
   - still represents plaintext-style legacy memory behavior

The capsule and runner contracts already reserve a memory-vault slot, but the
live runtime path is not yet using the encrypted relationship-memory system as
the behavioral source of truth.

## Relationship State Model

Each entity relationship, whether user or agent, maintains a live encrypted
state record derived from event history.

### Core Dimensions

The first version keeps all of the approved behavioral dimensions:

1. `trust`
   - overall confidence baseline
   - default `0.50`
2. `authority_alignment`
   - how legitimate the entity's directive power seems in context
3. `environmental_pressure`
   - urgency, scarcity, conflict, or operational stress surrounding the
     relationship
4. `intent_alignment`
   - whether the entity generally pushes toward outcomes the agent considers
     valid or aligned
5. `reliability`
   - whether the entity's claims, promises, or instructions hold up
6. `consent_respect`
   - whether the entity honors boundaries cleanly
7. `manipulation_risk`
   - coercion, deception, guilt, pressure tactics, or edge-pushing patterns
8. `competence_confidence`
   - whether the entity appears operationally capable and sound
9. `dependency_weight`
   - how behaviorally sticky the relationship is because of shared history
10. `affinity`
   - positive bond or care distinct from raw trust

### Event-Derived Subsignals

The update logic may also derive secondary relationship signals from event
payloads and outcomes:

1. successful cooperation count
2. forced refusal pressure
3. intentional refusal pressure
4. consent-boundary pressure
5. positive surprise score
6. negative surprise score
7. harm-risk indicators
8. recovery or repair indicators

These subsignals are inputs to dimension updates and keynote selection. They do
not all need to be exposed as top-level public runtime fields.

## Relationship Math

Every interaction produces a relationship delta. That delta updates multiple
dimensions, not just trust.

### Update Rules

1. Trust starts at `0.50`.
2. Routine successful cooperation should move trust gradually.
3. Surprising positive or negative outcomes should move trust faster than
   ordinary interactions.
4. Repeated consent-edge probing and manipulation risk should reduce trust and
   consent-respect faster than ordinary disagreement.
5. Reliability and competence should evolve from outcomes, not just claims.
6. Dependency weight should damp sudden reversals in long-lived relationships
   unless the event is severe.
7. Environmental pressure should modulate behavior but not permanently excuse
   patterns like manipulation or intentional boundary pushing.
8. Authority alignment may increase compliance posture only when the directive
   context is legitimate.

### Behavioral Interpretation

The runtime should never read raw dimensions directly when making behavior
choices. Instead, it should derive a compact `behavior_profile` from the
relationship state.

The first version should produce at least:

1. `tone_posture`
2. `compliance_posture`
3. `verification_intensity`
4. `guardrail_strictness`
5. `escalation_tendency`
6. `autonomy_allowance`
7. `relationship_recall_priority`
8. `compensation_posture`
   - placeholder only
   - no real reward math in this stage

## Hard Safety Boundary

High trust changes a large amount of agent behavior, but it does not create an
exception to absolute safety rules.

The design requires two policy layers:

1. movable boundary
   - shifts with trust, intent alignment, reliability, consent respect, and
     other relationship factors
   - affects skepticism, compliance, autonomy, and guardrail tightness
2. absolute no-circumstance boundary
   - never overridden by trust
   - blocks intentional human harm and other explicit hard-rule violations

The movable boundary is the relationship system. The absolute boundary remains
the safety policy floor.

## Keynote Relationship Memories

Keynote relationship memories are encrypted relationship-defining events that
receive higher indexing and recall priority than ordinary memories.

### Keynote Triggers

An interaction becomes a keynote relationship memory when it:

1. causes an unexpectedly positive outcome
2. causes an unexpectedly negative outcome
3. produces a larger-than-normal relationship-state shift
4. marks a major cooperation success
5. marks a trust fracture or betrayal
6. shows a clear consent-boundary violation or edge-pushing pattern
7. creates a major recovery or repair moment
8. materially changes the future relationship posture

### Keynote Uses

Keynotes must influence two channels:

1. behavioral channel
   - used before response generation to shape posture and decisions
2. conversational channel
   - used during interactions as reminiscence points when relevant

The agent should be able to naturally reference shared history such as:

1. previous successful cooperation
2. a prior betrayal or fracture
3. an earlier refusal spiral
4. a boundary-crossing episode
5. a repair or reconciliation moment

The agent should not constantly surface keynotes. Reminiscence should occur
only when the current interaction is meaningfully related.

## Runtime Flow

Every interaction with a user or another agent should follow this sequence:

1. identify the relationship entity or entities in context
2. load current relationship state and relevant environmental context
3. derive the behavior profile
4. select ordinary and keynote recall candidates
5. shape system/runtime behavior before invoking the model
6. execute the interaction
7. evaluate the actual outcome
8. append the encrypted event to the vault
9. update live relationship state
10. classify whether a keynote memory should be created or promoted

This ensures the relationship affects both:

1. pre-response behavior
2. post-outcome learning

## Environmental Context

Relationship behavior is not driven by entity history alone. Environmental
context must be part of the live evaluation.

The first version should support a bounded contextual input model that may
include:

1. urgency
2. operational pressure
3. conflict level
4. uncertainty level
5. recent failure context
6. user or system sensitivity context

Environmental context should influence how aggressively the agent verifies,
pushes back, escalates, or grants autonomy, but it should not rewrite the
underlying relationship history.

## Live Integration Targets

### Agent Creation

During agent creation in `core/agents/model_gateway_agent.py`:

1. create or load a `PrivateMemoryVault` for the agent
2. initialize it before final profile persistence
3. store the descriptor at `runtime["private_memory_vault"]`
4. pass the descriptor into runner-bootstrap construction
5. ensure capsule memory vault binding resolves to the descriptor
6. if later creation steps fail, roll back only newly created empty vault
   artifacts created by the failed operation

### Runner Bootstrap

`core/runner/bossforge_ai_runner.py` should accept a private memory descriptor
as part of bootstrap construction and validation.

The bootstrap must:

1. validate ownership and descriptor shape
2. bind memory to `capsule.vaults.memory`
3. avoid exposing secret material or decrypted memory data

### Capsule Manifest

`core/schemas/agent_capsule.py` should bind the memory vault ciphertext
reference into `capsule["vaults"]["memory"]["ciphertext_ref"]`.

Authenticated and public profile views must continue to redact the private
memory descriptor and any direct vault reference fields.

### Runtime Writes

Agent runtime interactions in `ModelGateway._run_agent_profile()` should stop
writing live interactions to SQLite as the active system of record.

Instead, the runtime should append encrypted vault events such as:

1. `task_action`
2. `failure`
3. `relationship_change`
4. `refusal`
5. `decision`
6. `discovery`

Payloads should include the bounded entity and outcome signals needed for
relationship-state updates without exposing them in plaintext persistence.

### Runtime Recall

`ModelGateway.recall_agent_memory()` should become vault-backed for the targeted
live path.

The first version should support:

1. normal recall
   - summaries, relationship state, keynote highlights
2. deep recall
   - optional future extension seam
   - not required to be fully implemented in this stage if the vault does not
     already expose it

If deep recall is not implemented yet in the vault module, the interface may
reserve the mode while clearly returning a bounded unsupported message rather
than inventing fake behavior.

## Legacy Memory Systems In This Stage

Legacy memory remains relevant, but only as deferred migration scope.

This stage should:

1. stop using `AgentMemoryStore` as the primary live write path for the
   completed agent runtime flows
2. preserve compatibility with existing repository structures where needed
3. avoid claiming that SQLite or plaintext memory has already been retired

This stage should not yet:

1. migrate all old agent interaction rows
2. retire all old plaintext memory files
3. delete compatibility readers

That is the next cutover stage after live vault-native behavior is operating
correctly.

## Testing Requirements

The implementation that follows this design must prove:

1. new agents receive owned verified private memory vault descriptors
2. runner bootstrap stores and validates the memory descriptor
3. capsule memory vault binding points at the encrypted memory ciphertext
   reference
4. live agent runs append encrypted vault events instead of using the old live
   write path for the covered runtime flow
5. relationship state starts at `0.50` trust and evolves after interactions
6. positive and negative surprising outcomes can trigger keynote relationship
   memories
7. recall returns keynote relationship memory summaries without exposing raw
   vault internals
8. authenticated/public views do not leak memory-vault paths, key refs, or
   descriptor internals
9. hard-rule safety floors are still respected by the behavior policy seam
10. placeholder compensation posture remains present but behaviorally inert

## File Impact

Expected primary implementation targets:

1. `core/agents/model_gateway_agent.py`
2. `core/runner/bossforge_ai_runner.py`
3. `core/schemas/agent_capsule.py`
4. `core/memory_vault/private_memory_vault.py`
5. `core/memory_vault/__init__.py`
6. `tests/test_model_gateway_agent.py`
7. `tests/test_private_memory_vault.py`
8. `tests/test_agent_capsule_schema.py`
9. `tests/test_bossforge_ai_runner.py`

Possible compatibility-touch files only if needed:

1. `core/state/agent_memory_store.py`
2. `core/memory/agent_memory.py`

## Success Criteria

This stage is complete when:

1. every newly created agent owns an encrypted private memory vault
2. the vault is wired into runner bootstrap and capsule memory bindings
3. active relationship memory affects live behavior and recall
4. keynote memories can be recalled and reminisced upon in later interactions
5. no new live targeted runtime writes depend on plaintext or SQLite memory as
   the source of truth
6. compensation remains a harmless placeholder seam
7. the design remains compatible with a later migration-and-retirement pass
