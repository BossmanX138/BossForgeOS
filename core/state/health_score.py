"""Per-agent SLA / health scoring for BossForgeOS.

Computes a 0–100 health score for each agent based on:

* Whether state is present in the bus state tree.
* Whether the reported status is ``"alive"``.
* How recently the agent last wrote its state (recency).
* Whether the agent emitted any events in the last 30 minutes.
* Whether the agent's most recent events include error/critical entries.

Usage::

    from core.state.health_score import score_agent_health, score_all_agents

    result = score_agent_health("archivist", state=state_dict, recent_events=events)
    print(result["score"], result["grade"])   # e.g. 85 B

    all_scores = score_all_agents(state_tree, recent_events=events)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


# Grade thresholds (inclusive lower bound → grade letter).
_GRADE_THRESHOLDS: list[tuple[int, str]] = [
    (90, "A"),
    (75, "B"),
    (60, "C"),
    (40, "D"),
]


def _grade(score: int) -> str:
    for threshold, letter in _GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "F"


def _minutes_since(timestamp_iso: str) -> float | None:
    """Return minutes elapsed since *timestamp_iso*, or None if unparseable."""
    if not timestamp_iso:
        return None
    try:
        ts = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds() / 60.0
    except (ValueError, OverflowError):
        return None


def score_agent_health(
    agent_id: str,
    state: dict[str, Any],
    recent_events: list[dict[str, Any]] | None = None,
    max_stale_minutes: int = 15,
) -> dict[str, Any]:
    """Compute a health score (0–100) for *agent_id*.

    Scoring factors and their maximum contributions:

    ==================  ==========
    Factor              Max points
    ==================  ==========
    State present             20
    Status == "alive"         30
    Recency (≤ stale)         25
    Event activity            15
    No recent errors          10
    ==================  ==========
    Total                    100

    Parameters
    ----------
    agent_id:
        The agent to score.
    state:
        The agent's current state dict from the bus state tree (may be empty).
    recent_events:
        A list of recent bus events; used to assess activity and error rates.
    max_stale_minutes:
        Minutes beyond which a state timestamp is considered stale.

    Returns
    -------
    dict with keys ``agent_id``, ``score``, ``grade``, and ``factors``.
    """
    score = 0
    factors: dict[str, Any] = {}
    events = recent_events or []
    agent_events = [
        e
        for e in events
        if isinstance(e, dict)
        and str(e.get("source", "")).strip().lower() == agent_id.strip().lower()
    ]

    # ── Factor: state present ──────────────────────────────────────────
    state_present = bool(state)
    if state_present:
        score += 20
    factors["state_present"] = {
        "value": state_present,
        "contribution": 20 if state_present else 0,
    }

    # ── Factor: status is "alive" ──────────────────────────────────────
    status = str(state.get("status", "unknown")).strip().lower() if state else "unknown"
    is_alive = status == "alive"
    if is_alive:
        score += 30
    factors["status_alive"] = {
        "value": status,
        "contribution": 30 if is_alive else 0,
    }

    # ── Factor: last-seen recency ──────────────────────────────────────
    last_seen = str(state.get("timestamp", "")).strip() if state else ""
    minutes_ago = _minutes_since(last_seen)
    recency_ok = minutes_ago is not None and minutes_ago <= max_stale_minutes
    if recency_ok:
        score += 25
    factors["last_seen_recency"] = {
        "last_seen": last_seen,
        "minutes_ago": round(minutes_ago, 1) if minutes_ago is not None else None,
        "max_stale_minutes": max_stale_minutes,
        "contribution": 25 if recency_ok else 0,
    }

    # ── Factor: recent event activity (last 30 min) ───────────────────
    recent_active = any(
        (_minutes_since(str(e.get("timestamp", ""))) or 9999) <= 30
        for e in agent_events
    )
    if recent_active:
        score += 15
    factors["recent_activity"] = {
        "events_from_agent": len(agent_events),
        "any_in_last_30min": recent_active,
        "contribution": 15 if recent_active else 0,
    }

    # ── Factor: no error/critical in last 5 agent events ─────────────
    last_5 = agent_events[:5]
    has_errors = any(
        str(e.get("level", "info")).strip().lower() in {"error", "critical"}
        for e in last_5
    )
    no_errors = not has_errors
    if no_errors:
        score += 10
    factors["no_recent_errors"] = {
        "last_5_checked": len(last_5),
        "has_errors": has_errors,
        "contribution": 10 if no_errors else 0,
    }

    return {
        "agent_id": agent_id,
        "score": score,
        "grade": _grade(score),
        "factors": factors,
    }


def score_all_agents(
    state_tree: dict[str, dict[str, Any]],
    recent_events: list[dict[str, Any]] | None = None,
    max_stale_minutes: int = 15,
) -> dict[str, dict[str, Any]]:
    """Score health for every agent present in *state_tree*.

    Returns a dict mapping ``agent_id`` → health score result.
    """
    return {
        agent_id: score_agent_health(
            agent_id=agent_id,
            state=state,
            recent_events=recent_events,
            max_stale_minutes=max_stale_minutes,
        )
        for agent_id, state in state_tree.items()
    }
