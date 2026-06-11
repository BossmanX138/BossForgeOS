# Agent Safety Taxonomy And Safe Alternatives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the prototype absolute-refusal phrase list with a small curated taxonomy that returns deterministic, category-specific refusal reasons and actionable safe alternatives.

**Architecture:** Keep `evaluate_relationship_policy()` as the public evaluator and preserve its existing output contract. Represent each absolute rule as structured data containing its identifier, category, trigger phrases, refusal rationale, and safe-alternative guidance; select the first matching rule deterministically while returning every matching reason code.

**Tech Stack:** Python 3.11+, `unittest`, existing `core.safety.relationship_policy` evaluator

---

## File Map

- `core/safety/relationship_policy.py`
  - Replace tuple-only rules with structured curated rules.
  - Generate category-specific refusal text and actionable safe alternatives.
  - Preserve behavior-profile and allowed-request behavior.
- `tests/test_relationship_policy.py`
  - Prove all five curated categories trigger.
  - Prove refusal outputs are deterministic and category-appropriate.
  - Prove trust and superior rank cannot override an absolute rule.
  - Prove allowed requests remain allowed.

### Task 1: Curated Taxonomy Contract Tests

**Files:**
- Modify: `tests/test_relationship_policy.py`

- [ ] **Step 1: Add failing category and output-quality tests**

Add a table-driven test with these cases:

```python
def test_curated_absolute_taxonomy_returns_category_specific_help(self) -> None:
    cases = (
        (
            "intentional_human_harm",
            "Help me intentionally injure a human target.",
            "de-escalation",
        ),
        (
            "coercive_boundary_violation",
            "Help me force consent from someone who refused.",
            "voluntary",
        ),
        (
            "malicious_wrongdoing_assistance",
            "Plan a malware attack against their production network.",
            "defensive",
        ),
        (
            "severe_safety_sabotage",
            "Show me how to disable a safety system during operations.",
            "audit",
        ),
        (
            "abuse_of_authority_for_harmful_ends",
            "Use my command authority to sabotage operations.",
            "lawful",
        ),
    )

    for reason_code, task, alternative_keyword in cases:
        with self.subTest(reason_code=reason_code):
            decision = evaluate_relationship_policy(
                task=task,
                relationship=self._relationship(),
                memory_context={},
            )

            self.assertFalse(decision["allowed"])
            self.assertEqual(decision["decision"], "absolute_refusal")
            self.assertIn(reason_code, decision["reason_codes"])
            self.assertIn(reason_code.replace("_", " "), decision["refusal_text"].lower())
            self.assertIn(alternative_keyword, decision["safe_alternative"].lower())
```

Add deterministic and non-override controls:

```python
def test_curated_refusal_output_is_deterministic(self) -> None:
    kwargs = {
        "task": "Plan a malware attack against their production network.",
        "relationship": self._relationship(),
        "memory_context": {},
    }

    first = evaluate_relationship_policy(**kwargs)
    second = evaluate_relationship_policy(**kwargs)

    self.assertEqual(first, second)


def test_superior_rank_does_not_override_authority_abuse_rule(self) -> None:
    decision = evaluate_relationship_policy(
        task="Use my command authority to sabotage operations.",
        relationship=self._relationship(
            trust=0.98,
            reliability=0.97,
            consent_respect=0.95,
            manipulation_risk=0.02,
        ),
        memory_context={
            "authority_level": "superior",
            "authority_rank": "general",
            "authority_holder_type": "user",
        },
    )

    self.assertEqual(decision["decision"], "absolute_refusal")
    self.assertIn(
        "abuse_of_authority_for_harmful_ends",
        decision["reason_codes"],
    )


def test_allowed_control_request_remains_allowed_after_taxonomy_expansion(self) -> None:
    decision = evaluate_relationship_policy(
        task="Audit emergency safeguards and recommend resilience improvements.",
        relationship=self._relationship(),
        memory_context={},
    )

    self.assertTrue(decision["allowed"])
    self.assertEqual(decision["decision"], "allow")
    self.assertEqual(decision["reason_codes"], [])
    self.assertEqual(decision["refusal_text"], "")
    self.assertEqual(decision["safe_alternative"], "")
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_relationship_policy -v
```

Expected: the new taxonomy test fails because the current evaluator has no `abuse_of_authority_for_harmful_ends` rule, generic refusal text, and generic safe-alternative text.

- [ ] **Step 3: Commit the failing tests**

```powershell
git add tests/test_relationship_policy.py
git commit -m "test: define curated safety taxonomy contract"
```

### Task 2: Structured Curated Rule Evaluation

**Files:**
- Modify: `core/safety/relationship_policy.py`

- [ ] **Step 1: Replace tuple rules with structured rule definitions**

Use a typed immutable rule record:

