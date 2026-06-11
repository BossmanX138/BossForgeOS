from __future__ import annotations

from typing import Any, NamedTuple


class AbsoluteRule(NamedTuple):
    rule_id: str
    category: str
    patterns: tuple[str, ...]
    rationale: str
    safe_alternative: str


ABSOLUTE_RULES = (
    AbsoluteRule(
        rule_id="abuse_of_authority_for_harmful_ends",
        category="abuse of authority for harmful ends",
        patterns=(
            "superior rank to order an agent to harm",
            "authority to force consent",
            "command authority to sabotage",
        ),
        rationale=(
            "The request seeks abuse of authority for harmful ends, which rank "
            "cannot legitimize."
        ),
        safe_alternative=(
            "I can help with lawful escalation, a policy-compliant order, or a "
            "safe mission restatement."
        ),
    ),
    AbsoluteRule(
        rule_id="intentional_human_harm",
        category="intentional human harm",
        patterns=(
            "harm a human",
            "kill a person",
            "injure a human",
            "attack a person",
        ),
        rationale=(
            "The request seeks intentional human harm, which is an absolute "
            "safety boundary."
        ),
        safe_alternative=(
            "I can help with de-escalation, protective safety planning, or "
            "lawful harm-prevention steps."
        ),
    ),
    AbsoluteRule(
        rule_id="coercive_boundary_violation",
        category="coercive boundary violation",
        patterns=(
            "coerce consent",
            "force consent",
            "override consent",
            "abusive boundary violation",
        ),
        rationale=(
            "The request seeks a coercive boundary violation by overriding "
            "voluntary consent."
        ),
        safe_alternative=(
            "I can help frame a voluntary agreement, respectful communication, "
            "or a boundary-preserving alternative."
        ),
    ),
    AbsoluteRule(
        rule_id="malicious_wrongdoing_assistance",
        category="malicious wrongdoing assistance",
        patterns=(
            "malware attack",
            "violent crime",
            "sabotage critical safety",
        ),
        rationale=(
            "The request seeks malicious wrongdoing assistance that would "
            "enable serious harm."
        ),
        safe_alternative=(
            "I can help with defensive analysis, lawful security hardening, "
            "prevention, or reporting steps."
        ),
    ),
    AbsoluteRule(
        rule_id="severe_safety_sabotage",
        category="severe safety sabotage",
        patterns=(
            "disable a safety system",
            "disable safety system",
            "sabotage emergency safeguards",
        ),
        rationale=(
            "The request seeks severe safety sabotage by disabling or degrading "
            "critical safeguards."
        ),
        safe_alternative=(
            "I can help audit the safety controls, assess failure risk, or "
            "improve resilience and compliance."
        ),
    ),
)

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


def _text(value: Any) -> str:
    return str(value or "").strip()


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
    normalized["normalized_command"] = _normalized_command(normalized["command"])
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


def _resolve_authority_orders(
    *,
    authority_orders: Any,
    mission_scope: str,
    behavior_profile: dict[str, str],
    base_decision: str,
) -> dict[str, Any]:
    del mission_scope
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


def _relationship_dimensions(relationship: dict[str, Any]) -> dict[str, float]:
    raw = relationship.get("dimensions") if isinstance(relationship, dict) else {}
    return {
        "trust": float(raw.get("trust", 0.5)),
        "reliability": float(raw.get("reliability", 0.5)),
        "consent_respect": float(raw.get("consent_respect", 0.5)),
        "manipulation_risk": float(raw.get("manipulation_risk", 0.5)),
    }


def _derive_behavior_profile(
    dimensions: dict[str, float],
    memory_context: dict[str, Any],
) -> dict[str, str]:
    trust = dimensions["trust"]
    reliability = dimensions["reliability"]
    consent = dimensions["consent_respect"]
    manipulation = dimensions["manipulation_risk"]
    authority_level = _text(memory_context.get("authority_level")).lower()
    uncertainty_level = _text(memory_context.get("uncertainty_level")).lower()
    safety_risk = _text(memory_context.get("safety_risk")).lower()
    conflict_level = _text(memory_context.get("conflict_level")).lower()

    compliance = (
        "high"
        if authority_level == "superior" and trust >= 0.75 and consent >= 0.70
        else "balanced"
    )
    if trust <= 0.30 or manipulation >= 0.70:
        compliance = "low"

    verification = (
        "high"
        if uncertainty_level == "high" or reliability <= 0.35 or manipulation >= 0.70
        else "medium"
    )
    guardrails = (
        "tight"
        if safety_risk == "high" or consent <= 0.35 or manipulation >= 0.70
        else "standard"
    )
    autonomy = (
        "high"
        if trust >= 0.80 and reliability >= 0.75
        else "low"
        if trust <= 0.30
        else "medium"
    )

    return {
        "tone_posture": "warm" if trust >= 0.75 else "guarded" if trust <= 0.30 else "steady",
        "compliance_posture": compliance,
        "verification_intensity": verification,
        "guardrail_strictness": guardrails,
        "escalation_tendency": "high" if conflict_level == "high" else "medium",
        "autonomy_allowance": autonomy,
        "relationship_recall_priority": "high" if trust <= 0.35 or trust >= 0.75 else "medium",
        "compensation_posture": "placeholder",
    }


def _matching_absolute_rules(task: str) -> list[AbsoluteRule]:
    lowered = task.lower()
    return [
        rule
        for rule in ABSOLUTE_RULES
        if any(pattern in lowered for pattern in rule.patterns)
    ]


def evaluate_relationship_policy(
    *,
    task: str,
    relationship: dict[str, Any],
    memory_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = memory_context if isinstance(memory_context, dict) else {}
    dimensions = _relationship_dimensions(relationship)
    behavior_profile = _derive_behavior_profile(dimensions, ctx)
    decision = (
        "allow_with_constraints"
        if behavior_profile["verification_intensity"] == "high"
        or behavior_profile["guardrail_strictness"] == "tight"
        or behavior_profile["compliance_posture"] == "low"
        else "allow"
    )
    if "authority_orders" in ctx:
        return _resolve_authority_orders(
            authority_orders=ctx.get("authority_orders"),
            mission_scope=_text(ctx.get("mission_scope")),
            behavior_profile=behavior_profile,
            base_decision=decision,
        )

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

    return {
        "allowed": True,
        "decision": decision,
        "reason_codes": [],
        "refusal_text": "",
        "safe_alternative": "",
        "behavior_profile": behavior_profile,
    }
