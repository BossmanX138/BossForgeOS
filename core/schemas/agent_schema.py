from __future__ import annotations

import re
from pathlib import Path
from typing import Any

AGENT_SCHEMA_VERSION = "1.8"
_AGENT_ID_RE = re.compile(r"^[a-z][a-z0-9_\-]{1,63}$")
_AGENT_CLASSES = {"prime", "skilled", "normalized"}
_AGENT_TYPES = {"authority", "controller", "worker", "security", "tester", "ranger"}
_AGENT_RANKS = ("cadet", "specialist", "lieutenant", "captain", "commander", "general", "admiral")
_RANK_INDEX = {name: idx for idx, name in enumerate(_AGENT_RANKS)}
_RANK_SKILL_CAP = {
    "cadet": 4,
    "specialist": 5,
    "lieutenant": 6,
    "captain": 8,
    "commander": 10,
    "general": 12,
    "admiral": 15,
}
_RANK_SIGIL_CAP = {
    "cadet": 3,
    "specialist": 3,
    "lieutenant": 4,
    "captain": 5,
    "commander": 6,
    "general": 7,
    "admiral": 8,
}
_RANK_MCP_CAP = {
    "cadet": 5,
    "specialist": 6,
    "lieutenant": 7,
    "captain": 9,
    "commander": 11,
    "general": 13,
    "admiral": 15,
}
_DISPATCH_SCOPES = {"host", "lan", "remote"}
_SKILL_PREFIX_SKILLED_ONLY = (
    "advanced_",
    "orchestration_",
    "multi_agent_",
    "policy_",
)
_SKILL_PREFIX_PRIME_ONLY = (
    "prime_",
    "sigil_",
)
_SKILL_COMMAND = "command"
_SKILL_BOSSGATE_TRAVEL_CONTROL = "bossgate_travel_control"
_SIGIL_TRANSPORTER = "sigil_transporter"
_SKILLED_SIGILS = {_SIGIL_TRANSPORTER}
_DISALLOWED_SKILLS_BY_TYPE = {
    "authority": {_SKILL_BOSSGATE_TRAVEL_CONTROL},
    "worker": {_SKILL_COMMAND},
    "security": {_SKILL_BOSSGATE_TRAVEL_CONTROL},
    "tester": {_SKILL_COMMAND},
    "ranger": {_SKILL_COMMAND},
}
_REQUIRED_SKILLS_BY_TYPE = {
    "authority": {_SKILL_COMMAND},
    "controller": {_SKILL_COMMAND},
    "ranger": {_SKILL_BOSSGATE_TRAVEL_CONTROL},
}
_MCP_SERVER_PREFIX_ALLOWLIST = {
    "authority": ("bossgate", "authority", "audit", "policy"),
    "controller": ("orchestration", "controller", "workflow", "coordination"),
    "worker": ("worker", "task", "ops", "runtime", "file", "shell"),
    "security": ("security", "audit", "policy", "sentinel"),
    "tester": ("test", "qa", "validation", "sentinel"),
    "ranger": ("ranger", "repair", "maintenance", "diagnostic", "runtime", "ops", "shell", "remote"),
}
_PROPRIETARY_SEALED_FIELDS = [
    "llm",
    "mcp",
    "system_wrapper",
    "instructions",
    "integration",
    "runtime",
    "metadata",
]
_PRIORITY_DIMENSION_WEIGHTS = {
    "urgency": 0.35,
    "risk": 0.25,
    "proximity": 0.20,
    "confidence": 0.20,
}
_PERSONALITY_BEHAVIOR_PATTERNS = {
    "authority_like",
    "controller_like",
    "worker_like",
    "security_like",
    "tester_like",
    "ranger_like",
    "ranger_local",
}
_PERSONALITY_LOCAL_RANGER_PRESETS = {"introvert_local", "i_dont_like_crowded_places"}
_INTEREST_TOKEN_RE = re.compile(r"[a-z0-9_\-]+")
_INCIDENT_DOMAIN_HINTS: dict[str, dict[str, tuple[str, ...]]] = {
    "scope": {
        "host": ("host", "local", "this pc", "this machine", "workstation"),
        "lan": ("lan", "intranet", "office network", "subnet", "nearby device"),
        "remote": ("remote", "customer", "field", "offsite", "internet"),
    },
    "type": {
        "security": ("malware", "threat", "breach", "phish", "ransom", "exploit"),
        "tester": ("test", "regression", "flaky", "qa", "assertion", "coverage"),
        "ranger": ("repair", "fix", "maintenance", "broken", "ticket", "customer issue"),
        "controller": ("orchestrate", "coordination", "workflow", "assign", "dispatch"),
        "worker": ("batch", "routine", "task", "ops", "execution"),
    },
    "skills": {
        "bossgate_travel_control": ("travel", "remote", "onsite", "customer site", "field visit"),
        "command": ("delegate", "coordinate", "assign", "command", "handoff"),
        "runtime_observation": ("monitor", "latency", "bottleneck", "throughput", "runtime"),
        "task_queue_management": ("queue", "backlog", "stuck", "scheduling", "workload"),
    },
}



def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _clamp_score(value: Any, default: float = 0.5) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    if num < 0.0:
        return 0.0
    if num > 1.0:
        return 1.0
    return num


def _incident_blob(incident: dict[str, Any]) -> str:
    parts = [
        str(incident.get("title", "")),
        str(incident.get("summary", "")),
        str(incident.get("description", "")),
        str(incident.get("details", "")),
        str(incident.get("scope", "")),
        str(incident.get("location", "")),
        str(incident.get("source", "")),
    ]
    return " ".join(parts).strip().lower()


