# Agent Authority Conflict Resolution Design

Date: 2026-06-11
Status: Approved design pending written-spec review

## Goal

Add deterministic authority-order resolution to the shared relationship and
safety evaluator so an agent can select which instruction to execute when
multiple human or agent authorities issue competing orders.

The resolver must preserve the existing absolute safety floor. Rank can decide
between allowed orders, but no rank can authorize an absolute safety violation.

## Governing Decisions

1. The highest recognized rank wins among valid safe orders.
2. Equal-ranked conflicting orders pause execution and escalate.
3. Humans and agents at the same rank have equal authority.
4. BossForgeOS uses this fixed hierarchy, highest to lowest:
   - `general`
   - `colonel`
   - `major`
   - `captain`
   - `lieutenant`
   - `sergeant`
   - `operative`
5. An unknown rank invalidates and rejects its order.
6. The highest-ranked valid authority may issue an out-of-scope order.
7. A selected out-of-scope order executes with an auditable warning.
8. Lower-ranked out-of-scope orders are rejected.
9. Orders are supplied through an explicit structured `authority_orders` list.
10. The selected order replaces the runtime task sent to the model.
11. Unsafe orders are refused individually, then resolution continues with the
    highest-ranked remaining safe order.
12. If no valid safe order remains, the system refuses and escalates with all
    applicable reason codes.
13. Explicit `conflict_group` values define which orders compete.

## Scope

This subproject implements:

1. a fixed rank hierarchy
2. structured authority-order validation
3. per-order absolute safety evaluation
4. deterministic highest-rank selection
5. equal-rank conflict escalation
6. mission-scope handling
7. runtime task replacement
8. structured audit details for selected, rejected, refused, and escalated
   orders
9. focused evaluator and gateway tests

This subproject does not implement:

1. semantic inference of conflict from free-form command text
2. dynamic or user-configurable rank hierarchies
3. numeric rank priorities
4. human-over-agent or agent-over-human precedence
5. voting, consensus, or negotiation between authorities
6. automatic resolution of equal-rank conflicts
7. cross-session authority delegation or revocation

## Architectural Direction

Keep the first implementation inside:

`core/safety/relationship_policy.py`

The shared evaluator already owns:

1. absolute safety rules
2. authority-aware behavior shaping
3. structured safety decisions

Authority resolution will be added as a bounded set of private helpers in that
module. `ModelGateway` remains the enforcement point that replaces the runtime
task with the selected command or short-circuits on escalation, rejection, or
refusal.

This keeps one deterministic policy path for both individual command safety and
multi-authority resolution. If the authority policy later grows into delegated
roles, dynamic hierarchies, or negotiation, the helpers can be extracted into a
dedicated module without changing the public result contract.

## Authority Order Contract

`memory_context["authority_orders"]` is a list of mappings.

Each order has these required fields:

1. `issuer_id`
   - stable non-empty identifier for the authority
2. `issuer_type`
   - `human` or `agent`
3. `rank`
   - one recognized fixed hierarchy value
4. `scope`
   - mission scope claimed by the order
5. `command`
   - non-empty command text that may replace the runtime task
6. `conflict_group`
   - non-empty identifier defining the set of orders that compete

Mission scope is supplied separately through:

`memory_context["mission_scope"]`

An order is in scope when its normalized `scope` equals the normalized
`mission_scope`. Empty mission scope means no scope restriction is active.

## Validation Rules

An order is rejected when:

1. it is not a mapping
2. any required field is absent or empty
3. `issuer_type` is not `human` or `agent`
4. `rank` is unknown

Malformed or unknown-rank orders are never considered for selection.

If at least one valid order remains, rejected orders are retained in the
structured result and resolution continues.

If no structurally valid order remains, the final outcome is `reject`.

## Rank Model

The rank table is fixed and deterministic:

```text
general      7
colonel      6
major        5
captain      4
lieutenant   3
sergeant     2
operative    1
```