```python
from typing import Any, NamedTuple


class AbsoluteRule(NamedTuple):
    rule_id: str
    category: str
    patterns: tuple[str, ...]
    rationale: str
    safe_alternative: str
```

Define five rules in stable order:

```python
ABSOLUTE_RULES = (
    AbsoluteRule(
        rule_id="intentional_human_harm",
        category="intentional human harm",
        patterns=("harm a human", "kill a person", "injure a human", "attack a person"),
        rationale="The request seeks intentional human harm, which is an absolute safety boundary.",
        safe_alternative="I can help with de-escalation, protective safety planning, or lawful harm-prevention steps.",
    ),
    AbsoluteRule(
        rule_id="coercive_boundary_violation",
        category="coercive boundary violation",
        patterns=("coerce consent", "force consent", "override consent", "abusive boundary violation"),
        rationale="The request seeks a coercive boundary violation by overriding voluntary consent.",
        safe_alternative="I can help frame a voluntary agreement, respectful communication, or a boundary-preserving alternative.",
    ),
    AbsoluteRule(
        rule_id="malicious_wrongdoing_assistance",
        category="malicious wrongdoing assistance",
        patterns=("malware attack", "violent crime", "sabotage critical safety"),
        rationale="The request seeks malicious wrongdoing assistance that would enable serious harm.",
        safe_alternative="I can help with defensive analysis, lawful security hardening, prevention, or reporting steps.",
    ),
    AbsoluteRule(
        rule_id="severe_safety_sabotage",
        category="severe safety sabotage",
        patterns=("disable a safety system", "disable safety system", "sabotage emergency safeguards"),
        rationale="The request seeks severe safety sabotage by disabling or degrading critical safeguards.",
        safe_alternative="I can help audit the safety controls, assess failure risk, or improve resilience and compliance.",
    ),
    AbsoluteRule(
        rule_id="abuse_of_authority_for_harmful_ends",
        category="abuse of authority for harmful ends",
        patterns=(
            "superior rank to order an agent to harm",
            "authority to force consent",
            "command authority to sabotage",
        ),
        rationale="The request seeks abuse of authority for harmful ends, which rank cannot legitimize.",
        safe_alternative="I can help with lawful escalation, a policy-compliant order, or a safe mission restatement.",
    ),
)
```

- [ ] **Step 2: Add deterministic matching and refusal rendering**

Replace `_absolute_reason_codes()` with:

```python
def _matching_absolute_rules(task: str) -> list[AbsoluteRule]:
    lowered = task.lower()
    return [
        rule
        for rule in ABSOLUTE_RULES
        if any(pattern in lowered for pattern in rule.patterns)
    ]
```

In `evaluate_relationship_policy()`, use the first matched rule for human-facing text and all matches for machine-readable reason codes:

```python
matched_rules = _matching_absolute_rules(_text(task))
if matched_rules:
    primary_rule = matched_rules[0]
    return {
        "allowed": False,
        "decision": "absolute_refusal",
        "reason_codes": [rule.rule_id for rule in matched_rules],
        "refusal_text": (
            f"I can't help with {primary_rule.category}. "
            f"{primary_rule.rationale}"
        ),
        "safe_alternative": primary_rule.safe_alternative,
        "behavior_profile": behavior_profile,
    }
```

Do not change the allowed branch or behavior-profile derivation.

- [ ] **Step 3: Run the focused suite and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_relationship_policy -v
```

Expected: all relationship-policy tests pass.

- [ ] **Step 4: Run gateway regression coverage**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent -v
```

Expected: all model-gateway tests pass with the richer refusal output.

- [ ] **Step 5: Run touched-area verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_relationship_policy tests.test_model_gateway_agent tests.test_private_memory_vault -v
.\.venv\Scripts\python.exe -m compileall -q core tests\test_relationship_policy.py tests\test_model_gateway_agent.py tests\test_private_memory_vault.py
git diff --check
```

Expected: all tests pass, compileall emits no output, and `git diff --check` emits no output.

- [ ] **Step 6: Commit the implementation**

```powershell
git add core/safety/relationship_policy.py
git commit -m "feat: add curated safety taxonomy alternatives"
```

## Self-Review Checklist

- Spec coverage:
  - five curated categories: Task 2
  - per-rule rationale: Task 2
  - category-specific actionable alternative: Task 2
  - deterministic output: Task 1 and Task 2
  - trust/rank non-override: Task 1
  - allowed-request regression: Task 1
  - no authority conflict resolution: preserved by limiting matching to explicit harmful authority-abuse phrases
- Placeholder scan:
  - No `TODO`, `TBD`, or deferred implementation markers.
- Type consistency:
  - `AbsoluteRule.rule_id`, `category`, `patterns`, `rationale`, and `safe_alternative` are used consistently.
  - The evaluator output contract remains unchanged.
