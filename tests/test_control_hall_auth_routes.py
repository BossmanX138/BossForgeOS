import base64
import json
import time
import unittest
from unittest.mock import patch

from ui import control_hall


def _encode_handoff(payload: dict) -> str:
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


class ControlHallAuthRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = control_hall.app.test_client()
        control_hall._ASS_CONSUMED_LAUNCH_TICKETS.clear()

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


if __name__ == "__main__":
    unittest.main()