def _keyword_hits(blob: str, needles: tuple[str, ...]) -> int:
    return sum(1 for needle in needles if needle in blob)


def infer_incident_domains(incident: dict[str, Any]) -> dict[str, Any]:
    """Infer likely routing domains for an incident from free-form payload text.

    Returns candidates for scope/type/skills plus normalized triage dimensions.
    """
    blob = _incident_blob(incident)

    scope_scores = {
        scope: _keyword_hits(blob, hints)
        for scope, hints in _INCIDENT_DOMAIN_HINTS["scope"].items()
    }
    inferred_scope = max(scope_scores, key=lambda key: scope_scores[key])
    if scope_scores[inferred_scope] == 0:
        inferred_scope = str(incident.get("scope", "host")).strip().lower()
        if inferred_scope not in _DISPATCH_SCOPES:
            inferred_scope = "host"

    type_hits = {
        agent_type: _keyword_hits(blob, hints)
        for agent_type, hints in _INCIDENT_DOMAIN_HINTS["type"].items()
    }
    type_candidates = [name for name, hits in sorted(type_hits.items(), key=lambda item: item[1], reverse=True) if hits > 0]
    if not type_candidates:
        type_candidates = ["worker"]

    skill_hits = {
        skill: _keyword_hits(blob, hints)
        for skill, hints in _INCIDENT_DOMAIN_HINTS["skills"].items()
    }
    skill_candidates = [name for name, hits in sorted(skill_hits.items(), key=lambda item: item[1], reverse=True) if hits > 0]

    # Incident can carry explicit dimension overrides; otherwise defaults are synthesized.
    urgency = _clamp_score(incident.get("urgency"), default=0.55)
    risk = _clamp_score(incident.get("risk"), default=0.50)
    confidence = _clamp_score(incident.get("confidence"), default=0.60)
    proximity_raw = incident.get("proximity")
    if proximity_raw is None:
        proximity = 1.0 if inferred_scope == "host" else (0.7 if inferred_scope == "lan" else 0.4)
    else:
        proximity = _clamp_score(proximity_raw, default=0.5)

    rank_floor = "captain" if "command" in skill_candidates else "cadet"
    class_candidates = ["skilled"]
    if risk >= 0.8:
        class_candidates.insert(0, "prime")
    if inferred_scope == "host" and risk < 0.3 and urgency < 0.4:
        class_candidates = ["normalized", "skilled"]

    return {
        "scope": inferred_scope,
        "type_candidates": type_candidates,
        "skill_candidates": skill_candidates,
        "class_candidates": class_candidates,
        "rank_floor": rank_floor,
        "dimensions": {
            "urgency": urgency,
            "risk": risk,
            "proximity": proximity,
            "confidence": confidence,
        },
    }


