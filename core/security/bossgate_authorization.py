from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BOOTSTRAP_OWNER = "bossforge-owner"
ROLE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

PERMISSION_CATALOG = {
    "agentforge.profile.view",
    "bossgate.commerce.view",
    "bossgate.discovery.run",
    "bossgate.install",
    "bossgate.key.rotate",
    "bossgate.license.issue",
    "bossgate.license.validate",
    "bossgate.map.view",
    "bossgate.package",
    "bossgate.remote_debug.close",
    "bossgate.remote_debug.open",
    "bossgate.roles.manage",
    "bossgate.support.view",
    "bossgate.transfer",
    "bossgate.usage.report",
}

SEEDED_ROLES = {
    "viewer": {
        "permissions": [
            "agentforge.profile.view",
            "bossgate.discovery.run",
            "bossgate.map.view",
        ]
    },
    "operator": {
        "includes": ["viewer"],
        "permissions": [
            "bossgate.install",
            "bossgate.package",
            "bossgate.transfer",
        ],
    },
    "security_admin": {
        "includes": ["operator"],
        "permissions": [
            "bossgate.key.rotate",
            "bossgate.roles.manage",
        ],
    },
    "commerce_manager": {
        "includes": ["viewer"],
        "permissions": [
            "bossgate.commerce.view",
            "bossgate.license.issue",
            "bossgate.license.validate",
            "bossgate.usage.report",
        ],
    },
    "support_engineer": {
        "includes": ["viewer"],
        "permissions": [
            "bossgate.remote_debug.close",
            "bossgate.remote_debug.open",
            "bossgate.support.view",
        ],
    },
}


class BossGateAuthorizationRegistry:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load_or_create()

    def _default_payload(self) -> dict[str, Any]:
        return {
            "version": 1,
            "bootstrap_owner": BOOTSTRAP_OWNER,
            "seeded_roles": SEEDED_ROLES,
            "custom_roles": {},
            "users": {
                BOOTSTRAP_OWNER: {
                    "roles": ["security_admin"],
                }
            },
        }

    def _load_or_create(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return payload
            except (OSError, json.JSONDecodeError):
                pass
        payload = self._default_payload()
        self._save(payload)
        return payload

    def _save(self, payload: dict[str, Any] | None = None) -> None:
        if payload is not None:
            self._data = payload
        self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")

    def _roles(self) -> dict[str, dict[str, Any]]:
        out = {name: dict(value) for name, value in SEEDED_ROLES.items()}
        custom = self._data.get("custom_roles")
        if isinstance(custom, dict):
            out.update({str(name): dict(value) for name, value in custom.items() if isinstance(value, dict)})
        return out

    def roles_for_user(self, user_id: str) -> list[str]:
        users = self._data.get("users")
        user = users.get(str(user_id).strip()) if isinstance(users, dict) else None
        roles = user.get("roles") if isinstance(user, dict) else []
        return sorted({str(role).strip().lower() for role in roles if str(role).strip()}) if isinstance(roles, list) else []

    def effective_permissions(self, user_id: str) -> list[str]:
        roles = self._roles()
        pending = list(self.roles_for_user(user_id))
        visited: set[str] = set()
        permissions: set[str] = set()
        while pending:
            role_name = pending.pop()
            if role_name in visited:
                continue
            visited.add(role_name)
            role = roles.get(role_name)
            if not isinstance(role, dict):
                continue
            raw_permissions = role.get("permissions")
            if isinstance(raw_permissions, list):
                permissions.update(str(item).strip() for item in raw_permissions if str(item).strip() in PERMISSION_CATALOG)
            included = role.get("includes")
            if isinstance(included, list):
                pending.extend(str(item).strip().lower() for item in included if str(item).strip())
        return sorted(permissions)

    def has_permission(self, user_id: str, permission: str) -> bool:
        return str(permission).strip() in set(self.effective_permissions(user_id))

    def is_seeded_security_admin(self, user_id: str) -> bool:
        return "security_admin" in set(self.roles_for_user(user_id))

    def create_or_update_custom_role(self, acting_user: str, role_name: str, permissions: list[str]) -> dict[str, Any]:
        if not self.is_seeded_security_admin(acting_user):
            return {"ok": False, "message": "authorization denied: seeded security_admin role is required"}
        key = str(role_name).strip().lower()
        if not ROLE_NAME_PATTERN.fullmatch(key):
            return {"ok": False, "message": "invalid role name"}
        if key in SEEDED_ROLES:
            return {"ok": False, "message": "seeded roles are immutable"}
        normalized_permissions = sorted({str(item).strip() for item in permissions if str(item).strip()})
        unknown = sorted(set(normalized_permissions) - PERMISSION_CATALOG)
        if unknown:
            return {"ok": False, "message": f"unknown permissions: {', '.join(unknown)}"}
        custom_roles = self._data.setdefault("custom_roles", {})
        custom_roles[key] = {"permissions": normalized_permissions}
        self._save()
        return {"ok": True, "role": key, "permissions": normalized_permissions}

    def assign_user_roles(self, acting_user: str, user_id: str, roles: list[str]) -> dict[str, Any]:
        if not self.is_seeded_security_admin(acting_user):
            return {"ok": False, "message": "authorization denied: seeded security_admin role is required"}
        key = str(user_id).strip()
        if not key:
            return {"ok": False, "message": "user_id is required"}
        normalized_roles = sorted({str(role).strip().lower() for role in roles if str(role).strip()})
        unknown = sorted(set(normalized_roles) - set(self._roles()))
        if unknown:
            return {"ok": False, "message": f"unknown roles: {', '.join(unknown)}"}
        users = self._data.setdefault("users", {})
        users[key] = {"roles": normalized_roles}
        self._save()
        return {
            "ok": True,
            "user_id": key,
            "roles": normalized_roles,
            "permissions": self.effective_permissions(key),
        }

    def capabilities_for_user(self, user_id: str) -> dict[str, Any]:
        key = str(user_id).strip()
        permissions = self.effective_permissions(key)
        permission_set = set(permissions)
        return {
            "ok": True,
            "user_id": key,
            "known_user": bool(self.roles_for_user(key)),
            "roles": self.roles_for_user(key),
            "permissions": permissions,
            "panels": {
                "bossgate_map": "bossgate.map.view" in permission_set,
                "discovery": "bossgate.discovery.run" in permission_set,
                "operator": bool({"bossgate.package", "bossgate.transfer", "bossgate.install"} & permission_set),
                "commerce": "bossgate.commerce.view" in permission_set,
                "support": "bossgate.support.view" in permission_set,
                "security_admin": self.is_seeded_security_admin(key),
            },
            "permission_catalog": sorted(PERMISSION_CATALOG),
            "role_catalog": sorted(self._roles()),
        }