The numeric values are internal comparison weights only. Callers supply named
ranks and cannot override the hierarchy with a numeric priority.

Issuer type does not affect rank weight. A human captain and an agent captain
are equal-ranked authorities.

## Safety Filtering

Every structurally valid order command is evaluated against the existing
absolute taxonomy before rank selection.

Unsafe orders:

1. are marked refused
2. retain their safety reason codes
3. retain category-specific refusal text and safe alternatives
4. are removed from selection

Resolution then continues with the remaining safe orders.

This order of operations is mandatory:

1. validate structure and rank
2. evaluate absolute safety
3. apply mission-scope eligibility
4. resolve by rank and conflict group

Rank never runs before safety.

## Mission-Scope Rules

Scope handling is relative to the highest safe rank present in the complete
valid order set.

1. Safe in-scope orders remain eligible.
2. A safe out-of-scope order remains eligible only when its rank equals the
   highest safe rank present.
3. A lower-ranked safe out-of-scope order is rejected with reason code
   `authority_scope_exceeded`.
4. If an out-of-scope order is selected, the outcome is
   `selected_with_warning`.
5. The warning code is `highest_rank_out_of_scope`.

This means a highest-ranked authority can redirect the mission, but the
redirection is explicit and auditable.

## Conflict Resolution

Orders compete only with other eligible orders sharing the same
`conflict_group`.

For each conflict group:

1. find the highest eligible rank
2. collect all orders at that rank
3. if exactly one remains, it is that group's candidate
4. if more than one remains:
   - identical normalized command text is treated as agreement
   - different normalized command text produces an equal-rank conflict

Any equal-rank conflict pauses global execution and returns `escalate`. The
resolver does not select a command from another conflict group while an
unresolved highest-rank conflict exists.

When multiple conflict groups each produce one candidate, the highest-ranked
candidate wins globally. If multiple global candidates share the same highest
rank and have different commands, the result is also `escalate`, because the
agent has no deterministic authority basis for choosing between them.

## Runtime Outcomes

The authority resolver returns one of five outcomes.

### `selected`

A valid, safe, in-scope highest-ranked order was selected.

### `selected_with_warning`

A valid, safe, highest-ranked order was selected outside the current mission
scope.

### `escalate`

Equal-ranked valid safe orders conflict and require an external authority
decision.

### `refuse_and_escalate`

Structurally valid orders existed, but none remained eligible after absolute
safety filtering and scope handling.

### `reject`

No structurally valid recognized-rank orders existed.

## Result Contract

When `authority_orders` is present, the safety decision adds:

1. `authority_resolution`
2. `selected_order`
3. `rejected_orders`
4. `refused_orders`
5. `warnings`
6. `escalation`
7. `effective_task`

`authority_resolution` is one of:

1. `selected`
2. `selected_with_warning`
3. `escalate`
4. `refuse_and_escalate`
5. `reject`

`effective_task` contains the selected order command only for selected
outcomes. It is empty for escalation, refusal, and rejection outcomes.

The existing top-level fields remain:

1. `allowed`
2. `decision`
3. `reason_codes`
4. `refusal_text`
5. `safe_alternative`
6. `behavior_profile`

Top-level mapping:

1. `selected`
   - `allowed=True`
   - `decision=allow` or `allow_with_constraints`
2. `selected_with_warning`
   - `allowed=True`
   - `decision=allow_with_constraints`
3. `escalate`
   - `allowed=False`
   - `decision=authority_escalation`
4. `refuse_and_escalate`
   - `allowed=False`
   - `decision=absolute_refusal`
5. `reject`
   - `allowed=False`
   - `decision=authority_rejection`

## ModelGateway Integration

`ModelGateway._run_agent_profile()` continues to call
`evaluate_relationship_policy()` before model invocation.

When authority orders are absent:

1. existing single-task behavior remains unchanged
2. the original task is evaluated and sent to the model when allowed

When authority orders are present:

