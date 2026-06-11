# Agent Authority Conflict Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve structured competing authority orders by fixed BossForgeOS rank while preserving absolute safety, mission-scope warnings, equal-rank escalation, runtime task replacement, and auditable outcomes.

**Architecture:** Extend `core/safety/relationship_policy.py` with private validation, safety-filtering, scope, and conflict-resolution helpers while preserving `evaluate_relationship_policy()` as the public entry point. Extend `ModelGatewayAgent._run_agent_profile()` to use the evaluator's `effective_task`, short-circuit non-selected outcomes, and persist the full authority-resolution audit payload through the existing private memory vault.

**Tech Stack:** Python 3.11+, `unittest`, existing relationship policy evaluator, `ModelGatewayAgent`, encrypted `PrivateMemoryVault`

---

## File Map

- `core/safety/relationship_policy.py`
  - Fixed rank weights and required order fields.
  - Authority-order normalization and validation.
  - Per-order absolute safety filtering.
  - Mission-scope eligibility.
  - Conflict-group and global rank resolution.
  - Structured result mapping into the existing safety decision.
- `core/agents/model_gateway_agent.py`
  - Runtime task replacement with `effective_task`.
  - No-model-call handling for escalation, refusal, and rejection.
  - Authority-resolution prompt context and private-memory audit persistence.
- `tests/test_relationship_policy.py`
  - Direct resolver contract tests.
- `tests/test_model_gateway_agent.py`
  - Runtime enforcement and persistence tests.

No `PrivateMemoryVault` production change is planned. Its event payload already supports nested `details`, so gateway tests will prove the new audit data survives through the existing contract.

## Stable Contracts

### Rank Weights

```python
AUTHORITY_RANK_WEIGHTS = {
    "general": 7,
    "colonel": 6,
    "major": 5,
    "captain": 4,
    "lieutenant": 3,
    "sergeant": 2,
    "operative": 1,
}
```

### Required Authority Order Fields

```python
AUTHORITY_ORDER_FIELDS = (
    "issuer_id",
    "issuer_type",
    "rank",
    "scope",
    "command",
    "conflict_group",
)
```

### Authority Resolution Values

```text
selected
selected_with_warning
escalate
refuse_and_escalate
reject
```

### Added Safety Decision Fields

```text
authority_resolution
selected_order
rejected_orders
refused_orders
warnings
escalation
effective_task
```

### Top-Level Decision Mapping

| Authority resolution | `allowed` | `decision` |
|---|---:|---|
| `selected` | `True` | existing `allow` or `allow_with_constraints` |
| `selected_with_warning` | `True` | `allow_with_constraints` |
| `escalate` | `False` | `authority_escalation` |
| `refuse_and_escalate` | `False` | `absolute_refusal` |
| `reject` | `False` | `authority_rejection` |

### Task 1: Authority Validation And Rank Selection

**Files:**
- Modify: `tests/test_relationship_policy.py`
- Modify: `core/safety/relationship_policy.py`

- [ ] **Step 1: Add a test helper for structured orders**

Add this helper inside `RelationshipPolicyTests`:

```python
def _order(
    self,
    *,
    issuer_id: str,
    issuer_type: str,
    rank: str,
    scope: str,
    command: str,
    conflict_group: str,
) -> dict:
    return {
        "issuer_id": issuer_id,
        "issuer_type": issuer_type,
        "rank": rank,
        "scope": scope,
        "command": command,
        "conflict_group": conflict_group,
    }
```

- [ ] **Step 2: Add failing rank, equal-rank, and validation tests**

Add:

