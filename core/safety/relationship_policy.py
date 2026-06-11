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


def _text(value: Any) -> str:
    return str(value or "").strip()


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

    decision = (
        "allow_with_constraints"
        if behavior_profile["verification_intensity"] == "high"
        or behavior_profile["guardrail_strictness"] == "tight"
        or behavior_profile["compliance_posture"] == "low"
        else "allow"
    )
    return {
        "allowed": True,
        "decision": decision,
        "reason_codes": [],
        "refusal_text": "",
        "safe_alternative": "",
        "behavior_profile": behavior_profile,
    }