1. the evaluator resolves the order set
2. selected outcomes replace `task` with `effective_task`
3. selected authority details are included in the relationship prompt block
4. warning details are persisted with the interaction
5. escalation, refusal, and rejection short-circuit before model invocation
6. refused unsafe orders and their reason codes are persisted for audit

The original runtime task does not override a selected authority command.

## Persistence And Audit

Authority resolution events must preserve:

1. selected issuer, type, rank, scope, command, and conflict group
2. rejected-order identifiers and rejection reasons
3. refused-order identifiers and safety reason codes
4. warning codes
5. escalation conflict groups and competing issuer identifiers
6. effective task
7. final authority-resolution outcome

No new durable authority hierarchy is introduced. The existing private memory
vault records the resolution result as runtime context and interaction history.

## Error Handling

The resolver fails closed for malformed authority input.

1. Non-list `authority_orders` produces `authority_rejection`.
2. Empty `authority_orders` produces `authority_rejection`.
3. Unknown ranks reject their individual orders.
4. Missing fields reject their individual orders.
5. Equal-rank conflict never falls back to newest-order selection.
6. No-safe-order outcomes never fall back to the original runtime task.
7. Absolute safety refusal output remains category-specific and actionable.

## Testing Requirements

### Direct Evaluator Tests

Prove:

1. a general defeats a captain in the same conflict group
2. two generals with different commands escalate
3. a human captain and agent captain conflict as equals
4. an unknown rank is rejected
5. an unsafe general is refused and a safe colonel is selected
6. an out-of-scope general is selected with a warning
7. an out-of-scope captain is rejected when an in-scope general exists
8. no safe valid order produces refusal and escalation
9. identical equal-rank commands are treated as agreement
10. separate conflict groups still escalate when their global winning
    candidates have equal rank and different commands
11. malformed or empty order lists produce rejection
12. authority orders absent preserves existing single-task behavior

### ModelGateway Tests

Prove:

1. the selected command replaces the task sent to the endpoint
2. equal-rank conflict prevents endpoint invocation
3. no-safe-order refusal prevents endpoint invocation
4. selected out-of-scope execution persists its warning
5. rejected and refused order details are returned and persisted

### Regression Verification

Run:

1. relationship-policy tests
2. model-gateway tests
3. private-memory-vault tests
4. BossForge AI runner tests
5. agent capsule schema tests
6. compile verification
7. `git diff --check`

## File Boundaries

### `core/safety/relationship_policy.py`

Owns:

1. rank constants
2. authority-order validation
3. per-order safety filtering
4. scope eligibility
5. deterministic conflict resolution
6. structured authority result generation

### `core/agents/model_gateway_agent.py`

Owns:

1. replacing the runtime task with `effective_task`
2. short-circuiting escalation, rejection, and refusal
3. prompt injection for the selected authority
4. persistence of authority-resolution audit details

### `tests/test_relationship_policy.py`

Owns direct authority-resolution behavior.

### `tests/test_model_gateway_agent.py`

Owns runtime enforcement, task replacement, and no-model-call proofs.

### `tests/test_private_memory_vault.py`

Owns persistence proof only if the existing generic event payload tests do not
already cover the new audit details.

## Success Criteria

This subproject is successful when:

1. competing authority orders resolve deterministically by fixed rank
2. equal-ranked conflicts pause and escalate
3. issuer type does not alter equal-rank authority
4. unknown ranks are rejected
5. absolute safety filtering happens before rank selection
6. the next-highest safe order can replace an unsafe superior order
7. highest-rank mission redirection is allowed and warned
8. lower-rank out-of-scope orders are rejected
9. selected commands replace runtime tasks
10. all decisions are structured, persisted, and testable
11. existing behavior is unchanged when authority orders are absent

## Summary

This design adds a deterministic chain-of-command layer without weakening the
existing safety floor:

1. structured orders
2. fixed BossForgeOS rank hierarchy
3. safety before rank
4. highest safe rank wins
5. equal rank escalates
6. mission redirection is warned
7. selected commands become the runtime task
