from __future__ import annotations

import hashlib
import re
from typing import Any

from .crypto import MEMORY_VAULT_SCHEMA_VERSION, canonical_json, normalize_agent_id


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SUPPORTED_RELATIONSHIP_FIELDS = {
    "user": "user",
    "agent": "agent",
    "counterpart_agent": "agent",
    "employer": "employer",
    "project": "project",
    "organization": "organization",
}
_REASON_EVENT_TYPES = {
    "commitment",
    "decision",
    "relationship_change",
    "lifecycle",
    "refusal",
    "failure",
    "recovery",
    "security",
    "discovery",
    "milestone",
}
_REASON_KEYWORDS = {
    "commitment": {"commit", "committed", "promise", "will", "follow", "followup"},
    "decision": {"decide", "decided", "decision", "ship", "approved"},
    "relationship_change": {"change", "changed", "contact", "relationship", "reassign"},
    "lifecycle": {"start", "started", "launch", "launched", "end", "ended"},
    "refusal": {"refuse", "refused", "cannot", "can't", "won't", "decline"},
    "failure": {"fail", "failed", "failure", "error", "broken"},
    "recovery": {"recover", "recovered", "restore", "restored", "resume"},
    "security": {"security", "secure", "auth", "authenticate", "credential"},
    "discovery": {"discover", "discovered", "found", "learned"},
    "milestone": {"milestone", "shipping", "shipped", "complete", "completed", "reach", "reached"},
}


def _normalize_path_safe_field(value: str, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text or text in {".", ".."} or "/" in text or "\\" in text:
        raise ValueError(f"{field_name} must be a normalized path-safe identifier")
    return text


def _tokenize(value: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(str(value).lower()) if len(token) >= 3}


def _payload_strings(payload: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key, value in payload.items():
        if key == "topics":
            continue
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, (int, float, bool)) and not isinstance(value, bool):
            values.append(str(value))
    return values


def _relationship_items(payload: dict[str, Any]) -> list[dict[str, str]]:
    relationships: dict[str, dict[str, str]] = {}
    for field, relationship_type in _SUPPORTED_RELATIONSHIP_FIELDS.items():
        value = payload.get(field)
        if not isinstance(value, str):
            continue
        key = value.strip()
        if not key:
            continue
        relationships[relationship_type] = {"type": relationship_type, "key": key}
    return [relationships[key] for key in sorted(relationships)]


def _search_terms(
    *,
    event_type: str,
    payload: dict[str, Any],
    relationships: list[dict[str, str]],
) -> list[str]:
    terms: set[str] = set()
    terms.update(_tokenize(event_type))
    for value in _payload_strings(payload):
        terms.update(_tokenize(value))
    for item in relationships:
        terms.update(_tokenize(item["key"]))
        terms.update(_tokenize(item["type"]))
    topics = payload.get("topics")
    if isinstance(topics, str):
        terms.update(_tokenize(topics))
    elif isinstance(topics, list):
        for entry in topics:
            if isinstance(entry, str):
                terms.update(_tokenize(entry))
    return sorted(terms)


def _topics(
    *,
    event_type: str,
    payload: dict[str, Any],
    reason_codes: list[str],
) -> list[str]:
    topics: set[str] = set(reason_codes)
    topics.update(_tokenize(event_type))
    raw_topics = payload.get("topics")
    if isinstance(raw_topics, str):
        topics.update(_tokenize(raw_topics))
    elif isinstance(raw_topics, list):
        for entry in raw_topics:
            if isinstance(entry, str):
                topics.update(_tokenize(entry))
    return sorted(topics)


def _classify_reason_codes(event_type: str, payload: dict[str, Any]) -> list[str]:
    normalized_type = str(event_type or "").strip().lower()
    tokens = set(_tokenize(normalized_type))
    for value in _payload_strings(payload):
        tokens.update(_tokenize(value))

    reasons: set[str] = set()
    if normalized_type in _REASON_EVENT_TYPES:
        reasons.add(normalized_type)
    for reason, keywords in _REASON_KEYWORDS.items():
        if normalized_type == reason or normalized_type.replace("-", "_") == reason:
            reasons.add(reason)
        elif tokens.intersection(keywords):
            reasons.add(reason)
    if bool(payload.get("important")):
        reasons.add("manual")
    return sorted(reasons)


def normalize_memory_event(
    *,
    agent_id: str,
    session_id: str,
    sequence: int,
    event_type: str,
    payload: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    normalized_agent_id = normalize_agent_id(agent_id)
    normalized_session_id = _normalize_path_safe_field(session_id, field_name="session_id")
    normalized_event_type = str(event_type or "").strip()
    if not normalized_event_type:
        raise ValueError("event_type is required")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    if int(sequence) <= 0:
        raise ValueError("sequence must be positive")
    normalized_timestamp = str(timestamp or "").strip()
    if not normalized_timestamp:
        raise ValueError("timestamp is required")

    core = {
        "agent_id": normalized_agent_id,
        "event_type": normalized_event_type,
        "payload": payload,
        "sequence": int(sequence),
        "session_id": normalized_session_id,
        "timestamp": normalized_timestamp,
    }
    event_id = "event-" + hashlib.sha256(canonical_json(core)).hexdigest()
    relationships = _relationship_items(payload)
    reason_codes = _classify_reason_codes(normalized_event_type, payload)
    manually_marked = bool(payload.get("important"))
    importance = {
        "level": "high" if reason_codes else "normal",
        "manually_marked": manually_marked,
        "reason_codes": sorted(set([*reason_codes, "manual"] if manually_marked and "manual" not in reason_codes else reason_codes)),
    }

    return {
        "schema_version": MEMORY_VAULT_SCHEMA_VERSION,
        "event_id": event_id,
        "agent_id": normalized_agent_id,
        "session_id": normalized_session_id,
        "sequence": int(sequence),
        "event_type": normalized_event_type,
        "timestamp": normalized_timestamp,
        "payload": payload,
        "search_terms": _search_terms(
            event_type=normalized_event_type,
            payload=payload,
            relationships=relationships,
        ),
        "topics": _topics(
            event_type=normalized_event_type,
            payload=payload,
            reason_codes=reason_codes,
        ),
        "relationships": relationships,
        "importance": importance,
    }
