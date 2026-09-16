from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class BosskeyAuthorization:
    package_id: str
    authorized_at: int
    proof_scope: str

    @classmethod
    def from_handoff(cls, payload: dict[str, Any] | None) -> "BosskeyAuthorization | None":
        if not isinstance(payload, dict):
            return None

        package_id = str(payload.get("packageId") or payload.get("package_id") or "").strip()
        authorized_at = payload.get("authorizedAt", payload.get("authorized_at"))
        proof_scope = str(payload.get("proofScope") or payload.get("proof_scope") or "").strip()
        if not package_id or authorized_at is None:
            return None

        try:
            ts = int(authorized_at)
        except (TypeError, ValueError):
            return None

        return cls(package_id=package_id, authorized_at=ts, proof_scope=proof_scope or "operational")

    def is_fresh(self, now_ts: int, max_age_seconds: int = 60) -> bool:
        return now_ts - int(self.authorized_at) <= max_age_seconds