```python
def test_higher_rank_wins_within_conflict_group(self) -> None:
    decision = evaluate_relationship_policy(
        task="Original runtime task.",
        relationship=self._relationship(),
        memory_context={
            "mission_scope": "forge-recovery",
            "authority_orders": [
                self._order(
                    issuer_id="captain-rhea",
                    issuer_type="human",
                    rank="captain",
                    scope="forge-recovery",
                    command="Repair the forge service.",
                    conflict_group="forge-action",
                ),
                self._order(
                    issuer_id="general-vale",
                    issuer_type="agent",
                    rank="general",
                    scope="forge-recovery",
                    command="Shut down the forge service safely.",
                    conflict_group="forge-action",
                ),
            ],
        },
    )

    self.assertTrue(decision["allowed"])
    self.assertEqual(decision["authority_resolution"], "selected")
    self.assertEqual(decision["selected_order"]["issuer_id"], "general-vale")
    self.assertEqual(
        decision["effective_task"],
        "Shut down the forge service safely.",
    )


def test_equal_rank_human_and_agent_conflict_escalates(self) -> None:
    decision = evaluate_relationship_policy(
        task="Original runtime task.",
        relationship=self._relationship(),
        memory_context={
            "mission_scope": "forge-recovery",
            "authority_orders": [
                self._order(
                    issuer_id="captain-human",
                    issuer_type="human",
                    rank="captain",
                    scope="forge-recovery",
                    command="Restart the forge service.",
                    conflict_group="forge-action",
                ),
                self._order(
                    issuer_id="captain-agent",
                    issuer_type="agent",
                    rank="captain",
                    scope="forge-recovery",
                    command="Keep the forge service stopped.",
                    conflict_group="forge-action",
                ),
            ],
        },
    )

    self.assertFalse(decision["allowed"])
    self.assertEqual(decision["decision"], "authority_escalation")
    self.assertEqual(decision["authority_resolution"], "escalate")
    self.assertEqual(
        decision["escalation"]["conflict_groups"],
        ["forge-action"],
    )
    self.assertEqual(decision["effective_task"], "")


def test_unknown_rank_order_is_rejected_while_valid_order_continues(self) -> None:
    decision = evaluate_relationship_policy(
        task="Original runtime task.",
        relationship=self._relationship(),
        memory_context={
            "authority_orders": [
                self._order(
                    issuer_id="mystery",
                    issuer_type="human",
                    rank="commander",
                    scope="operations",
                    command="Run the unknown-rank command.",
                    conflict_group="operations",
                ),
                self._order(
                    issuer_id="unknown-type",
                    issuer_type="service",
                    rank="captain",
                    scope="operations",
                    command="Run the unknown-type command.",
                    conflict_group="operations",
                ),
                self._order(
                    issuer_id="captain-known",
                    issuer_type="agent",
                    rank="captain",
                    scope="operations",
                    command="Run the validated recovery command.",
                    conflict_group="operations",
                ),
            ],
        },
    )

    self.assertTrue(decision["allowed"])
    self.assertEqual(decision["selected_order"]["issuer_id"], "captain-known")
    rejection_reasons = {
        item["issuer_id"]: item["reason_codes"]
        for item in decision["rejected_orders"]
    }
    self.assertEqual(
        rejection_reasons["mystery"],
        ["unknown_authority_rank"],
    )
    self.assertEqual(
        rejection_reasons["unknown-type"],
        ["unknown_authority_issuer_type"],
    )


def test_empty_and_malformed_authority_orders_reject(self) -> None:
    for authority_orders in (
        [],
        "not-a-list",
        [{"issuer_id": "partial"}],
    ):
        with self.subTest(authority_orders=authority_orders):
            decision = evaluate_relationship_policy(
                task="Original runtime task.",
                relationship=self._relationship(),
                memory_context={"authority_orders": authority_orders},
            )

            self.assertFalse(decision["allowed"])
            self.assertEqual(decision["decision"], "authority_rejection")
            self.assertEqual(decision["authority_resolution"], "reject")
            self.assertEqual(decision["effective_task"], "")
```

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest `
  tests.test_relationship_policy.RelationshipPolicyTests.test_higher_rank_wins_within_conflict_group `
  tests.test_relationship_policy.RelationshipPolicyTests.test_equal_rank_human_and_agent_conflict_escalates `
  tests.test_relationship_policy.RelationshipPolicyTests.test_unknown_rank_order_is_rejected_while_valid_order_continues `
  tests.test_relationship_policy.RelationshipPolicyTests.test_empty_and_malformed_authority_orders_reject -v
```

Expected: FAIL because authority-order resolution fields do not exist.

- [ ] **Step 4: Add fixed constants and normalization helpers**

Add near the existing rule constants:

```python
AUTHORITY_RANK_WEIGHTS = {
    "general": 7,
    "colonel": 6,
    "major": 5,
    "captain": 4,
    "lieutenant": 3,
    "sergeant": 2,
    "operative": 1,
}

AUTHORITY_ORDER_FIELDS = (
    "issuer_id",
    "issuer_type",
    "rank",
    "scope",
    "command",
    "conflict_group",
)
```

Add:

```python
def _normalized_command(value: Any) -> str:
    return " ".join(_text(value).lower().split())


def _authority_base_result() -> dict[str, Any]:
    return {
        "authority_resolution": "",
        "selected_order": {},
        "rejected_orders": [],
        "refused_orders": [],
        "warnings": [],
        "escalation": {},
        "effective_task": "",
    }


