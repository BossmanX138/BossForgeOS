import unittest
from unittest.mock import patch

from ui import control_hall


class ControlHallModelRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = control_hall.app.test_client()

    @patch.object(control_hall.model_gateway_api, "list_endpoints_from_state")
    def test_model_endpoints_uses_adapter(self, mock_list_endpoints) -> None:
        mock_list_endpoints.return_value = {"endpoints": {"local": {"url": "http://127.0.0.1:8000"}}}
        res = self.client.get("/api/model/endpoints")
        self.assertEqual(res.status_code, 200)
        self.assertIn("endpoints", res.get_json())
        mock_list_endpoints.assert_called_once()

    @patch.object(control_hall.agentforge_api, "list_agent_profiles")
    def test_model_agents_uses_agentforge_adapter(self, mock_list_agents) -> None:
        mock_list_agents.return_value = {"agents": {"scribe": {"endpoint": "local"}}}
        res = self.client.get("/api/model/agents")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertIn("agents", payload)
        self.assertIn("scribe", payload["agents"])
        mock_list_agents.assert_called_once()

    @patch.object(control_hall.agentforge_api, "create_agent_profile")
    def test_model_agents_create_uses_adapter(self, mock_create) -> None:
        mock_create.return_value = {"ok": True, "message": "created"}
        res = self.client.post("/api/model/agents/create", json={"name": "scribe", "endpoint": "local"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("ok"))
        mock_create.assert_called_once()

    @patch.object(control_hall.model_gateway_api, "invoke_endpoint")
    def test_model_chat_uses_adapter(self, mock_invoke) -> None:
        mock_invoke.return_value = {"ok": True, "reply": "pong"}
        res = self.client.post(
            "/api/model/chat",
            json={"endpoint": "local", "prompt": "ping", "temperature": 0.1, "max_tokens": 64},
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("ok"))
        mock_invoke.assert_called_once()


if __name__ == "__main__":
    unittest.main()
