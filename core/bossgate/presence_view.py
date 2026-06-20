from __future__ import annotations

from typing import Any

from core.schemas.agent_capsule import build_public_identity_card


def classify_presence_color(trust_state: str, discovery_state: str) -> str:
    if str(discovery_state or "").strip().lower() == "unrevealed_beacon":
        return "grey"
    return {
        "own": "green",
        "trade_linked": "blue",
        "unknown": "red",
    }.get(str(trust_state or "").strip().lower(), "grey")


def build_node_presence(raw: dict[str, Any], *, current_node_id: str) -> dict[str, Any]:
    node_id = str(raw.get("node_id", "")).strip() or "unknown-node"
    visited = bool(raw.get("visited", False))
    trade_linked = bool(raw.get("trade_linked", False))
    if node_id == current_node_id:
        trust_state = "own"
    elif trade_linked:
        trust_state = "trade_linked"
    else:
        trust_state = "neutral_unaffiliated" if not visited else "unknown"
    discovery_state = "revealed" if visited or trust_state == "own" else "unrevealed_beacon"
    return {
        "presence_kind": "node",
        "node_id": node_id,
        "node_type": str(raw.get("target_type", "unknown")).strip() or "unknown",
        "visited": visited,
        "trust_state": trust_state,
        "discovery_state": discovery_state,
        "color": classify_presence_color(trust_state, discovery_state),
        "display_name": node_id if discovery_state == "revealed" else "",
        "public_summary": str(raw.get("target_type", "")).strip() if discovery_state == "revealed" else "",
    }


def build_agent_presence(name: str, profile: dict[str, Any], *, current_node_id: str) -> dict[str, Any]:
    model_card = profile.get("agent_card") if isinstance(profile.get("agent_card"), dict) else build_public_identity_card(profile)
    origin_node_id = str(profile.get("created_by_node", "")).strip()
    current_node = str(profile.get("current_node", "")).strip()
    inspection_state = (
        "origin_forge_available"
        if origin_node_id and origin_node_id == current_node_id and current_node == current_node_id
        else "origin_forge_required"
    )
    return {
        "presence_kind": "agent",
        "agent_id": str(name or "").strip().lower(),
        "agent_name": str(name or "").strip().lower(),
        "origin_node_id": origin_node_id,
        "current_node_id": current_node,
        "trust_state": "own" if origin_node_id == current_node_id else "trade_linked",
        "public_identity_card": build_public_identity_card(profile),
        "model_card": model_card,
        "disclosure_posture": str(profile.get("disclosure_posture", "hidden")).strip().lower() or "hidden",
        "inspection_state": inspection_state,
    }
