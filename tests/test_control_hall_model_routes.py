import unittest
from unittest.mock import Mock, patch

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

    @patch.object(control_hall.agentforge_api, "view_agent_profile")
    def test_agentforge_agent_view_forwards_viewer_context(self, mock_view) -> None:
        mock_view.return_value = {"ok": True, "agent": "scribe", "sealed": True}
        res = self.client.get("/api/agentforge/agents/scribe/view?viewer_id=owner-1&viewer_channel=bossforgeos")
        self.assertEqual(res.status_code, 200)
        mock_view.assert_called_once_with("scribe", viewer_id="owner-1", viewer_channel="bossforgeos")

    @patch.object(control_hall.agentforge_api, "set_agent_disclosure_posture")
    def test_agentforge_agent_disclosure_update_forwards_posture(self, mock_update) -> None:
        mock_update.return_value = {"ok": True, "agent": "scribe", "disclosure_posture": "non_hidden"}
        res = self.client.post("/api/agentforge/agents/scribe/disclosure", json={"disclosure_posture": "non_hidden"})
        self.assertEqual(res.status_code, 200)
        mock_update.assert_called_once_with("scribe", "non_hidden")

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

    @patch.object(control_hall.model_gateway_api, "bossgate_map_snapshot")
    def test_model_travel_map_uses_adapter(self, mock_snapshot) -> None:
        mock_snapshot.return_value = {
            "ok": True,
            "map": {
                "gates": [],
                "travelable_gates": [],
                "agents": {},
                "node_presences": [{"presence_kind": "node", "color": "grey"}],
                "agent_presences": [{"presence_kind": "agent", "color": "green"}],
            },
        }
        res = self.client.get("/api/model/travel/map?refresh=true&timeout=3")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertTrue(payload.get("ok"))
        self.assertIn("map", payload)
        self.assertIn("node_presences", payload["map"])
        self.assertIn("agent_presences", payload["map"])
        mock_snapshot.assert_called_once_with(refresh=True, timeout=3)

    @patch.object(control_hall.model_gateway_api, "discover_travel_targets")
    def test_model_travel_discover_forwards_authorization(self, mock_discover) -> None:
        mock_discover.return_value = {"ok": True, "targets": []}
        res = self.client.get(
            "/api/model/travel/discover?timeout=3&assistance_only=true&operator_id=bossm&scope_id=local-lab"
        )
        self.assertEqual(res.status_code, 200)
        mock_discover.assert_called_once_with(
            timeout=3,
            assistance_only=True,
            operator_id="bossm",
            scope_id="local-lab",
            actor_type="human",
        )

    @patch.object(control_hall.model_gateway_api, "validate_transfer_target")
    def test_model_travel_validate_forwards_authorization(self, mock_validate) -> None:
        mock_validate.return_value = {"ok": True, "allowed_for_transfer": True}
        res = self.client.post(
            "/api/model/travel/validate",
            json={"destination": "example.com", "operator_id": "bossm", "scope_id": "local-lab"},
        )
        self.assertEqual(res.status_code, 200)
        mock_validate.assert_called_once_with(
            destination="example.com",
            operator_id="bossm",
            scope_id="local-lab",
            actor_type="human",
        )

    @patch("ui.control_hall._read_bossgate_transfers")
    def test_model_travel_transfers_reads_transfer_log(self, mock_read_transfers) -> None:
        mock_read_transfers.return_value = {
            "ok": True,
            "items": [
                {
                    "node_id": "bossforgeos",
                    "destination": "http://bridgebase.local",
                    "presence_color": "green",
                    "agent_name": "promethius",
                }
            ],
        }
        res = self.client.get("/api/model/travel/transfers?limit=7")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertTrue(payload.get("ok"))
        self.assertIn("items", payload)
        self.assertEqual(payload["items"][0]["presence_color"], "green")
        mock_read_transfers.assert_called_once_with(limit=7)

    @patch("ui.control_hall._bossgate_authorization")
    def test_bossgate_access_capabilities_uses_registry(self, mock_registry_factory) -> None:
        registry = Mock()
        registry.capabilities_for_user.return_value = {"ok": True, "user_id": "bossforge-owner", "permissions": []}
        mock_registry_factory.return_value = registry
        res = self.client.get("/api/bossgate/access/capabilities?user_id=bossforge-owner")
        self.assertEqual(res.status_code, 200)
        registry.capabilities_for_user.assert_called_once_with("bossforge-owner")

    @patch.object(control_hall.model_gateway_api, "bossgate_presence_policy")
    def test_bossgate_access_policy_reads_gateway_policy(self, mock_policy) -> None:
        mock_policy.return_value = {"ok": True, "policy": {"accept_unknown_messages": False}}
        res = self.client.get("/api/bossgate/access/policy")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.get_json()["policy"]["accept_unknown_messages"])

    @patch.object(control_hall.model_gateway_api, "set_bossgate_presence_policy")
    def test_bossgate_access_policy_update_forwards_toggle(self, mock_policy) -> None:
        mock_policy.return_value = {"ok": True, "policy": {"accept_unknown_messages": True}}
        res = self.client.post("/api/bossgate/access/policy", json={"accept_unknown_messages": True})
        self.assertEqual(res.status_code, 200)
        mock_policy.assert_called_once_with(accept_unknown_messages=True)

    @patch("ui.control_hall._bossgate_authorization")
    def test_bossgate_access_role_create_forwards_security_admin(self, mock_registry_factory) -> None:
        registry = Mock()
        registry.create_or_update_custom_role.return_value = {"ok": True, "role": "auditor"}
        mock_registry_factory.return_value = registry
        res = self.client.post(
            "/api/bossgate/access/roles",
            json={"acting_user": "bossforge-owner", "role_name": "auditor", "permissions": ["bossgate.map.view"]},
        )
        self.assertEqual(res.status_code, 200)
        registry.create_or_update_custom_role.assert_called_once_with(
            acting_user="bossforge-owner",
            role_name="auditor",
            permissions=["bossgate.map.view"],
        )

    @patch("ui.control_hall._bossgate_authorization")
    def test_bossgate_access_user_assignment_forwards_multiple_roles(self, mock_registry_factory) -> None:
        registry = Mock()
        registry.assign_user_roles.return_value = {"ok": True, "user_id": "hybrid"}
        mock_registry_factory.return_value = registry
        res = self.client.post(
            "/api/bossgate/access/users/hybrid/roles",
            json={"acting_user": "bossforge-owner", "roles": ["commerce_manager", "support_engineer"]},
        )
        self.assertEqual(res.status_code, 200)
        registry.assign_user_roles.assert_called_once_with(
            acting_user="bossforge-owner",
            user_id="hybrid",
            roles=["commerce_manager", "support_engineer"],
        )

    @patch.object(control_hall.model_gateway_api, "bossgate_map_snapshot")
    @patch.object(control_hall.model_gateway_api, "bossgate_presence_policy")
    def test_control_hall_policy_and_map_routes_can_coexist(self, mock_policy, mock_map) -> None:
        mock_map.return_value = {"ok": True, "map": {"node_presences": [], "agent_presences": []}}
        mock_policy.return_value = {"ok": True, "policy": {"accept_unknown_messages": False}}
        map_res = self.client.get("/api/model/travel/map")
        policy_res = self.client.get("/api/bossgate/access/policy")
        self.assertEqual(map_res.status_code, 200)
        self.assertEqual(policy_res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
