from __future__ import annotations

from typing import Any


def join_agent(agent_editors: dict[str, set[str]], agent_locks: dict[str, str], data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    agent = str(data.get("agent", "")).strip().lower()
    user = str(data.get("user", "anon")).strip()
    agent_editors.setdefault(agent, set()).add(user)
    return agent, {"agent": agent, "editors": list(agent_editors.get(agent, set())), "lock": agent_locks.get(agent)}


def leave_agent(agent_editors: dict[str, set[str]], agent_locks: dict[str, str], data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    agent = str(data.get("agent", "")).strip().lower()
    user = str(data.get("user", "anon")).strip()
    if agent in agent_editors:
        agent_editors[agent].discard(user)
        if not agent_editors[agent]:
            agent_editors.pop(agent)
    if agent_locks.get(agent) == user:
        agent_locks.pop(agent)
    return agent, {"agent": agent, "editors": list(agent_editors.get(agent, set())), "lock": agent_locks.get(agent)}


def lock_agent(agent_editors: dict[str, set[str]], agent_locks: dict[str, str], data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    agent = str(data.get("agent", "")).strip().lower()
    user = str(data.get("user", "anon")).strip()
    if agent_locks.get(agent) in (None, user):
        agent_locks[agent] = user
    return agent, {"agent": agent, "editors": list(agent_editors.get(agent, set())), "lock": agent_locks.get(agent)}


def unlock_agent(agent_editors: dict[str, set[str]], agent_locks: dict[str, str], data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    agent = str(data.get("agent", "")).strip().lower()
    user = str(data.get("user", "anon")).strip()
    if agent_locks.get(agent) == user:
        agent_locks.pop(agent)
    return agent, {"agent": agent, "editors": list(agent_editors.get(agent, set())), "lock": agent_locks.get(agent)}


def edit_agent_payload(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    agent = str(data.get("agent", "")).strip().lower()
    user = str(data.get("user", "anon")).strip()
    content = data.get("content", {})
    return agent, {"agent": agent, "user": user, "content": content}
