import base64
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core.security.bossgate_authorization import BossGateAuthorizationRegistry
from ui import control_hall


def _encode_handoff(payload: dict) -> str:
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


class ControlHallAuthRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = control_hall.app.test_client()
        control_hall._ASS_CONSUMED_LAUNCH_TICKETS.clear()
        control_hall._BOSSGATE_SESSIONS.clear()
        self.tmp = tempfile.TemporaryDirectory(prefix=".test-bossgate-auth-", dir=control_hall.PROJECT_ROOT)
        self.registry = BossGateAuthorizationRegistry(Path(self.tmp.name) / "roles.json")
        self.registry_patch = patch.object(control_hall, "_bossgate_authorization", return_value=self.registry)
        self.registry_patch.start()
        self.addCleanup(self.registry_patch.stop)
        self.addCleanup(self.tmp.cleanup)

    def _exchange_session(self, user_id: str, *, ticket_id: str = "ticket-session"):
        handoff = _encode_handoff(
            {
                "userId": user_id,
                "username": user_id,
                "roles": ["launcher.user"],
                "launchTicketId": ticket_id,
                "targetApp": "bossforgeos",
                "ts": int(time.time()),
            }
        )
        with patch.dict("os.environ", {"ASS_SESSION_HANDOFF_B64": handoff}, clear=False):
            return self.client.post(
                "/api/auth/launch-ticket/exchange",
                json={"ticketId": ticket_id, "targetApp": "bossforgeos"},
                headers={"Origin": "http://localhost"},
            )

    def test_launch_ticket_exchange_uses_ass_handoff(self) -> None:
        handoff = _encode_handoff(
            {
                "userId": "boss",
                "username": "boss",
                "roles": ["launcher.user"],
                "launchTicketId": "ticket-123",
                "targetApp": "bossforgeos",
                "ts": int(time.time()),
            }
        )

        with patch.dict("os.environ", {"ASS_SESSION_HANDOFF_B64": handoff}, clear=False):
            res = self.client.post(
                "/api/auth/launch-ticket/exchange",
                json={"ticketId": "ticket-123", "targetApp": "bossforgeos"},
            )

        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["session"]["userId"], "boss")
        self.assertEqual(payload["session"]["targetApp"], "bossforgeos")

    def test_launch_ticket_exchange_rejects_replayed_ticket(self) -> None:
        handoff = _encode_handoff(
            {
                "userId": "boss",
                "username": "boss",
                "roles": ["launcher.user"],
                "launchTicketId": "ticket-123",
                "targetApp": "bossforgeos",
                "ts": int(time.time()),
            }
        )

        with patch.dict("os.environ", {"ASS_SESSION_HANDOFF_B64": handoff}, clear=False):
            first = self.client.post(
                "/api/auth/launch-ticket/exchange",
                json={"ticketId": "ticket-123", "targetApp": "bossforgeos"},
            )
            second = self.client.post(
                "/api/auth/launch-ticket/exchange",
                json={"ticketId": "ticket-123", "targetApp": "bossforgeos"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        payload = second.get_json()
        self.assertFalse(payload["ok"])
        self.assertIn("already been used", payload["message"])

    def test_launch_ticket_exchange_preserves_bosskey_authorization(self) -> None:
        handoff = _encode_handoff(
            {
                "userId": "boss",
                "username": "boss",
                "roles": ["launcher.user"],
                "launchTicketId": "ticket-123",
                "targetApp": "bossforgeos",
                "ts": int(time.time()),
                "bosskey": {"packageId": "pkg-1", "authorizedAt": int(time.time()), "proofScope": "operational"},
            }
        )

        with patch.dict("os.environ", {"ASS_SESSION_HANDOFF_B64": handoff}, clear=False):
            res = self.client.post(
                "/api/auth/launch-ticket/exchange",
                json={"ticketId": "ticket-123", "targetApp": "bossforgeos"},
            )

        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertEqual(payload["session"]["bosskey"]["packageId"], "pkg-1")

    def test_launch_ticket_exchange_rejects_missing_identity(self) -> None:
        handoff = _encode_handoff(
            {
                "username": "boss",
                "roles": ["launcher.user"],
                "launchTicketId": "ticket-123",
                "targetApp": "bossforgeos",
                "ts": int(time.time()),
            }
        )

        with patch.dict("os.environ", {"ASS_SESSION_HANDOFF_B64": handoff}, clear=False):
            res = self.client.post(
                "/api/auth/launch-ticket/exchange",
                json={"ticketId": "ticket-123", "targetApp": "bossforgeos"},
            )

        self.assertEqual(res.status_code, 401)
        payload = res.get_json()
        self.assertFalse(payload["ok"])
        self.assertIn("missing required identity", payload["message"])

    def test_launch_ticket_exchange_rejects_stale_handoff(self) -> None:
        handoff = _encode_handoff(
            {
                "userId": "boss",
                "username": "boss",
                "roles": ["launcher.user"],
                "launchTicketId": "ticket-123",
                "targetApp": "bossforgeos",
                "ts": int(time.time()) - 601,
            }
        )

        with patch.dict("os.environ", {"ASS_SESSION_HANDOFF_B64": handoff}, clear=False):
            res = self.client.post(
                "/api/auth/launch-ticket/exchange",
                json={"ticketId": "ticket-123", "targetApp": "bossforgeos"},
            )

        self.assertEqual(res.status_code, 401)
        payload = res.get_json()
        self.assertFalse(payload["ok"])
        self.assertIn("expired", payload["message"])

    def test_index_injects_launch_ticket_bootstrap_when_ticket_present(self) -> None:
        handoff = _encode_handoff(
            {
                "userId": "boss",
                "username": "boss",
                "roles": ["launcher.user"],
                "launchTicketId": "ticket-123",
                "targetApp": "bossforgeos",
                "ts": int(time.time()),
            }
        )

        with patch.dict("os.environ", {"ASS_SESSION_HANDOFF_B64": handoff}, clear=False):
            res = self.client.get("/?launch_ticket=ticket-123&target_app=bossforgeos&launcher=ass")

        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("/api/auth/launch-ticket/exchange", html)
        self.assertIn("ticket-123", html)

    def test_role_management_rejects_anonymous_spoofed_acting_user(self) -> None:
        role_res = self.client.post(
            "/api/bossgate/access/roles",
            json={
                "acting_user": "bossforge-owner",
                "role_name": "spoofed-admin",
                "permissions": ["bossgate.map.view"],
            },
        )
        user_res = self.client.post(
            "/api/bossgate/access/users/spoof-target/roles",
            json={"acting_user": "bossforge-owner", "roles": ["security_admin"]},
        )

        self.assertEqual(role_res.status_code, 401)
        self.assertEqual(user_res.status_code, 401)
        self.assertFalse(role_res.get_json()["ok"])
        self.assertFalse(user_res.get_json()["ok"])
        self.assertNotIn("spoofed-admin", self.registry._data["custom_roles"])
        self.assertFalse(self.registry.roles_for_user("spoof-target"))

    def test_role_management_rejects_invalid_session_credential(self) -> None:
        self.client.set_cookie(control_hall._BOSSGATE_SESSION_COOKIE, "not-a-valid-session")

        res = self.client.post(
            "/api/bossgate/access/roles",
            json={"role_name": "invalid-session", "permissions": ["bossgate.map.view"]},
        )

        self.assertEqual(res.status_code, 401)
        self.assertIn("invalid session", res.get_json()["message"])

    def test_role_management_rejects_expired_session_credential(self) -> None:
        exchange = self._exchange_session("bossforge-owner")
        self.assertEqual(exchange.status_code, 200)
        for principal in control_hall._BOSSGATE_SESSIONS.values():
            principal["expiresAt"] = int(time.time()) - 1

        res = self.client.post(
            "/api/bossgate/access/roles",
            json={"role_name": "expired-session", "permissions": ["bossgate.map.view"]},
        )

        self.assertEqual(res.status_code, 401)
        self.assertIn("expired", res.get_json()["message"])

    def test_role_management_rejects_authenticated_lower_role_spoof(self) -> None:
        self.registry.assign_user_roles("bossforge-owner", "operator-user", ["operator"])
        exchange = self._exchange_session("operator-user")
        self.assertEqual(exchange.status_code, 200)

        res = self.client.post(
            "/api/bossgate/access/roles",
            json={
                "acting_user": "bossforge-owner",
                "role_name": "lower-role-spoof",
                "permissions": ["bossgate.map.view"],
            },
        )

        self.assertEqual(res.status_code, 403)
        self.assertNotIn("lower-role-spoof", self.registry._data["custom_roles"])

    def test_role_management_uses_authenticated_authorized_principal(self) -> None:
        exchange = self._exchange_session("bossforge-owner")
        self.assertEqual(exchange.status_code, 200)

        role_res = self.client.post(
            "/api/bossgate/access/roles",
            json={
                "acting_user": "operator-user",
                "role_name": "auditor",
                "permissions": ["bossgate.map.view"],
            },
            headers={"Origin": "http://localhost"},
        )
        user_res = self.client.post(
            "/api/bossgate/access/users/audit-user/roles",
            json={"acting_user": "operator-user", "roles": ["auditor"]},
            headers={"Origin": "http://localhost"},
        )

        self.assertEqual(role_res.status_code, 200)
        self.assertEqual(user_res.status_code, 200)
        self.assertEqual(self.registry.roles_for_user("audit-user"), ["auditor"])

    def test_role_management_rejects_cross_origin_cookie_request(self) -> None:
        exchange = self._exchange_session("bossforge-owner")
        self.assertEqual(exchange.status_code, 200)

        res = self.client.post(
            "/api/bossgate/access/roles",
            json={"role_name": "cross-origin", "permissions": ["bossgate.map.view"]},
            headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"},
        )

        self.assertEqual(res.status_code, 403)
        self.assertNotIn("cross-origin", self.registry._data["custom_roles"])

    def test_launch_ticket_exchange_rejects_cross_origin_request(self) -> None:
        handoff = _encode_handoff(
            {
                "userId": "bossforge-owner",
                "username": "bossforge-owner",
                "roles": ["launcher.user"],
                "launchTicketId": "ticket-cross-origin",
                "targetApp": "bossforgeos",
                "ts": int(time.time()),
            }
        )
        with patch.dict("os.environ", {"ASS_SESSION_HANDOFF_B64": handoff}, clear=False):
            res = self.client.post(
                "/api/auth/launch-ticket/exchange",
                json={"ticketId": "ticket-cross-origin", "targetApp": "bossforgeos"},
                headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"},
            )

        self.assertEqual(res.status_code, 403)
        self.assertFalse(control_hall._BOSSGATE_SESSIONS)


if __name__ == "__main__":
    unittest.main()
