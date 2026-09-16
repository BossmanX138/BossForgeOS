from __future__ import annotations

from typing import Any


def _normalize_presence_inputs(data: dict[str, Any]) -> tuple[str, str]:
    agent = str(data.get("agent", "")).strip().lower()
    user = str(data.get("user", "anon")).strip() or "anon"
    return agent, user


def _invalid_presence(agent: str, user: str) -> dict[str, Any]:
    return {"ok": False, "message": "agent is required", "agent": agent, "user": user}


def join_agent(agent_editors: dict[str, set[str]], agent_locks: dict[str, str], data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    agent, user = _normalize_presence_inputs(data)
    if not agent:
        return "", _invalid_presence(agent, user)
    agent_editors.setdefault(agent, set()).add(user)
    return agent, {"ok": True, "agent": agent, "editors": list(agent_editors.get(agent, set())), "lock": agent_locks.get(agent)}


def leave_agent(agent_editors: dict[str, set[str]], agent_locks: dict[str, str], data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    agent, user = _normalize_presence_inputs(data)
    if not agent:
        return "", _invalid_presence(agent, user)
    if agent in agent_editors:
        agent_editors[agent].discard(user)
        if not agent_editors[agent]:
            agent_editors.pop(agent)
    if agent_locks.get(agent) == user:
        agent_locks.pop(agent)
    return agent, {"ok": True, "agent": agent, "editors": list(agent_editors.get(agent, set())), "lock": agent_locks.get(agent)}


def lock_agent(agent_editors: dict[str, set[str]], agent_locks: dict[str, str], data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    agent, user = _normalize_presence_inputs(data)
    if not agent:
        return "", _invalid_presence(agent, user)
    if agent_locks.get(agent) in (None, user):
        agent_locks[agent] = user
    return agent, {"ok": True, "agent": agent, "editors": list(agent_editors.get(agent, set())), "lock": agent_locks.get(agent)}


def unlock_agent(agent_editors: dict[str, set[str]], agent_locks: dict[str, str], data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    agent, user = _normalize_presence_inputs(data)
    if not agent:
        return "", _invalid_presence(agent, user)
    if agent_locks.get(agent) == user:
        agent_locks.pop(agent)
    return agent, {"ok": True, "agent": agent, "editors": list(agent_editors.get(agent, set())), "lock": agent_locks.get(agent)}


def edit_agent_payload(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    agent, user = _normalize_presence_inputs(data)
    if not agent:
        return "", _invalid_presence(agent, user)
    content = data.get("content", {})
    return agent, {"ok": True, "agent": agent, "user": user, "content": content}