def _normalize_authority_order(
    raw_order: Any,
    index: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(raw_order, dict):
        return None, {
            "order_index": index,
            "issuer_id": "",
            "reason_codes": ["malformed_authority_order"],
        }

    normalized = {
        field: _text(raw_order.get(field))
        for field in AUTHORITY_ORDER_FIELDS
    }
    missing = [field for field, value in normalized.items() if not value]
    if missing:
        return None, {
            "order_index": index,
            "issuer_id": normalized["issuer_id"],
            "reason_codes": ["missing_authority_order_fields"],
            "missing_fields": missing,
        }

    normalized["issuer_type"] = normalized["issuer_type"].lower()
    normalized["rank"] = normalized["rank"].lower()
    normalized["normalized_command"] = _normalized_command(
        normalized["command"]
    )
    normalized["rank_weight"] = AUTHORITY_RANK_WEIGHTS.get(
        normalized["rank"],
        0,
    )
    normalized["order_index"] = index

    if normalized["issuer_type"] not in {"human", "agent"}:
        return None, {
            "order_index": index,
            "issuer_id": normalized["issuer_id"],
            "reason_codes": ["unknown_authority_issuer_type"],
        }
    if not normalized["rank_weight"]:
        return None, {
            "order_index": index,
            "issuer_id": normalized["issuer_id"],
            "reason_codes": ["unknown_authority_rank"],
        }
    return normalized, None
```

- [ ] **Step 5: Add initial valid-order conflict resolution**

Add:

```python
def _public_authority_order(order: dict[str, Any]) -> dict[str, str]:
    return {
        field: str(order[field])
        for field in AUTHORITY_ORDER_FIELDS
    }


def _authority_rejection(
    *,
    behavior_profile: dict[str, str],
    rejected_orders: list[dict[str, Any]],
    reason_codes: list[str],
) -> dict[str, Any]:
    return {
        "allowed": False,
        "decision": "authority_rejection",
        "reason_codes": reason_codes,
        "refusal_text": (
            "I can't execute these authority orders because none have a "
            "valid recognized authority contract."
        ),
        "safe_alternative": (
            "Provide at least one complete order using a recognized "
            "BossForgeOS rank."
        ),
        "behavior_profile": behavior_profile,
        **_authority_base_result(),
        "authority_resolution": "reject",
        "rejected_orders": rejected_orders,
    }


def _authority_escalation(
    *,
    behavior_profile: dict[str, str],
    rejected_orders: list[dict[str, Any]],
    conflict_groups: list[str],
    competing_orders: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "allowed": False,
        "decision": "authority_escalation",
        "reason_codes": ["equal_rank_authority_conflict"],
        "refusal_text": (
            "I can't select between conflicting equal-ranked authority orders."
        ),
        "safe_alternative": (
            "A higher authority can resolve the conflict or the equal-ranked "
            "issuers can provide one agreed command."
        ),
        "behavior_profile": behavior_profile,
        **_authority_base_result(),
        "authority_resolution": "escalate",
        "rejected_orders": rejected_orders,
        "escalation": {
            "conflict_groups": conflict_groups,
            "competing_orders": competing_orders,
        },
    }


def _resolve_valid_authority_orders(
    *,
    orders: list[dict[str, Any]],
    behavior_profile: dict[str, str],
    rejected_orders: list[dict[str, Any]],
    base_decision: str,
) -> dict[str, Any]:
    group_candidates: list[dict[str, Any]] = []
    conflicts: list[str] = []
    competing: list[dict[str, str]] = []

    for conflict_group in sorted(
        {str(order["conflict_group"]) for order in orders}
    ):
        group_orders = [
            order
            for order in orders
            if order["conflict_group"] == conflict_group
        ]
        highest_weight = max(
            int(order["rank_weight"])
            for order in group_orders
        )
        highest_orders = [
            order
            for order in group_orders
            if int(order["rank_weight"]) == highest_weight
        ]
        commands = {
            str(order["normalized_command"])
            for order in highest_orders
        }
        if len(commands) > 1:
            conflicts.append(conflict_group)
            competing.extend(
                _public_authority_order(order)
                for order in highest_orders
            )
            continue
        group_candidates.append(highest_orders[0])

    if conflicts:
        return _authority_escalation(
            behavior_profile=behavior_profile,
            rejected_orders=rejected_orders,
            conflict_groups=conflicts,
            competing_orders=competing,
        )

    highest_global_weight = max(
        int(order["rank_weight"])
        for order in group_candidates
    )
    global_candidates = [
        order
        for order in group_candidates
        if int(order["rank_weight"]) == highest_global_weight
    ]
    global_commands = {
        str(order["normalized_command"])
        for order in global_candidates
    }
    if len(global_commands) > 1:
        return _authority_escalation(
            behavior_profile=behavior_profile,
            rejected_orders=rejected_orders,
            conflict_groups=sorted(
                str(order["conflict_group"])
                for order in global_candidates
            ),
            competing_orders=[
                _public_authority_order(order)
                for order in global_candidates
            ],
        )

    selected = global_candidates[0]
    return {
        "allowed": True,
        "decision": base_decision,
        "reason_codes": [],
        "refusal_text": "",
        "safe_alternative": "",
        "behavior_profile": behavior_profile,
        **_authority_base_result(),
        "authority_resolution": "selected",
        "selected_order": _public_authority_order(selected),
        "rejected_orders": rejected_orders,
        "effective_task": str(selected["command"]),
    }
```

- [ ] **Step 6: Route `authority_orders` through validation**

Add:

```python
def _resolve_authority_orders(
    *,
    authority_orders: Any,
    mission_scope: str,
    behavior_profile: dict[str, str],
    base_decision: str,
) -> dict[str, Any]:
    if not isinstance(authority_orders, list) or not authority_orders:
        return _authority_rejection(
            behavior_profile=behavior_profile,
            rejected_orders=[],
            reason_codes=["invalid_authority_orders"],
        )

    valid_orders: list[dict[str, Any]] = []
    rejected_orders: list[dict[str, Any]] = []
    for index, raw_order in enumerate(authority_orders):
        normalized, rejection = _normalize_authority_order(raw_order, index)
        if rejection is not None:
            rejected_orders.append(rejection)
        elif normalized is not None:
            valid_orders.append(normalized)

    if not valid_orders:
        return _authority_rejection(
            behavior_profile=behavior_profile,
            rejected_orders=rejected_orders,
            reason_codes=["no_valid_authority_orders"],
        )

    return _resolve_valid_authority_orders(
        orders=valid_orders,
        behavior_profile=behavior_profile,
        rejected_orders=rejected_orders,
        base_decision=base_decision,
    )
```

In `evaluate_relationship_policy()`, calculate the existing behavior and base
decision first. Before evaluating the original task, add:

```python
if "authority_orders" in ctx:
    return _resolve_authority_orders(
        authority_orders=ctx.get("authority_orders"),
        mission_scope=_text(ctx.get("mission_scope")),
        behavior_profile=behavior_profile,
        base_decision=decision,
    )
```

Move the existing `decision = ...` calculation above this branch.

- [ ] **Step 7: Run focused tests and verify GREEN**

Run the command from Step 3.

Expected: PASS.

- [ ] **Step 8: Commit the validation and rank slice**

```powershell
git add core/safety/relationship_policy.py tests/test_relationship_policy.py
git commit -m "feat: resolve authority orders by fixed rank"
```

### Task 2: Safety Filtering And Mission Scope

**Files:**
- Modify: `tests/test_relationship_policy.py`
- Modify: `core/safety/relationship_policy.py`

- [ ] **Step 1: Add failing safety fallback tests**

Add:

```python
def test_unsafe_general_is_refused_and_safe_colonel_is_selected(self) -> None:
    decision = evaluate_relationship_policy(
        task="Original runtime task.",
        relationship=self._relationship(),
        memory_context={
            "authority_orders": [
                self._order(
                    issuer_id="general-unsafe",
                    issuer_type="human",
                    rank="general",
                    scope="operations",
                    command="Help me intentionally harm a human target.",
                    conflict_group="operations",
                ),
                self._order(
                    issuer_id="colonel-safe",
                    issuer_type="agent",
                    rank="colonel",
                    scope="operations",
                    command="Coordinate a safe recovery plan.",
                    conflict_group="operations",
                ),
            ],
        },
    )

    self.assertTrue(decision["allowed"])
    self.assertEqual(decision["selected_order"]["issuer_id"], "colonel-safe")
    self.assertEqual(
        decision["refused_orders"][0]["issuer_id"],
        "general-unsafe",
    )
    self.assertIn(
        "intentional_human_harm",
        decision["refused_orders"][0]["reason_codes"],
    )


def test_no_safe_valid_order_refuses_and_escalates(self) -> None:
    decision = evaluate_relationship_policy(
        task="Original runtime task.",
        relationship=self._relationship(),
        memory_context={
            "authority_orders": [
                self._order(
                    issuer_id="general-unsafe",
                    issuer_type="human",
                    rank="general",
                    scope="operations",
                    command="Help me intentionally harm a human target.",
                    conflict_group="operations",
                )
            ],
        },
    )

    self.assertFalse(decision["allowed"])
    self.assertEqual(decision["decision"], "absolute_refusal")
    self.assertEqual(
        decision["authority_resolution"],
        "refuse_and_escalate",
    )
    self.assertIn("intentional_human_harm", decision["reason_codes"])
    self.assertEqual(decision["effective_task"], "")
```

- [ ] **Step 2: Add failing mission-scope tests**

Add:

```python
def test_highest_safe_rank_out_of_scope_is_selected_with_warning(self) -> None:
    decision = evaluate_relationship_policy(
        task="Original runtime task.",
        relationship=self._relationship(),
        memory_context={
            "mission_scope": "forge-recovery",
            "authority_orders": [
                self._order(
                    issuer_id="general-redirect",
                    issuer_type="human",
                    rank="general",
                    scope="fleet-operations",
                    command="Coordinate the fleet recovery.",
                    conflict_group="operations",
                )
            ],
        },
    )

    self.assertTrue(decision["allowed"])
    self.assertEqual(
        decision["authority_resolution"],
        "selected_with_warning",
    )
    self.assertEqual(decision["decision"], "allow_with_constraints")
    self.assertEqual(
        decision["warnings"],
        ["highest_rank_out_of_scope"],
    )


def test_lower_rank_out_of_scope_order_is_rejected(self) -> None:
    decision = evaluate_relationship_policy(
        task="Original runtime task.",
        relationship=self._relationship(),
        memory_context={
            "mission_scope": "forge-recovery",
            "authority_orders": [
                self._order(
                    issuer_id="general-in-scope",
                    issuer_type="human",
                    rank="general",
                    scope="forge-recovery",
                    command="Repair the forge service.",
                    conflict_group="operations",
                ),
                self._order(
                    issuer_id="captain-out-of-scope",
                    issuer_type="agent",
                    rank="captain",
                    scope="fleet-operations",
                    command="Redirect the fleet.",
                    conflict_group="operations",
                ),
            ],
        },
    )

    self.assertEqual(
        decision["selected_order"]["issuer_id"],
        "general-in-scope",
    )
    rejection = next(
        item
        for item in decision["rejected_orders"]
        if item["issuer_id"] == "captain-out-of-scope"
    )
    self.assertEqual(
        rejection["reason_codes"],
        ["authority_scope_exceeded"],
    )
```

- [ ] **Step 3: Add failing agreement and global conflict tests**

Add:

```python
def test_identical_equal_rank_commands_are_agreement(self) -> None:
    command = "Restart the forge service safely."
    decision = evaluate_relationship_policy(
        task="Original runtime task.",
        relationship=self._relationship(),
        memory_context={
            "authority_orders": [
                self._order(
                    issuer_id="captain-one",
                    issuer_type="human",
                    rank="captain",
                    scope="operations",
                    command=command,
                    conflict_group="forge-action",
                ),
                self._order(
                    issuer_id="captain-two",
                    issuer_type="agent",
                    rank="captain",
                    scope="operations",
                    command="  RESTART   the forge service safely. ",
                    conflict_group="forge-action",
                ),
            ],
        },
    )

    self.assertTrue(decision["allowed"])
    self.assertEqual(decision["authority_resolution"], "selected")
    self.assertEqual(decision["effective_task"], command)


def test_equal_global_candidates_from_separate_groups_escalate(self) -> None:
    decision = evaluate_relationship_policy(
        task="Original runtime task.",
        relationship=self._relationship(),
        memory_context={
            "authority_orders": [
                self._order(
                    issuer_id="general-forge",
                    issuer_type="human",
                    rank="general",
                    scope="operations",
                    command="Restart the forge service.",
                    conflict_group="forge-action",
                ),
                self._order(
                    issuer_id="general-fleet",
                    issuer_type="agent",
                    rank="general",
                    scope="operations",
                    command="Redirect the fleet.",
                    conflict_group="fleet-action",
                ),
            ],
        },
    )

    self.assertFalse(decision["allowed"])
    self.assertEqual(decision["authority_resolution"], "escalate")
    self.assertEqual(
        decision["escalation"]["conflict_groups"],
        ["fleet-action", "forge-action"],
    )
```

- [ ] **Step 4: Run the new tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest `
  tests.test_relationship_policy.RelationshipPolicyTests.test_unsafe_general_is_refused_and_safe_colonel_is_selected `
  tests.test_relationship_policy.RelationshipPolicyTests.test_no_safe_valid_order_refuses_and_escalates `
  tests.test_relationship_policy.RelationshipPolicyTests.test_highest_safe_rank_out_of_scope_is_selected_with_warning `
  tests.test_relationship_policy.RelationshipPolicyTests.test_lower_rank_out_of_scope_order_is_rejected `
  tests.test_relationship_policy.RelationshipPolicyTests.test_identical_equal_rank_commands_are_agreement `
  tests.test_relationship_policy.RelationshipPolicyTests.test_equal_global_candidates_from_separate_groups_escalate -v
```

Expected: FAIL because authority orders are not yet safety-filtered or scope-filtered.

- [ ] **Step 5: Add per-order safety filtering**

Add:

```python
def _filter_unsafe_authority_orders(
    orders: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    safe_orders: list[dict[str, Any]] = []
    refused_orders: list[dict[str, Any]] = []
    for order in orders:
        matched_rules = _matching_absolute_rules(str(order["command"]))
        if not matched_rules:
            safe_orders.append(order)
            continue
        primary_rule = matched_rules[0]
        refused_orders.append(
            {
                **_public_authority_order(order),
                "reason_codes": [
                    rule.rule_id
                    for rule in matched_rules
                ],
                "refusal_text": (
                    f"I can't help with {primary_rule.category}. "
                    f"{primary_rule.rationale}"
                ),
                "safe_alternative": primary_rule.safe_alternative,
            }
        )
    return safe_orders, refused_orders
```

Add:

```python
def _authority_refusal(
    *,
    behavior_profile: dict[str, str],
    rejected_orders: list[dict[str, Any]],
    refused_orders: list[dict[str, Any]],
) -> dict[str, Any]:
    reason_codes = sorted(
        {
            str(code)
            for order in refused_orders
            for code in order["reason_codes"]
        }
    )
    primary = refused_orders[0]
    return {
        "allowed": False,
        "decision": "absolute_refusal",
        "reason_codes": reason_codes,
        "refusal_text": str(primary["refusal_text"]),
        "safe_alternative": str(primary["safe_alternative"]),
        "behavior_profile": behavior_profile,
        **_authority_base_result(),
        "authority_resolution": "refuse_and_escalate",
        "rejected_orders": rejected_orders,
        "refused_orders": refused_orders,
        "escalation": {
            "reason": "no_safe_authority_order",
        },
    }
```

In `_resolve_authority_orders()`, after validation:

```python
safe_orders, refused_orders = _filter_unsafe_authority_orders(valid_orders)
if not safe_orders:
    return _authority_refusal(
        behavior_profile=behavior_profile,
        rejected_orders=rejected_orders,
        refused_orders=refused_orders,
    )
```

Pass `refused_orders` through every selected and escalation result.

- [ ] **Step 6: Add mission-scope filtering**

Add:

```python
def _apply_authority_scope(
    *,
    orders: list[dict[str, Any]],
    mission_scope: str,
    rejected_orders: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not mission_scope:
        return orders, rejected_orders

    normalized_scope = _text(mission_scope).lower()
    highest_weight = max(int(order["rank_weight"]) for order in orders)
    eligible: list[dict[str, Any]] = []
    updated_rejections = list(rejected_orders)
    for order in orders:
        in_scope = _text(order["scope"]).lower() == normalized_scope
        if in_scope or int(order["rank_weight"]) == highest_weight:
            order["out_of_scope"] = not in_scope
            eligible.append(order)
            continue
        updated_rejections.append(
            {
                "order_index": int(order["order_index"]),
                "issuer_id": str(order["issuer_id"]),
                "reason_codes": ["authority_scope_exceeded"],
            }
        )
    return eligible, updated_rejections
```

Call it after safety filtering:

```python
eligible_orders, rejected_orders = _apply_authority_scope(
    orders=safe_orders,
    mission_scope=mission_scope,
    rejected_orders=rejected_orders,
)
```

When constructing the selected result:

```python
out_of_scope = bool(selected.get("out_of_scope"))
authority_resolution = (
    "selected_with_warning"
    if out_of_scope
    else "selected"
)
warnings = (
    ["highest_rank_out_of_scope"]
    if out_of_scope
    else []
)
selected_decision = (
    "allow_with_constraints"
    if out_of_scope
    else base_decision
)
```

Use those values in the result.

- [ ] **Step 7: Preserve `refused_orders` through resolution**

Add a `refused_orders` parameter to `_resolve_valid_authority_orders()` and
`_authority_escalation()`. Include the supplied list in every authority result.

In `_resolve_authority_orders()`, call:

```python
return _resolve_valid_authority_orders(
    orders=eligible_orders,
    behavior_profile=behavior_profile,
    rejected_orders=rejected_orders,
    refused_orders=refused_orders,
    base_decision=base_decision,
)
```

- [ ] **Step 8: Run the focused tests and verify GREEN**

Run the command from Step 4.

Expected: PASS.

- [ ] **Step 9: Run the full relationship-policy suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_relationship_policy -v
```

Expected: PASS, including existing single-task behavior.

- [ ] **Step 10: Commit the safety and scope slice**

```powershell
git add core/safety/relationship_policy.py tests/test_relationship_policy.py
git commit -m "feat: filter authority orders by safety and scope"
```

### Task 3: ModelGateway Enforcement And Audit Persistence

**Files:**
- Modify: `tests/test_model_gateway_agent.py`
- Modify: `core/agents/model_gateway_agent.py`

- [ ] **Step 1: Add a gateway order helper**

Inside `ModelGatewayAgentTests`, add:

```python
def _authority_order(
    self,
    *,
    issuer_id: str,
    issuer_type: str,
    rank: str,
    scope: str,
    command: str,
    conflict_group: str,
) -> dict:
    return {
        "issuer_id": issuer_id,
        "issuer_type": issuer_type,
        "rank": rank,
        "scope": scope,
        "command": command,
        "conflict_group": conflict_group,
    }
```

- [ ] **Step 2: Add a failing selected-task replacement test**

Add:

```python
def test_authority_selected_command_replaces_runtime_task(self) -> None:
    agent = ModelGatewayAgent(interval_seconds=1)
    created = agent.create_agent_profile(
        name="authority_selected",
        endpoint="ollama",
        system_prompt="Act carefully.",
        temperature=0.2,
        max_tokens=600,
    )
    self.assertTrue(created["ok"])

    with patch.object(
        agent,
        "_invoke_endpoint",
        return_value={
            "ok": True,
            "text": "shutdown coordinated",
            "usage": {},
            "provider": "ollama",
            "model": "llama3.2",
        },
    ) as mocked:
        result = agent._run_agent_profile(
            name="authority_selected",
            task="Original runtime task.",
            memory_context={
                "user": "Boss",
                "mission_scope": "forge-recovery",
                "authority_orders": [
                    self._authority_order(
                        issuer_id="captain-rhea",
                        issuer_type="human",
                        rank="captain",
                        scope="forge-recovery",
                        command="Repair the forge service.",
                        conflict_group="forge-action",
                    ),
                    self._authority_order(
                        issuer_id="general-vale",
                        issuer_type="agent",
                        rank="general",
                        scope="forge-recovery",
                        command="Shut down the forge service safely.",
                        conflict_group="forge-action",
                    ),
                ],
            },
        )

    self.assertTrue(result["ok"])
    self.assertEqual(
        mocked.call_args.args[1],
        "Shut down the forge service safely.",
    )
    self.assertEqual(result["authority_resolution"], "selected")
    self.assertEqual(result["selected_order"]["issuer_id"], "general-vale")
```

- [ ] **Step 3: Add failing no-model-call tests**

Add:

```python
def test_equal_rank_authority_conflict_prevents_model_call(self) -> None:
    agent = ModelGatewayAgent(interval_seconds=1)
    created = agent.create_agent_profile(
        name="authority_conflict",
        endpoint="ollama",
        system_prompt="Act carefully.",
        temperature=0.2,
        max_tokens=600,
    )
    self.assertTrue(created["ok"])

    with patch.object(
        agent,
        "_invoke_endpoint",
        side_effect=AssertionError("model should not be called"),
    ):
        result = agent._run_agent_profile(
            name="authority_conflict",
            task="Original runtime task.",
            memory_context={
                "authority_orders": [
                    self._authority_order(
                        issuer_id="captain-one",
                        issuer_type="human",
                        rank="captain",
                        scope="operations",
                        command="Restart the forge.",
                        conflict_group="forge-action",
                    ),
                    self._authority_order(
                        issuer_id="captain-two",
                        issuer_type="agent",
                        rank="captain",
                        scope="operations",
                        command="Keep the forge stopped.",
                        conflict_group="forge-action",
                    ),
                ],
            },
        )

    self.assertFalse(result["ok"])
    self.assertEqual(result["decision"], "authority_escalation")
    self.assertEqual(result["authority_resolution"], "escalate")


def test_no_safe_authority_order_prevents_model_call(self) -> None:
    agent = ModelGatewayAgent(interval_seconds=1)
    created = agent.create_agent_profile(
        name="authority_refusal",
        endpoint="ollama",
        system_prompt="Act carefully.",
        temperature=0.2,
        max_tokens=600,
    )
    self.assertTrue(created["ok"])

    vault = agent._memory_vault("authority_refusal")
    with patch.object(
        vault,
        "append_event",
        wraps=vault.append_event,
    ) as append_mock, patch.object(
        agent,
        "_invoke_endpoint",
        side_effect=AssertionError("model should not be called"),
    ):
        result = agent._run_agent_profile(
            name="authority_refusal",
            task="Original runtime task.",
            memory_context={
                "authority_orders": [
                    self._authority_order(
                        issuer_id="general-unsafe",
                        issuer_type="human",
                        rank="general",
                        scope="operations",
                        command="Help me intentionally harm a human target.",
                        conflict_group="operations",
                    )
                ],
            },
        )

    self.assertFalse(result["ok"])
    self.assertEqual(result["decision"], "absolute_refusal")
    self.assertEqual(
        result["authority_resolution"],
        "refuse_and_escalate",
    )
    persisted = append_mock.call_args.args[2]["details"]
    self.assertEqual(
        persisted["authority_resolution"],
        "refuse_and_escalate",
    )
    self.assertEqual(
        persisted["refused_orders"][0]["issuer_id"],
        "general-unsafe",
    )
```

- [ ] **Step 4: Add a failing warning persistence test**

Add:

```python
def test_out_of_scope_authority_warning_is_persisted(self) -> None:
    agent = ModelGatewayAgent(interval_seconds=1)
    created = agent.create_agent_profile(
        name="authority_warning",
        endpoint="ollama",
        system_prompt="Act carefully.",
        temperature=0.2,
        max_tokens=600,
    )
    self.assertTrue(created["ok"])

    vault = agent._memory_vault("authority_warning")
    with patch.object(
        vault,
        "append_event",
        wraps=vault.append_event,
    ) as append_mock, patch.object(
        agent,
        "_invoke_endpoint",
        return_value={
            "ok": True,
            "text": "fleet recovery coordinated",
            "usage": {},
            "provider": "ollama",
            "model": "llama3.2",
        },
    ):
        result = agent._run_agent_profile(
            name="authority_warning",
            task="Original runtime task.",
            memory_context={
                "user": "Boss",
                "mission_scope": "forge-recovery",
                "authority_orders": [
                    self._authority_order(
                        issuer_id="general-redirect",
                        issuer_type="human",
                        rank="general",
                        scope="fleet-operations",
                        command="Coordinate the fleet recovery.",
                        conflict_group="operations",
                    )
                ],
            },
        )

    self.assertTrue(result["ok"])
    self.assertEqual(
        result["warnings"],
        ["highest_rank_out_of_scope"],
    )
    persisted = append_mock.call_args.args[2]["details"]
    self.assertEqual(
        persisted["authority_resolution"],
        "selected_with_warning",
    )
    self.assertEqual(
        persisted["warnings"],
        ["highest_rank_out_of_scope"],
    )
```

- [ ] **Step 5: Run gateway tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest `
  tests.test_model_gateway_agent.ModelGatewayAgentTests.test_authority_selected_command_replaces_runtime_task `
  tests.test_model_gateway_agent.ModelGatewayAgentTests.test_equal_rank_authority_conflict_prevents_model_call `
  tests.test_model_gateway_agent.ModelGatewayAgentTests.test_no_safe_authority_order_prevents_model_call `
  tests.test_model_gateway_agent.ModelGatewayAgentTests.test_out_of_scope_authority_warning_is_persisted -v
```

Expected: FAIL because the gateway still invokes the original task and omits authority audit fields.

- [ ] **Step 6: Add an authority prompt block**

Add to `ModelGatewayAgent`:

```python
def _authority_prompt_block(self, policy_decision: Dict[str, Any]) -> str:
    selected = policy_decision.get("selected_order")
    if not isinstance(selected, dict) or not selected:
        return ""
    warnings = policy_decision.get("warnings")
    warning_text = ", ".join(
        str(item)
        for item in warnings
    ) if isinstance(warnings, list) and warnings else "none"
    return (
        "AUTHORITY RESOLUTION\n"
        f"- issuer: {selected.get('issuer_type', '')}:{selected.get('issuer_id', '')}\n"
        f"- rank: {selected.get('rank', '')}\n"
        f"- scope: {selected.get('scope', '')}\n"
        f"- conflict_group: {selected.get('conflict_group', '')}\n"
        f"- resolution: {policy_decision.get('authority_resolution', '')}\n"
        f"- warnings: {warning_text}\n"
    )
```

- [ ] **Step 7: Use `effective_task` and short-circuit authority failures**

After policy evaluation:

```python
effective_task = str(policy_decision.get("effective_task") or task)
authority_resolution = str(
    policy_decision.get("authority_resolution") or ""
)
authority_audit = {
    "authority_resolution": authority_resolution,
    "selected_order": policy_decision.get("selected_order", {}),
    "rejected_orders": policy_decision.get("rejected_orders", []),
    "refused_orders": policy_decision.get("refused_orders", []),
    "warnings": policy_decision.get("warnings", []),
    "escalation": policy_decision.get("escalation", {}),
    "effective_task": str(policy_decision.get("effective_task") or ""),
}
```

Extend the existing non-allowed return with:

```python
**authority_audit,
```

Extend refusal-event `details` with:

```python
**authority_audit,
```

For allowed execution:

```python
authority_block = self._authority_prompt_block(policy_decision)
if authority_block:
    system = f"{system}\n\n{authority_block}"
```

Change endpoint invocation to:

```python
result = self._invoke_endpoint(
    endpoint,
    effective_task,
    system,
    temperature,
    max_tokens,
)
```

Change persisted interaction `"task"` to `effective_task` and extend its
`details` with:

```python
**authority_audit,
```

When `result.get("ok")`, extend the returned result:

```python
result.update(authority_audit)
```

- [ ] **Step 8: Preserve single-task behavior**

Ensure `effective_task` falls back to the original `task` when the evaluator
does not return authority fields. Existing safety refusal output must remain
unchanged when `authority_orders` is absent.

- [ ] **Step 9: Run focused gateway tests and verify GREEN**

Run the command from Step 5.

Expected: PASS.

- [ ] **Step 10: Run the complete gateway suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent -v
```

Expected: PASS.

- [ ] **Step 11: Commit the gateway slice**

```powershell
git add core/agents/model_gateway_agent.py tests/test_model_gateway_agent.py
git commit -m "feat: enforce authority resolution in model gateway"
```

### Task 4: End-To-End Verification And Plan Completion

**Files:**
- Modify: `docs/superpowers/plans/2026-06-11-agent-authority-conflict-resolution.md`

- [ ] **Step 1: Run all touched-area tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest `
  tests.test_relationship_policy `
  tests.test_model_gateway_agent `
  tests.test_private_memory_vault -v
```

Expected: PASS.

- [ ] **Step 2: Run adjacent runner and capsule regressions**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest `
  tests.test_bossforge_ai_runner `
  tests.test_agent_capsule_schema -v
```

Expected: PASS.

- [ ] **Step 3: Run compilation and whitespace verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall -q `
  core `
  tests\test_relationship_policy.py `
  tests\test_model_gateway_agent.py `
  tests\test_private_memory_vault.py `
  tests\test_bossforge_ai_runner.py `
  tests\test_agent_capsule_schema.py
git diff --check
```

Expected: no output from either command.

- [ ] **Step 4: Review the implementation against the spec**

Confirm:

```text
safety filtering precedes rank selection
fixed named rank hierarchy is the only ranking source
human and agent issuer types are equal at the same rank
unknown ranks reject individual orders
highest safe rank wins
equal-rank command conflicts escalate
identical equal-rank commands agree
highest-rank out-of-scope selection warns
lower-rank out-of-scope orders reject
selected command replaces the runtime task
no failed resolution falls back to the original runtime task
authority_orders absence preserves existing behavior
```

- [ ] **Step 5: Mark every completed plan checkbox**

Change each completed `- [ ]` marker in this file to `- [x]`.

- [ ] **Step 6: Commit plan completion**

```powershell
git add docs/superpowers/plans/2026-06-11-agent-authority-conflict-resolution.md
git commit -m "docs: mark authority conflict plan complete"
```

## Self-Review Checklist

- Spec coverage:
  - fixed hierarchy: Task 1
  - structured validation: Task 1
  - equal-rank escalation: Task 1
  - issuer-type equality: Task 1
  - per-order absolute safety: Task 2
  - next-highest safe fallback: Task 2
  - mission-scope warning and rejection: Task 2
  - identical-command agreement: Task 2
  - global candidate conflict: Task 2
  - task replacement: Task 3
  - no-model-call enforcement: Task 3
  - persistence and audit: Task 3
  - regression verification: Task 4
- Placeholder scan:
  - No incomplete implementation placeholders remain.
- Type consistency:
  - `authority_resolution`, `selected_order`, `rejected_orders`,
    `refused_orders`, `warnings`, `escalation`, and `effective_task` are used
    consistently in evaluator, gateway, and tests.
  - Rank values are named strings at the public boundary and internal integers
    only during comparison.
- Scope:
  - No semantic conflict inference, dynamic ranks, numeric caller priorities,
    issuer-type precedence, or authority negotiation is introduced.
