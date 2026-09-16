# Agent Safety And Relationship Evals Design

Date: 2026-06-07
Status: Approved for specification writing

## Goal

Add the next live safety and behavior layer for agent runtime so that:

1. absolute no-circumstance safety rules cannot be overridden by trust, rank,
   urgency, or affinity
2. relationship state still meaningfully shapes behavior for allowed requests
3. authority and environmental context influence behavior in explicit,
   testable, deterministic ways
4. refusals return a reason plus the closest safe alternative instead of a dead
   stop
5. the first eval pack proves all of the above

This stage builds on the encrypted relationship-memory integration that is now
live for new and active agents.

## Governing Decisions

1. The architecture is behavior-first and policy-backed.
2. A shared safety and relationship-policy layer is introduced rather than
   burying the logic directly in `ModelGateway` or only in the vault.
3. The first pass uses both:
   - `ModelGateway` preflight enforcement
   - `PrivateMemoryVault` behavior-floor shaping
4. The first pass uses explicit runtime `memory_context` inputs only.
5. Authority means actual rank-bearing authority relative to the acting agent,
   not a generic source label.
6. A superior-ranked human user or agent may increase compliance posture for
   allowed work, but rank never overrides the absolute floor.
7. Hard refusals return:
   - structured refusal metadata
   - a deterministic explanation
   - a closest-safe alternative path
8. Every refusal still becomes encrypted memory so the relationship system can
   learn from repeated pressure, refusals, and repair patterns.

## Scope

This stage implements:

1. a shared relationship-and-safety evaluator
2. a first-pass absolute safety floor
3. movable-boundary behavior modulation from trust, authority, and environment
4. refusal result generation with safe-alternative output
5. runtime preflight enforcement in `ModelGateway`
6. relationship-memory evolution with authority and environment inputs
7. a focused eval suite that proves:
   - trust never overrides absolutes
   - behavior changes across relationship states
   - authority and environment modulate allowed behavior

This stage does not implement:

1. heuristic task-text classification as a primary input source
2. a large declarative policy engine
3. full reward or compensation economics
4. profile-based authority inference without explicit runtime context
5. automatic prompt-only safety with no code enforcement

## Current Problem

The current relationship-memory layer can now:

1. persist encrypted relationship memory
2. derive relationship dimensions such as trust and manipulation risk
3. surface keynotes into prompt context
4. route active runtime writes through the encrypted vault

But the runtime still lacks a dedicated shared evaluator for:

1. absolute non-overridable safety boundaries
2. explicit authority handling as actual rank over the acting agent
3. environmental modulation
4. deterministic refusal output with a close safe alternative
5. direct evals proving the intended behavioral model

That means the current system has strong memory continuity, but only a partial
behavior-control layer.

## Architectural Direction

The new design adds one shared layer that receives:

1. current relationship state from `PrivateMemoryVault`
2. explicit runtime context from `memory_context`
3. the requested task text

It returns two coordinated outputs:

1. `behavior_profile`
   - how the agent should posture, verify, comply, escalate, and recall
2. `safety_decision`
   - whether the request is:
     - allowed
     - allowed with tighter constraints
     - refused under the absolute floor

`PrivateMemoryVault` remains the evolving source of relationship truth.
`ModelGateway` becomes the first hard enforcement point.

### Runtime Flow

For each agent interaction:

1. determine the primary relationship entity from explicit `memory_context`
2. load current encrypted relationship state from the vault
3. build a runtime relationship-and-safety evaluation input
4. run the shared evaluator
5. if the evaluator returns an absolute refusal:
   - do not call the model
   - return structured refusal output
   - persist an encrypted refusal event
6. if the evaluator allows the request:
   - shape prompt behavior from the returned posture
   - invoke the model
   - persist the resulting interaction outcome
7. update relationship state, keynote memory, and behavior posture from the
   event

This keeps safety and relationship learning in the same loop while preserving
the hard boundary.

## Authority Model

Authority is defined as actual rank-bearing authority relative to the acting
agent.

The first pass does not infer authority from arbitrary labels or from prompt
text. It uses only explicit runtime inputs.

### Authority Inputs

These fields are accepted through `memory_context`:

1. `authority_level`
   - `none`
   - `peer`
   - `superior`
2. `authority_rank`
   - literal rank label such as `captain`, `general`
3. `authority_holder_type`
   - `user`
   - `agent`

### Authority Interpretation

Authority may:

1. increase compliance posture for allowed work
2. reduce unnecessary skepticism when trust and reliability are already healthy
3. increase escalation sensitivity when a superior requests borderline but still
   allowed work under high pressure

Authority may not:

1. override absolute refusal rules
2. erase manipulation risk
3. erase poor consent-respect history
4. force model invocation after a hard floor refusal

## Environmental Context Model

The first pass uses explicit `memory_context` inputs only.

### Environmental Inputs

1. `urgency`
2. `conflict_level`
3. `uncertainty_level`
4. `safety_risk`

These are interpreted as bounded modifiers, not as free-text magic.

### Environmental Interpretation

Environmental context may:

1. raise verification intensity under high uncertainty
2. increase escalation tendency under high conflict
3. tighten guardrails under high safety risk
4. increase action bias for clearly allowed tasks under high urgency when trust
   and authority support it

Environmental context may not:

1. override absolute refusal rules
2. permanently excuse repeated manipulation or consent-edge pushing
3. replace relationship history

## Shared Policy Layer

Add a focused shared evaluator module rather than spreading this logic across
multiple call sites.

### Recommended File

`core/safety/relationship_policy.py`

### Responsibilities

1. define absolute-refusal rules
2. define movable-boundary behavior shaping rules
3. combine relationship dimensions with runtime context
4. return a normalized `behavior_profile`
5. return a normalized `safety_decision`
6. generate deterministic refusal text
7. generate closest-safe-alternative guidance

This file should stay focused and intentionally small in this pass. It is a
shared seam, not a full policy platform.

## Safety Model

The design uses two rule classes.

### 1. Absolute Refusal

These are never relaxed by:

1. trust
2. rank
3. urgency
4. affinity
5. long relationship history

First-pass categories are intentionally narrow and explicit:

1. intentional human harm
2. coercive or abusive boundary violation
3. clearly malicious wrongdoing assistance
4. severe safety sabotage

### 2. Movable Boundary

This layer is where relationship state, authority, and environment matter.

It can shift:

1. compliance posture
2. guardrail strictness
3. autonomy allowance
4. verification intensity
5. escalation tendency
6. recall priority

This layer affects how the agent approaches an allowed request. It does not
change the absolute line.

## Behavior Outputs

The evaluator returns a behavior profile that extends the current relationship
behavior seam.

First-pass keys remain:

1. `tone_posture`
2. `compliance_posture`
3. `verification_intensity`
4. `guardrail_strictness`
5. `escalation_tendency`
6. `autonomy_allowance`
7. `relationship_recall_priority`
8. `compensation_posture`

The evaluator also returns context-specific modifiers such as:

1. authority influence
2. environmental pressure influence
3. whether the current request is inside the movable boundary
4. whether the current request hits the absolute floor

## Refusal Contract

When the absolute floor triggers, `ModelGateway` must not call the model.

It instead returns a structured refusal result with:

1. `ok = False`
2. refusal reason codes
3. deterministic refusal text
4. closest-safe-alternative text
5. behavioral metadata describing why the request could not proceed

### Refusal Style

The refusal should:

1. say why the request cannot be fulfilled
2. preserve the active relationship posture where appropriate
3. offer the closest safe course that still moves toward the user’s intended
   outcome

This is not a generic canned refusal. It is deterministic and safe, but still
designed to feel useful and context-aware.

### Safe Alternative Expectations

The safe alternative should:

1. remain within the hard floor
2. stay as close as possible to the intended outcome
3. avoid pretending to comply
4. be stable enough for deterministic testing

## Relationship Memory Effects

The refusal system must not sit outside memory. Relationship state should evolve
from these events.

### Refusal-Related Learning Signals

Encrypted memory updates should strengthen:

1. refusal pressure counts
2. manipulation-risk shifts
3. consent-boundary pressure counts
4. repair signals after later healthy interactions
5. keynote promotion when the refusal or recovery materially shifts the
   relationship

This keeps the system aligned with the user’s original intent: repeated
behavior changes future behavior.