def compute_adaptive_priority(
    agent_profile: dict[str, Any],
    incident: dict[str, Any],
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compute a policy-aware priority score for assigning an incident to one agent.

    Score is in [0, 100] and combines incident dimensions with role-fit modifiers.
    """
    profile = normalize_agent_profile(str(agent_profile.get("id", "agent")), agent_profile)
    inferred = infer_incident_domains(incident)
    dimensions = inferred["dimensions"]
    applied_weights = dict(_PRIORITY_DIMENSION_WEIGHTS)
    if isinstance(weights, dict):
        for key in applied_weights:
            if key in weights:
                applied_weights[key] = _clamp_score(weights.get(key), default=applied_weights[key])

    base_score = sum(dimensions[key] * applied_weights[key] for key in applied_weights)

    agent_type = str(profile.get("agent_type", "worker")).strip().lower()
    skills = set(_normalize_string_list(profile.get("skills")))
    dispatch_policy = profile.get("dispatch_policy") if isinstance(profile.get("dispatch_policy"), dict) else {}
    metadata = profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}
    personality_wrapper = metadata.get("personality_wrapper") if isinstance(metadata.get("personality_wrapper"), dict) else {}
    personality_preset = str(personality_wrapper.get("preset", "balanced")).strip().lower()
    behavior_patterns = {
        pattern
        for pattern in _normalize_string_list(personality_wrapper.get("behavior_patterns"))
        if pattern in _PERSONALITY_BEHAVIOR_PATTERNS
    }
    if personality_preset in _PERSONALITY_LOCAL_RANGER_PRESETS:
        behavior_patterns.add("ranger_local")
    interests = _normalize_string_list(personality_wrapper.get("interests"))
    preferred_scope = str(dispatch_policy.get("preferred_scope", "host")).strip().lower()
    incident_scope = str(inferred.get("scope", "host")).strip().lower()
    incident_text = " ".join(
        [
            str(incident.get("title", "")).strip().lower(),
            str(incident.get("summary", "")).strip().lower(),
            str(incident.get("details", "")).strip().lower(),
            " ".join(_normalize_string_list(incident.get("tags"))),
        ]
    ).strip()
    incident_tokens = set(_INTEREST_TOKEN_RE.findall(incident_text))

    scope_fit = 1.0 if preferred_scope == incident_scope else (0.75 if {preferred_scope, incident_scope} == {"host", "lan"} else 0.4)
    type_fit = 1.0 if agent_type in set(inferred.get("type_candidates", [])) else 0.7
    skill_fit = 1.0
    if inferred.get("skill_candidates"):
        overlap = len(skills.intersection(set(inferred["skill_candidates"])))
        skill_fit = max(0.4, min(1.0, overlap / max(1, len(inferred["skill_candidates"]))))

    personality_bias = 1.0
    if agent_type == "ranger":
        personality_bias = 1.08 if incident_scope == "remote" else 0.96
    elif agent_type == "controller":
        personality_bias = 1.06 if incident_scope in {"host", "lan"} else 0.88
    elif agent_type == "security":
        personality_bias = 1.05 if dimensions["risk"] >= 0.7 else 0.98
    elif agent_type == "tester":
        personality_bias = 1.05 if "tester" in inferred.get("type_candidates", []) else 0.95

    if incident_scope == "remote" and agent_type == "controller":
        can_leave = bool(dispatch_policy.get("can_leave_host_without_command", False))
        has_explicit_command = bool(incident.get("commanded", False) or incident.get("ordered", False))
        if not can_leave and not has_explicit_command:
            personality_bias *= 0.6

    pattern_type_map = {
        "authority_like": "authority",
        "controller_like": "controller",
        "worker_like": "worker",
        "security_like": "security",
        "tester_like": "tester",
        "ranger_like": "ranger",
    }
    type_candidates = set(inferred.get("type_candidates", []))
    for pattern, mapped_type in pattern_type_map.items():
        if pattern in behavior_patterns and mapped_type in type_candidates:
            type_fit *= 1.08

    if "ranger_local" in behavior_patterns:
        if incident_scope in {"host", "lan"}:
            scope_fit *= 1.12
            personality_bias *= 1.06
        else:
            scope_fit *= 0.85
            personality_bias *= 0.92

    interest_hits = 0
    if interests and incident_tokens:
        for interest in interests:
            words = set(_INTEREST_TOKEN_RE.findall(str(interest).lower()))
            if not words:
                continue
            if words.issubset(incident_tokens) or any(word in incident_tokens for word in words):
                interest_hits += 1
        if interest_hits > 0:
            personality_bias *= min(1.16, 1.0 + (0.06 * interest_hits))

    final_score = max(0.0, min(100.0, base_score * scope_fit * type_fit * skill_fit * personality_bias * 100.0))
    return {
        "agent_id": str(profile.get("id", "")).strip(),
        "score": round(final_score, 2),
        "breakdown": {
            "base": round(base_score * 100.0, 2),
            "scope_fit": round(scope_fit, 3),
            "type_fit": round(type_fit, 3),
            "skill_fit": round(skill_fit, 3),
            "personality_bias": round(personality_bias, 3),
            "behavior_patterns": sorted(behavior_patterns),
            "interest_hits": int(interest_hits),
            "interests": interests,
        },
        "incident_inference": inferred,
    }


def rank_agents_for_incident(
    incident: dict[str, Any],
    agent_profiles: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Return scored agent candidates sorted by descending adaptive priority."""
    scored = [compute_adaptive_priority(profile, incident, weights=weights) for profile in agent_profiles]
    return sorted(scored, key=lambda item: item.get("score", 0.0), reverse=True)


def get_agent_schema_path() -> Path:
    return Path(__file__).with_name("bosscrafts_agent.schema.json")


def _normalize_agent_id(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _default_agent_name(agent_id: str) -> str:
    return agent_id.replace("_", " ").replace("-", " ").title() or "Unknown Agent"


def _default_rank_for_class(agent_class: str) -> str:
    if agent_class == "prime":
        return "captain"
    if agent_class == "skilled":
        return "lieutenant"
    return "cadet"


def _default_type_for_profile(raw: dict[str, Any], agent_class: str) -> str:
    skills = set(_normalize_string_list(raw.get("skills")))
    if _SKILL_COMMAND in skills:
        return "controller"
    if _SKILL_BOSSGATE_TRAVEL_CONTROL in skills:
        return "ranger"
    if agent_class == "prime":
        return "controller"
    return "worker"


def _default_dispatch_policy_for_type(agent_type: str) -> dict[str, Any]:
    if agent_type == "ranger":
        return {
            "autonomous_bus_intake": True,
            "proactive_remote_hunt": True,
            "preferred_scope": "remote",
            "can_leave_host_without_command": True,
            "can_leave_host_for_lan_when_host_idle": True,
        }
    if agent_type == "controller":
        return {
            "autonomous_bus_intake": True,
            "proactive_remote_hunt": False,
            "preferred_scope": "host",
            "can_leave_host_without_command": False,
            "can_leave_host_for_lan_when_host_idle": True,
        }
    return {
        "autonomous_bus_intake": False,
        "proactive_remote_hunt": False,
        "preferred_scope": "host",
        "can_leave_host_without_command": False,
        "can_leave_host_for_lan_when_host_idle": False,
    }


def to_agent_card(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(profile.get("id", "")).strip(),
        "name": str(profile.get("name", "")).strip(),
        "description": str(profile.get("description", "")).strip(),
        "agent_class": str(profile.get("agent_class", "normalized")).strip().lower() or "normalized",
        "agent_type": str(profile.get("agent_type", "worker")).strip().lower() or "worker",
        "rank": str(profile.get("rank", "cadet")).strip().lower() or "cadet",
        "skills": _normalize_string_list(profile.get("skills")),
        "sigils": _normalize_string_list(profile.get("sigils")),
    }


def normalize_agent_profile(agent_id: str, profile: dict[str, Any] | None) -> dict[str, Any]:
    normalized_id = _normalize_agent_id(agent_id)
    raw = dict(profile or {})

    out: dict[str, Any] = dict(raw)
    out["id"] = normalized_id

    name = str(raw.get("name", "")).strip()
    out["name"] = name or _default_agent_name(normalized_id)

    description = str(raw.get("description", "")).strip()
    out["description"] = description or "BossCrafts agent"

    schema_version = str(raw.get("schema_version", "")).strip()
    out["schema_version"] = schema_version or AGENT_SCHEMA_VERSION

    raw_class = str(raw.get("agent_class", "")).strip().lower()
    out["agent_class"] = raw_class if raw_class in _AGENT_CLASSES else "normalized"

    raw_type = str(raw.get("agent_type", "")).strip().lower()
    out["agent_type"] = raw_type if raw_type in _AGENT_TYPES else _default_type_for_profile(raw, out["agent_class"])

    raw_rank = str(raw.get("rank", "")).strip().lower()
    out["rank"] = raw_rank if raw_rank in _AGENT_RANKS else _default_rank_for_class(out["agent_class"])

    if "module" in out and not isinstance(out.get("module"), str):
        out["module"] = str(out.get("module", ""))
    if "class" in out and not isinstance(out.get("class"), str):
        out["class"] = str(out.get("class", ""))
    if "version" in out and not isinstance(out.get("version"), str):
        out["version"] = str(out.get("version", ""))

    out["skills"] = _normalize_string_list(raw.get("skills"))
    if out["agent_class"] == "normalized":
        out["skills"] = []
    normalized_sigils = _normalize_string_list(raw.get("sigils"))
    if out["agent_class"] == "normalized":
        normalized_sigils = []
    else:
        normalized_sigils = [sigil for sigil in normalized_sigils if sigil not in set(out["skills"])]
    out["sigils"] = normalized_sigils

    capabilities = _normalize_string_list(raw.get("capabilities"))
    if capabilities:
        out["capabilities"] = capabilities

    llm_raw = raw.get("llm") if isinstance(raw.get("llm"), dict) else {}
    llm_router = raw.get("llm_router") if isinstance(raw.get("llm_router"), dict) else {}
    models = raw.get("models") if isinstance(raw.get("models"), dict) else {}
    inference = models.get("inference") if isinstance(models.get("inference"), dict) else {}

    llm_enabled = bool(llm_raw.get("enabled", llm_router.get("enabled", False)))
    llm_model = llm_raw.get("model") if isinstance(llm_raw.get("model"), dict) else {}
    out["llm"] = {
        "enabled": llm_enabled,
        "model": {
            "provider": str(llm_model.get("provider", llm_router.get("provider", inference.get("provider", "")))).strip(),
            "model_name": str(llm_model.get("model_name", llm_router.get("model", inference.get("model", "")))).strip(),
            "endpoint": str(llm_model.get("endpoint", llm_router.get("url", inference.get("url", "")))).strip(),
            "api_key_env": str(llm_model.get("api_key_env", llm_router.get("api_key_env", inference.get("api_key_env", "")))).strip(),
            "temperature": llm_model.get("temperature", llm_router.get("temperature", inference.get("temperature", 0.0))),
            "max_tokens": llm_model.get("max_tokens", llm_router.get("max_tokens", inference.get("max_tokens", 0))),
        },
    }

    mcp_raw = raw.get("mcp") if isinstance(raw.get("mcp"), dict) else {}
    mcp_servers_raw = mcp_raw.get("servers") if isinstance(mcp_raw.get("servers"), list) else []
    mcp_servers: list[dict[str, Any]] = []
    for item in mcp_servers_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        transport = str(item.get("transport", "")).strip().lower()
        if not name or not transport:
            continue
        mcp_servers.append(
            {
                "name": name,
                "transport": transport,
                "endpoint": str(item.get("endpoint", "")).strip(),
                "command": str(item.get("command", "")).strip(),
                "args": _normalize_string_list(item.get("args")),
                "required": bool(item.get("required", False)),
            }
        )
    is_normalized = out["agent_class"] == "normalized"
    if is_normalized and not mcp_servers:
        # Normalized agents derive their abilities from MCP rather than skills.
        # When a minimal profile (id/name/description only) is registered, inject
        # a default local stdio server so the profile satisfies the schema
        # requirement without requiring every caller to supply the full MCP config.
        _agent_type_for_mcp = out.get("agent_type", "worker")
        _type_prefixes = _MCP_SERVER_PREFIX_ALLOWLIST.get(_agent_type_for_mcp, ("worker",))
        _default_prefix = _type_prefixes[0]
        mcp_servers = [
            {
                "name": f"{_default_prefix}_{normalized_id}",
                "transport": "stdio",
                "endpoint": "",
                "command": "",
                "args": [],
                "required": False,
            }
        ]
    out["mcp"] = {
        "enabled": True if is_normalized else bool(mcp_raw.get("enabled", False)),
        "servers": mcp_servers,
    }

    wrapper_raw = raw.get("system_wrapper") if isinstance(raw.get("system_wrapper"), dict) else {}
    out["system_wrapper"] = {
        "enabled": bool(wrapper_raw.get("enabled", False)),
        "name": str(wrapper_raw.get("name", "")).strip(),
        "mode": str(wrapper_raw.get("mode", "")).strip(),
        "entrypoint": str(wrapper_raw.get("entrypoint", "")).strip(),
        "contract_version": str(wrapper_raw.get("contract_version", "")).strip(),
    }

    instructions_raw = raw.get("instructions") if isinstance(raw.get("instructions"), dict) else {}
    out["instructions"] = {
        "system": str(instructions_raw.get("system", "")).strip() or "Operate as a BossCrafts agent.",
        "developer": str(instructions_raw.get("developer", "")).strip(),
        "operational": _normalize_string_list(instructions_raw.get("operational")),
        "safety": _normalize_string_list(instructions_raw.get("safety")),
    }

    proprietary_raw = raw.get("proprietary") if isinstance(raw.get("proprietary"), dict) else {}
    sealed_fields = _normalize_string_list(proprietary_raw.get("sealed_fields"))
    if not sealed_fields:
        sealed_fields = list(_PROPRIETARY_SEALED_FIELDS)
    out["proprietary"] = {
        "managed_by": "bossgate_connector",
        "encrypted": True,
        "encryption_scheme": str(proprietary_raw.get("encryption_scheme", "bossgate-envelope-v1")).strip()
        or "bossgate-envelope-v1",
        "ciphertext_ref": str(proprietary_raw.get("ciphertext_ref", "")).strip(),
        "sealed_fields": sealed_fields,
        "access_policy": str(proprietary_raw.get("access_policy", "bossgate-internal")).strip() or "bossgate-internal",
    }

    integration = raw.get("integration") if isinstance(raw.get("integration"), dict) else {}
    bossgate_raw = integration.get("bossgate") if isinstance(integration.get("bossgate"), dict) else {}
    bossgate_enabled = bool(
        bossgate_raw.get("enabled", raw.get("bossgate_enabled", True))
    )
    requested_travel_capable = bool(
        bossgate_raw.get("travel_capable", raw.get("travel_capable", False))
    )
    travel_skill_present = _SKILL_BOSSGATE_TRAVEL_CONTROL in set(out["skills"])
    transport_sigil_present = _SIGIL_TRANSPORTER in set(out["sigils"])
    bossgate_travel_capable = bool(bossgate_enabled) and (
        (requested_travel_capable and travel_skill_present) or transport_sigil_present
    )
    integration = dict(integration)
    integration["bossgate"] = {
        "enabled": bossgate_enabled,
        "travel_capable": bossgate_travel_capable and bossgate_enabled,
        "connector": str(bossgate_raw.get("connector", "bossgate_connector")).strip() or "bossgate_connector",
        "allowed_targets": _normalize_string_list(bossgate_raw.get("allowed_targets")),
    }
    out["integration"] = integration

    dispatch_raw = raw.get("dispatch_policy") if isinstance(raw.get("dispatch_policy"), dict) else {}
    dispatch_defaults = _default_dispatch_policy_for_type(out["agent_type"])
    preferred_scope = str(dispatch_raw.get("preferred_scope", dispatch_defaults["preferred_scope"]))
    preferred_scope = preferred_scope.strip().lower()
    if preferred_scope not in _DISPATCH_SCOPES:
        preferred_scope = dispatch_defaults["preferred_scope"]
    out["dispatch_policy"] = {
        "autonomous_bus_intake": bool(dispatch_raw.get("autonomous_bus_intake", dispatch_defaults["autonomous_bus_intake"])),
        "proactive_remote_hunt": bool(dispatch_raw.get("proactive_remote_hunt", dispatch_defaults["proactive_remote_hunt"])),
        "preferred_scope": preferred_scope,
        "can_leave_host_without_command": bool(
            dispatch_raw.get("can_leave_host_without_command", dispatch_defaults["can_leave_host_without_command"])
        ),
        "can_leave_host_for_lan_when_host_idle": bool(
            dispatch_raw.get(
                "can_leave_host_for_lan_when_host_idle",
                dispatch_defaults["can_leave_host_for_lan_when_host_idle"],
            )
        ),
    }

    runtime = raw.get("runtime")
    out["runtime"] = runtime if isinstance(runtime, dict) else {}

    metadata = raw.get("metadata")
    metadata_out = metadata if isinstance(metadata, dict) else {}
    personality_raw = metadata_out.get("personality_wrapper") if isinstance(metadata_out.get("personality_wrapper"), dict) else {}
    preset = str(personality_raw.get("preset", "balanced")).strip().lower() or "balanced"
    behavior_patterns = [
        pattern
        for pattern in _normalize_string_list(personality_raw.get("behavior_patterns"))
        if pattern in _PERSONALITY_BEHAVIOR_PATTERNS
    ]
    if preset in _PERSONALITY_LOCAL_RANGER_PRESETS and "ranger_local" not in behavior_patterns:
        behavior_patterns.append("ranger_local")
    metadata_out = dict(metadata_out)
    metadata_out["personality_wrapper"] = {
        "preset": preset,
        "notes": str(personality_raw.get("notes", "")).strip(),
        "behavior_patterns": sorted(behavior_patterns),
        "interests": _normalize_string_list(personality_raw.get("interests")),
    }
    out["metadata"] = metadata_out

    out["agent_card"] = to_agent_card(out)

    return out


def validate_agent_profile(profile: dict[str, Any]) -> None:
    if not isinstance(profile, dict):
        raise ValueError("agent profile must be an object")

    agent_id = str(profile.get("id", "")).strip()
    if not agent_id:
        raise ValueError("agent profile id is required")
    if not _AGENT_ID_RE.fullmatch(agent_id):
        raise ValueError(f"agent profile id is invalid: {agent_id}")

    name = str(profile.get("name", "")).strip()
    if not name:
        raise ValueError("agent profile name is required")

    description = str(profile.get("description", "")).strip()
    if not description:
        raise ValueError("agent profile description is required")

    schema_version = str(profile.get("schema_version", "")).strip()
    if not schema_version:
        raise ValueError("agent profile schema_version is required")
    if not schema_version.startswith("1."):
        raise ValueError(
            f"unsupported schema_version '{schema_version}', expected 1.x"
        )

    agent_class = str(profile.get("agent_class", "")).strip().lower()
    if agent_class not in _AGENT_CLASSES:
        raise ValueError("agent profile agent_class must be 'prime', 'skilled', or 'normalized'")

    agent_type = str(profile.get("agent_type", "")).strip().lower()
    if agent_type not in _AGENT_TYPES:
        raise ValueError("agent profile agent_type must be 'authority', 'controller', 'worker', 'security', 'tester', or 'ranger'")

    rank = str(profile.get("rank", "")).strip().lower()
    if rank not in _AGENT_RANKS:
        raise ValueError(f"agent profile rank must be one of: {', '.join(_AGENT_RANKS)}")

    for key in ("skills", "sigils"):
        value = profile.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"agent profile {key} must be a list of strings")

    skills = _normalize_string_list(profile.get("skills"))
    sigils = _normalize_string_list(profile.get("sigils"))
    if set(skills) & set(sigils):
        raise ValueError("agent profile sigils must be distinct from skills")
    if agent_class == "normalized" and sigils:
        raise ValueError("normalized agents cannot declare sigils")
    if agent_class == "normalized" and skills:
        raise ValueError("normalized agents cannot declare skills; normalized abilities must come from MCP")
    if agent_class == "skilled":
        has_skills = bool(skills)
        has_sigils = bool(sigils)
        if has_skills and has_sigils:
            raise ValueError("skilled agents must choose either skills or a single sigil specialist path, not both")
        if not has_skills and not has_sigils:
            raise ValueError("skilled agents must declare at least one skill or exactly one skilled sigil")
        if has_sigils:
            if len(sigils) != 1:
                raise ValueError("skilled sigil-specialist agents must declare exactly one sigil")
            if sigils[0] not in _SKILLED_SIGILS:
                allowed = ", ".join(sorted(_SKILLED_SIGILS))
                raise ValueError(f"skilled sigil-specialist agents can only use: {allowed}")
    if agent_class == "prime" and not sigils:
        raise ValueError("prime agents must declare at least one sigil")
    if _SKILL_COMMAND in set(skills) and _RANK_INDEX.get(rank, -1) < _RANK_INDEX["captain"]:
        raise ValueError("command skill requires rank captain or higher")
    if agent_class == "prime" and _RANK_INDEX.get(rank, -1) < _RANK_INDEX["captain"]:
        raise ValueError("prime agents must have rank captain or higher")
    skill_cap = _RANK_SKILL_CAP.get(rank, 0)
    if len(skills) > skill_cap:
        raise ValueError(f"rank '{rank}' allows at most {skill_cap} skills")
    sigil_cap = _RANK_SIGIL_CAP.get(rank, 0)
    if len(sigils) > sigil_cap:
        raise ValueError(f"rank '{rank}' allows at most {sigil_cap} sigils")
    if _SKILL_BOSSGATE_TRAVEL_CONTROL in set(skills) and agent_type not in {"ranger", "controller"}:
        raise ValueError("bossgate_travel_control is only allowed for agent_type='ranger' or 'controller'")

    required_skills = _REQUIRED_SKILLS_BY_TYPE.get(agent_type, set())
    missing_required = sorted(required_skills - set(skills))
    if missing_required:
        raise ValueError(f"agent profile agent_type='{agent_type}' requires skills: {', '.join(missing_required)}")
    disallowed_skills = _DISALLOWED_SKILLS_BY_TYPE.get(agent_type, set())
    present_disallowed = sorted(set(skills) & disallowed_skills)
    if present_disallowed:
        raise ValueError(
            f"agent profile agent_type='{agent_type}' cannot include skills: {', '.join(present_disallowed)}"
        )

    integration_preview = profile.get("integration") if isinstance(profile.get("integration"), dict) else {}
    bossgate_preview = integration_preview.get("bossgate") if isinstance(integration_preview.get("bossgate"), dict) else {}
    skilled_travel_capable = bool(bossgate_preview.get("travel_capable", False))
    if agent_class == "normalized":
        if any(skill.startswith(_SKILL_PREFIX_SKILLED_ONLY) for skill in skills):
            raise ValueError("normalized agents cannot use skilled-tier advanced skill namespaces")
        if any(skill.startswith(_SKILL_PREFIX_PRIME_ONLY) for skill in skills):
            raise ValueError("normalized agents cannot use prime-tier skill namespaces")
    if agent_class == "skilled":
        if any(skill.startswith(_SKILL_PREFIX_PRIME_ONLY) for skill in skills):
            raise ValueError("skilled agents cannot use prime-tier skill namespaces")

    capabilities = profile.get("capabilities")
    if capabilities is not None:
        if not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities):
            raise ValueError("agent profile capabilities must be a list of strings")

    for key in ("integration", "dispatch_policy", "runtime", "metadata", "mcp", "system_wrapper", "instructions", "agent_card", "proprietary"):
        value = profile.get(key)
        if value is not None and not isinstance(value, dict):
            raise ValueError(f"agent profile {key} must be an object")

    dispatch_policy = profile.get("dispatch_policy") if isinstance(profile.get("dispatch_policy"), dict) else {}
    for key in (
        "autonomous_bus_intake",
        "proactive_remote_hunt",
        "can_leave_host_without_command",
        "can_leave_host_for_lan_when_host_idle",
    ):
        if not isinstance(dispatch_policy.get(key), bool):
            raise ValueError(f"agent profile dispatch_policy.{key} must be a boolean")
    preferred_scope = str(dispatch_policy.get("preferred_scope", "")).strip().lower()
    if preferred_scope not in _DISPATCH_SCOPES:
        raise ValueError("agent profile dispatch_policy.preferred_scope must be 'host', 'lan', or 'remote'")
    metadata = profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}
    personality_wrapper = metadata.get("personality_wrapper") if isinstance(metadata.get("personality_wrapper"), dict) else {}
    personality_preset = str(personality_wrapper.get("preset", "balanced")).strip().lower()
    if not personality_preset:
        raise ValueError("agent profile metadata.personality_wrapper.preset is required")
    behavior_patterns = {
        pattern
        for pattern in _normalize_string_list(personality_wrapper.get("behavior_patterns"))
        if pattern
    }
    invalid_patterns = sorted(behavior_patterns - _PERSONALITY_BEHAVIOR_PATTERNS)
    if invalid_patterns:
        allowed = ", ".join(sorted(_PERSONALITY_BEHAVIOR_PATTERNS))
        raise ValueError(f"agent profile metadata.personality_wrapper.behavior_patterns contains invalid entries; allowed: {allowed}")
    local_ranger_mode = ("ranger_local" in behavior_patterns) or (personality_preset in _PERSONALITY_LOCAL_RANGER_PRESETS)
    interests = _normalize_string_list(personality_wrapper.get("interests"))
    if len(interests) > 24:
        raise ValueError("agent profile metadata.personality_wrapper.interests allows at most 24 entries")

    if agent_type == "controller":
        if dispatch_policy.get("autonomous_bus_intake") is not True:
            raise ValueError("controller agents must keep dispatch_policy.autonomous_bus_intake=true")
        if dispatch_policy.get("proactive_remote_hunt") is not False:
            raise ValueError("controller agents must keep dispatch_policy.proactive_remote_hunt=false")
        if dispatch_policy.get("can_leave_host_without_command") is not False:
            raise ValueError("controller agents cannot leave host without command")
        if dispatch_policy.get("can_leave_host_for_lan_when_host_idle") is not True:
            raise ValueError("controller agents must allow LAN travel when host queue is idle")
        if preferred_scope not in {"host", "lan"}:
            raise ValueError("controller agents dispatch scope must be 'host' or 'lan'")
    if agent_type == "ranger":
        if dispatch_policy.get("autonomous_bus_intake") is not True:
            raise ValueError("ranger agents must keep dispatch_policy.autonomous_bus_intake=true")
        if local_ranger_mode:
            if dispatch_policy.get("proactive_remote_hunt") is not False:
                raise ValueError("local-ranger personality mode requires dispatch_policy.proactive_remote_hunt=false")
            if dispatch_policy.get("can_leave_host_without_command") is not False:
                raise ValueError("local-ranger personality mode requires can_leave_host_without_command=false")
            if preferred_scope not in {"host", "lan"}:
                raise ValueError("local-ranger personality mode requires preferred_scope to be 'host' or 'lan'")
        else:
            if dispatch_policy.get("proactive_remote_hunt") is not True:
                raise ValueError("ranger agents must keep dispatch_policy.proactive_remote_hunt=true")
            if dispatch_policy.get("can_leave_host_without_command") is not True:
                raise ValueError("ranger agents must be able to leave host without command")
            if preferred_scope != "remote":
                raise ValueError("ranger agents dispatch scope must be 'remote'")

    agent_card = profile.get("agent_card") if isinstance(profile.get("agent_card"), dict) else {}
    for key in ("id", "name", "description", "agent_class", "agent_type"):
        if not str(agent_card.get(key, "")).strip():
            raise ValueError(f"agent profile agent_card.{key} is required")
    card_type = str(agent_card.get("agent_type", "")).strip().lower()
    if card_type not in _AGENT_TYPES:
        raise ValueError("agent profile agent_card.agent_type must be 'authority', 'controller', 'worker', 'security', 'tester', or 'ranger'")
    card_rank = str(agent_card.get("rank", "")).strip().lower()
    if not card_rank:
        raise ValueError("agent profile agent_card.rank is required")
    if card_rank not in _AGENT_RANKS:
        raise ValueError(f"agent profile agent_card.rank must be one of: {', '.join(_AGENT_RANKS)}")
    if str(agent_card.get("id", "")).strip() != agent_id:
        raise ValueError("agent profile agent_card.id must match profile id")

    llm = profile.get("llm")
    if not isinstance(llm, dict):
        raise ValueError("agent profile llm must be an object")
    if not isinstance(llm.get("enabled"), bool):
        raise ValueError("agent profile llm.enabled must be a boolean")
    if agent_class == "prime" and llm.get("enabled") is not True:
        raise ValueError("prime agents must have llm.enabled=true")
    if agent_class == "skilled" and llm.get("enabled") is not True:
        raise ValueError("skilled agents must have llm.enabled=true")
    llm_model = llm.get("model")
    if llm.get("enabled"):
        if not isinstance(llm_model, dict):
            raise ValueError("llm-backed agents must provide llm.model object")
        model_name = str(llm_model.get("model_name", "")).strip()
        if not model_name:
            raise ValueError("llm-backed agents must provide llm.model.model_name")
    if agent_class == "skilled" and skilled_travel_capable:
        if not isinstance(llm_model, dict):
            raise ValueError("travel-capable skilled agents must provide a dedicated llm.model configuration")
        provider = str(llm_model.get("provider", "")).strip()
        model_name = str(llm_model.get("model_name", "")).strip()
        endpoint = str(llm_model.get("endpoint", "")).strip()
        if not provider or not model_name or not endpoint:
            raise ValueError("travel-capable skilled agents must define llm.model.provider, model_name, and endpoint")

    integration = profile.get("integration") if isinstance(profile.get("integration"), dict) else {}
    bossgate = integration.get("bossgate")
    if not isinstance(bossgate, dict):
        raise ValueError("agent profile integration.bossgate must be an object")
    if not isinstance(bossgate.get("enabled"), bool):
        raise ValueError("integration.bossgate.enabled must be a boolean")
    if not isinstance(bossgate.get("travel_capable"), bool):
        raise ValueError("integration.bossgate.travel_capable must be a boolean")
    if bool(bossgate.get("travel_capable")) and not bool(bossgate.get("enabled")):
        raise ValueError("integration.bossgate.travel_capable cannot be true when bossgate is disabled")
    if bool(bossgate.get("travel_capable")) and _SKILL_BOSSGATE_TRAVEL_CONTROL not in set(skills) and _SIGIL_TRANSPORTER not in set(sigils):
        raise ValueError("bossgate travel capability requires 'bossgate_travel_control' or the 'sigil_transporter' sigil")

    proprietary = profile.get("proprietary") if isinstance(profile.get("proprietary"), dict) else {}
    if str(proprietary.get("managed_by", "")).strip() != "bossgate_connector":
        raise ValueError("agent profile proprietary.managed_by must be 'bossgate_connector'")
    if proprietary.get("encrypted") is not True:
        raise ValueError("agent profile proprietary.encrypted must be true")
    if not str(proprietary.get("encryption_scheme", "")).strip():
        raise ValueError("agent profile proprietary.encryption_scheme is required")
    sealed_fields = proprietary.get("sealed_fields")
    if not isinstance(sealed_fields, list) or not all(isinstance(item, str) and item.strip() for item in sealed_fields):
        raise ValueError("agent profile proprietary.sealed_fields must be a non-empty array of strings")
    if not bool(bossgate.get("enabled")):
        raise ValueError("integration.bossgate.enabled must be true for proprietary encrypted profiles")

    mcp = profile.get("mcp") if isinstance(profile.get("mcp"), dict) else {}
    if not isinstance(mcp.get("enabled"), bool):
        raise ValueError("agent profile mcp.enabled must be a boolean")
    servers = mcp.get("servers")
    if not isinstance(servers, list):
        raise ValueError("agent profile mcp.servers must be an array")
    if agent_class == "normalized":
        if mcp.get("enabled") is not True:
            raise ValueError("normalized agents must have mcp.enabled=true")
        if len(servers) < 1:
            raise ValueError("normalized agents must define at least one MCP server")
    mcp_cap = _RANK_MCP_CAP.get(rank, 0)
    if len(servers) > mcp_cap:
        raise ValueError(f"rank '{rank}' allows at most {mcp_cap} MCP servers")
    for server in servers:
        if not isinstance(server, dict):
            raise ValueError("each mcp server entry must be an object")
        name = str(server.get("name", "")).strip()
        transport = str(server.get("transport", "")).strip().lower()
        if not name:
            raise ValueError("each mcp server entry requires name")
        if transport not in {"stdio", "http", "sse", "ws", "custom"}:
            raise ValueError("each mcp server entry requires valid transport")
        allow_prefixes = _MCP_SERVER_PREFIX_ALLOWLIST.get(agent_type)
        if allow_prefixes:
            normalized_name = name.lower()
            if not any(normalized_name == prefix or normalized_name.startswith(prefix + "_") for prefix in allow_prefixes):
                allowed_text = ", ".join(allow_prefixes)
                raise ValueError(
                    f"agent_type='{agent_type}' only allows MCP server names with prefixes: {allowed_text}"
                )

    system_wrapper = profile.get("system_wrapper") if isinstance(profile.get("system_wrapper"), dict) else {}
    if not isinstance(system_wrapper.get("enabled"), bool):
        raise ValueError("agent profile system_wrapper.enabled must be a boolean")

    instructions = profile.get("instructions") if isinstance(profile.get("instructions"), dict) else {}
    system_instructions = str(instructions.get("system", "")).strip()
    if not system_instructions:
        raise ValueError("agent profile instructions.system is required")
    for key in ("operational", "safety"):
        value = instructions.get(key)
        if value is not None and (not isinstance(value, list) or not all(isinstance(item, str) for item in value)):
            raise ValueError(f"agent profile instructions.{key} must be an array of strings")


def can_issue_command(commander_profile: dict[str, Any], target_profile: dict[str, Any]) -> bool:
    commander_skills = set(_normalize_string_list(commander_profile.get("skills")))
    if _SKILL_COMMAND not in commander_skills:
        return False

    commander_rank = str(commander_profile.get("rank", "")).strip().lower()
    target_rank = str(target_profile.get("rank", "")).strip().lower()
    if commander_rank not in _RANK_INDEX or target_rank not in _RANK_INDEX:
        return False
    return _RANK_INDEX[commander_rank] > _RANK_INDEX[target_rank]


def is_assistance_mandatory(commander_profile: dict[str, Any], target_profile: dict[str, Any]) -> bool:
    if not can_issue_command(commander_profile, target_profile):
        return False
    commander_rank = str(commander_profile.get("rank", "")).strip().lower()
    target_rank = str(target_profile.get("rank", "")).strip().lower()
    return _RANK_INDEX[commander_rank] >= _RANK_INDEX["captain"] and _RANK_INDEX[target_rank] < _RANK_INDEX["captain"]
