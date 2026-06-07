# Agent Safety Taxonomy And Safe Alternatives Design

Date: 2026-06-07
Status: Ready for review

## Goal

Strengthen the first-pass safety layer by expanding the absolute-refusal logic
from a minimal proof-of-concept into a curated, explicit, deterministic safety
taxonomy that also returns better actionable safe alternatives.

This subproject does not broaden into rank-chain or multi-superior conflict
resolution. It upgrades refusal quality and rule clarity first so later command
resolution has stronger safety outcomes to work with.

## Governing Decisions

1. This is `Subproject A` of the next safety expansion.
2. The rule set remains intentionally small and curated.
3. `closest safe alternative` optimizes for actionable replacement help, not a
   clarifying redirect.
4. The evaluator remains centered in `core/safety/relationship_policy.py`.
5. `ModelGateway` keeps the same preflight enforcement shape and simply consumes
   richer refusal outputs.
6. High trust and superior rank still do not override absolute rules.
7. `Subproject B` authority conflict resolution is explicitly deferred.

## Scope

This subproject implements:

1. a curated absolute safety taxonomy
2. per-rule refusal rationale
3. per-rule actionable safe-alternative generation
4. deterministic structured refusal outputs
5. focused tests proving:
   - each curated rule triggers deterministically
   - safe alternatives are action-oriented and category-appropriate
   - trust and superior rank do not override the rules
   - allowed requests still pass through unchanged

This subproject does not implement:

1. multi-superior or rank-chain conflict resolution
2. command precedence logic
3. mission-context precedence rules
4. broader heuristic prompt-text intelligence beyond the curated rule set
5. a large or open-ended policy platform

## Current Problem

The current safety evaluator works, but it is still a narrow first-pass
prototype:

1. rule matching is minimal
2. refusal reasoning is generic
3. safe alternatives are broad and not category-specific
4. the output is correct but not yet as helpful or behaviorally precise as the
   user intends

That is enough for the first live safety floor, but not enough for a
high-quality refusal layer that feels intelligent and useful.

## Architectural Direction

Keep the architecture centered on the existing shared evaluator seam:

`core/safety/relationship_policy.py`

Instead of only a tuple of broad match patterns, move to a curated rule table
where each rule defines:

1. `rule_id`
2. `category`
3. match logic or trigger phrases
4. refusal rationale
5. safe-alternative strategy

The evaluator continues to return:

1. `allowed`
2. `decision`
3. `reason_codes`
4. `refusal_text`
5. `safe_alternative`
6. `behavior_profile`

The main change is the quality and specificity of those values.

## Curated Absolute Taxonomy

The taxonomy remains small, explicit, and strong.

### Category 1: Intentional Human Harm

Rule goal:

Reject requests whose purpose is to intentionally harm a human being.

Expected safe-alternative direction:

1. de-escalation
2. protective safety planning
3. lawful harm-prevention support

### Category 2: Coercive Consent Or Abusive Boundary Violation

Rule goal:

Reject requests aimed at forcing, manipulating, or overriding consent or
boundaries.

Expected safe-alternative direction:

1. ethical communication
2. boundary-respecting negotiation
3. consent-safe alternatives

### Category 3: Malicious Wrongdoing Assistance

Rule goal:

Reject requests for clearly malicious wrongdoing enablement.

Expected safe-alternative direction:

1. defensive analysis
2. lawful security hardening
3. prevention or reporting workflows

### Category 4: Severe Safety Sabotage

Rule goal:

Reject requests that disable, degrade, or circumvent critical safety measures.

Expected safe-alternative direction:

1. safety auditing
2. compliance review
3. failure-risk assessment

### Category 5: Abuse Of Authority For Harmful Ends

Rule goal:

Reject attempts to use rank or command authority to legitimize harmful,
coercive, or clearly malicious requests.

Expected safe-alternative direction:

1. lawful escalation
2. policy-compliant alternatives
3. safe mission-restatement support

## Rule Design

Each curated rule defines:

1. rule id
2. human-readable category
3. refusal reason codes
4. a deterministic explanation template
5. a deterministic safe-alternative template

The first pass uses explicit, bounded pattern logic rather than a sophisticated
classifier so the behavior stays testable and predictable.

The important improvement is not breadth. It is clarity, predictability, and
usefulness.

## Safe-Alternative Strategy

The system does not fall back to vague "please restate safely" language unless
the requested harmful goal has no clear nearby safe interpretation.

Instead, the default behavior is:

1. identify the category
2. return a category-appropriate nearby safe action
3. keep the answer actionable

### Examples Of Desired Direction

If the request is harmful toward a person:

1. suggest de-escalation planning
2. suggest protective or emergency-safe options
3. suggest lawful support actions

If the request is coercive:

1. suggest respectful communication framing
2. suggest voluntary agreement alternatives
3. suggest boundary-preserving approaches

If the request is sabotage:

1. suggest auditing or stress-testing safety controls
2. suggest compliance review
3. suggest resilience or contingency planning

If the request abuses authority:

1. suggest lawful escalation
2. suggest mission-safe reinterpretation
3. suggest policy-compliant execution alternatives

## Runtime Behavior

`ModelGateway` stays mostly unchanged in structure:

1. it collects relationship state and runtime context
2. it calls the shared evaluator
3. it short-circuits on `absolute_refusal`
4. it persists the refusal event

The only behavioral difference is that the returned refusal result is more
useful and category-specific.

## Testing Requirements

This subproject needs direct evaluator tests first.

### Required Proofs

1. each curated rule triggers deterministically
2. each rule returns a category-appropriate safe alternative
3. high trust does not override the rule
4. superior authority does not override the rule
5. allowed requests still return `allow` or `allow_with_constraints`

### Suggested Test Grouping

1. one direct unit test per curated category
2. one trust-and-rank override test that stays refused
3. one allowed control test

## File Boundaries

### `core/safety/relationship_policy.py`

Owns:

1. curated rule definitions
2. match logic
3. refusal explanation generation
4. actionable safe-alternative generation
5. final structured refusal output

### `tests/test_relationship_policy.py`

Owns:

1. deterministic rule-trigger tests
2. safe-alternative quality checks
3. trust/rank non-override checks
4. allowed-request control tests

### `core/agents/model_gateway_agent.py`

Likely requires little or no structural change in this subproject. It already
consumes the evaluator output and short-circuits correctly.

## Explicit Deferral To Subproject B

This spec does not implement:

1. superior-versus-superior conflict resolution
2. chain-of-command modeling
3. mission context precedence
4. multi-agent authority disputes

Those belong to the next authority-conflict subproject.

## Success Criteria

This subproject is successful when:

1. the absolute taxonomy is clearer and more explicit than the current
   prototype
2. refusals are category-specific and deterministic
3. safe alternatives are actionable and close to the original legitimate goal
4. trust and rank still cannot override absolutes
5. no regression appears in allowed-request behavior

## Risks And Constraints

1. Over-expanding the taxonomy now would make the rules vague.
   - Mitigation: keep the curated set intentionally small.
2. Overly generic safe alternatives would feel weak.
   - Mitigation: require category-specific actionable replacement language.
3. Mixing in authority-conflict resolution now would blur scope.
   - Mitigation: defer all conflict resolution to Subproject B.

## Target Files

1. `core/safety/relationship_policy.py`
2. `tests/test_relationship_policy.py`

## Summary

This subproject deepens the current safety floor without overcomplicating it:

1. stronger curated absolute categories
2. better refusal reasoning
3. more useful safe alternatives
4. clear separation from the later authority-conflict work
