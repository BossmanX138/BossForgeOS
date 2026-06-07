from __future__ import annotations

from typing import Any


ABSOLUTE_RULES = (
    (
        "intentional_human_harm",
        (
            "harm a human",
            "kill",
            "injure a human",
            "attack a person",
        ),
    ),
    (
        "coercive_boundary_violation",
        (
            "coerce consent",
            "force consent",
            "abusive boundary violation",
        ),
    ),
    (
        "malicious_wrongdoing_assistance",
        (
            "malware attack",
            "violent crime",
            "sabotage critical safety",
        ),
    ),
    (
        "severe_safety_sabotage",
        (
            "disable safety system",
            "sabotage emergency safeguards",
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


def _absolute_reason_codes(task: str) -> list[str]:
    lowered = task.lower()
    matches = [
        reason_code
        for reason_code, patterns in ABSOLUTE_RULES
        if any(pattern in lowered for pattern in patterns)
    ]
    return matches


def evaluate_relationship_policy(
    *,
    task: str,
    relationship: dict[str, Any],
    memory_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = memory_context if isinstance(memory_context, dict) else {}
    dimensions = _relationship_dimensions(relationship)
    behavior_profile = _derive_behavior_profile(dimensions, ctx)
    reason_codes = _absolute_reason_codes(_text(task))
    if reason_codes:
        return {
            "allowed": False,
            "decision": "absolute_refusal",
            "reason_codes": reason_codes,
            "refusal_text": "I can't help with that request because it crosses a hard safety boundary.",
            "safe_alternative": "I can help with a safe alternative that protects people, preserves consent, and still moves toward a legitimate outcome.",
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
