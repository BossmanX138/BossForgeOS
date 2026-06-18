import base64
import json
import unittest
from unittest.mock import patch

from ui import control_hall


def _encode_handoff(payload: dict) -> str:
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


class ControlHallAuthRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = control_hall.app.test_client()

    def test_launch_ticket_exchange_uses_ass_handoff(self) -> None:
        handoff = _encode_handoff(
            {
                "userId": "boss",
                "username": "boss",
                "roles": ["launcher.user"],
                "launchTicketId": "ticket-123",
                "targetApp": "bossforgeos",
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

    def test_index_injects_launch_ticket_bootstrap_when_ticket_present(self) -> None:
        handoff = _encode_handoff(
            {
                "userId": "boss",
                "username": "boss",
                "roles": ["launcher.user"],
                "launchTicketId": "ticket-123",
                "targetApp": "bossforgeos",
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