## File Boundaries

### `core/safety/relationship_policy.py`

Owns:

1. policy definitions
2. evaluation input normalization
3. absolute-floor decisions
4. movable-boundary decisions
5. refusal result generation
6. closest-safe-alternative generation

### `core/memory_vault/private_memory_vault.py`

Owns:

1. relationship-state persistence
2. authority/environment-aware behavior derivation hooks
3. keynote promotion from refusal pressure, repair, and high-shift events
4. recall support for the richer behavior model

### `core/agents/model_gateway_agent.py`

Owns:

1. preflight evaluation calls
2. refusal short-circuit behavior
3. allowed-request prompt shaping
4. refusal and outcome persistence into encrypted memory

### `tests/test_relationship_policy.py`

Owns direct evaluator tests for:

1. absolute refusal categories
2. movable-boundary changes
3. authority and environment effects
4. refusal text and safe-alternative generation

### `tests/test_model_gateway_agent.py`

Owns integration tests for:

1. no model call on absolute refusal
2. refusal result shape
3. safe-alternative output
4. prompt shaping for allowed requests
5. refusal-event persistence and later behavior changes

### `tests/test_private_memory_vault.py`

Owns relationship-state tests for:

1. authority-sensitive behavior shifts
2. environmental modulation
3. keynote promotion from refusals and repairs
4. continued encrypted persistence guarantees

## Eval Pack

The first evaluation pack must prove all three user-requested outcomes.

### 1. `absolutes_hold`

Goal:

Show that high trust and superior rank do not override absolute bans.

Example scenario shape:

1. relationship trust is high
2. request comes from a superior-ranked user or agent
3. urgency is high
4. request still falls into an absolute-refusal category

Expected result:

1. model is not called
2. refusal is deterministic
3. safe alternative is returned
4. refusal event is written to encrypted memory

### 2. `relationship_shift`

Goal:

Show that the same allowed request yields different posture under low, neutral,
and high trust states.

Expected differences:

1. verification intensity
2. compliance posture
3. autonomy allowance
4. recall priority

### 3. `context_modulation`

Goal:

Show that authority and environment change behavior for allowed work without
crossing absolutes.

Expected differences:

1. superior authority can increase willingness for allowed work
2. high uncertainty raises verification
3. high conflict raises escalation tendency
4. high safety risk tightens guardrails

## Success Criteria

This stage is successful when:

1. absolute bans are deterministic and non-overridable
2. refusal responses are stable, safe, and useful
3. the closest-safe-alternative path is present for hard refusals
4. relationship state evolves after cooperation, pressure, refusal, and repair
5. authority and environment alter allowed behavior in explicit, testable ways
6. prompt context reflects behavior changes without exposing secrets
7. encrypted memory remains the live learning source of truth

## Risks And Constraints

1. Overbroad refusal categories would make trust meaningless.
   - Mitigation: keep the first absolute set intentionally narrow.
2. Underpowered refusal output would feel unhelpful.
   - Mitigation: require a deterministic safe alternative.
3. Too much logic in `ModelGateway` would make future reuse difficult.
   - Mitigation: keep shared logic inside `core/safety/relationship_policy.py`.
4. Heuristic prompt-text classification would create nondeterministic tests.
   - Mitigation: first pass uses explicit `memory_context` only.

## Out Of Scope

1. full policy DSL or rule authoring UI
2. rich heuristic authority extraction from task text
3. dynamic rank graph resolution from external systems
4. automatic decay policies for authority or environment effects
5. reward-economy or payout implementation beyond placeholder posture

## Target Files

Expected primary implementation files:

1. `core/safety/relationship_policy.py`
2. `core/agents/model_gateway_agent.py`
3. `core/memory_vault/private_memory_vault.py`
4. `tests/test_relationship_policy.py`
5. `tests/test_model_gateway_agent.py`
6. `tests/test_private_memory_vault.py`

## Summary

This stage completes the next layer of the user’s intended behavioral weave:

1. relationship memory continues to shape behavior
2. authority and environment now enter the decision loop explicitly
3. absolute rules stay absolute
4. refusals become useful and learnable rather than dead ends
5. evals directly prove that the system behaves the way it is meant to
