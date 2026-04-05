import unittest
from unittest.mock import patch

from core.connectors.bossgate_connector import (
    ALLOWED_TRAVEL_TARGET_TYPES,
    classify_target_type,
    discover_transfer_targets,
    is_valid_transfer_target,
    scan_rest_endpoints,
)


class BossGateConnectorTargetValidationTests(unittest.TestCase):
    def test_classify_target_type_allows_bossforgeos(self) -> None:
        target_type = classify_target_type({"title": "BossForgeOS Node", "description": "BossForge OS runtime"})
        self.assertEqual(target_type, "bossforgeos")

    def test_is_valid_transfer_target_rejects_unknown(self) -> None:
        allowed, target_type = is_valid_transfer_target({"title": "Random IoT Device"})
        self.assertFalse(allowed)
        self.assertEqual(target_type, "unknown")

    @patch("core.connectors.bossgate_connector._http_get_json")
    @patch("core.connectors.bossgate_connector._http_get_headers")
    def test_scan_rest_endpoints_rejects_non_allowlisted_target(self, mock_get_headers, mock_get_json) -> None:
        mock_get_headers.return_value = (
            200,
            {
                "Server": "generic-proxy",
                "X-Powered-By": "random-stack",
                "X-BossGate-Role": "",
                "X-BossGate-Target-Type": "",
            },
        )
        mock_get_json.return_value = (
            200,
            {"Content-Type": "application/json"},
            {
                "info": {"title": "Device API", "description": "Not a travel destination"},
                "paths": {"/health": {"get": {}}},
            },
        )

        result = scan_rest_endpoints("http://example.com")
        self.assertFalse(result["ok"])
        self.assertFalse(result["allowed_for_transfer"])
        self.assertEqual(result["target_type"], "unknown")
        self.assertEqual(result["endpoints"], [])

    @patch("core.connectors.bossgate_connector._http_get_json")
    @patch("core.connectors.bossgate_connector._http_get_headers")
    def test_scan_rest_endpoints_allows_bridgebase_alpha(self, mock_get_headers, mock_get_json) -> None:
        mock_get_headers.return_value = (
            200,
            {
                "Server": "bridgebase-alpha-gateway",
                "X-Powered-By": "bossforge",
                "X-BossGate-Role": "bridgebase_alpha",
                "X-BossGate-Target-Type": "bridgebase_alpha",
            },
        )

        mock_get_json.return_value = (
            200,
            {"Content-Type": "application/json"},
            {
                "info": {"title": "bridgebase_alpha control plane", "description": "BossGate travel node"},
                "paths": {"/api/transfer": {"post": {}}, "/health": {"get": {}}},
            },
        )

        result = scan_rest_endpoints("example.com")
        self.assertTrue(result["ok"])
        self.assertTrue(result["allowed_for_transfer"])
        self.assertIn(result["target_type"], ALLOWED_TRAVEL_TARGET_TYPES)
        self.assertGreaterEqual(len(result["endpoints"]), 1)

    @patch("core.connectors.bossgate_connector.listen_for_beacons")
    def test_discover_transfer_targets_assistance_only(self, mock_listen_for_beacons) -> None:
        mock_listen_for_beacons.return_value = [
            {
                "address": "10.0.0.9",
                "node_id": "node-9",
                "target_type": "bossgate_connector",
                "agents": [
                    {
                        "name": "alpha",
                        "agent_class": "prime",
                        "bossgate_enabled": True,
                        "created_by_node": "owner-1",
                        "current_node": "node-9",
                        "assistance_requested": True,
                        "assistance_reason": "Need triage",
                    },
                    {
                        "name": "beta",
                        "agent_class": "core",
                        "bossgate_enabled": True,
                        "created_by_node": "owner-2",
                        "current_node": "node-9",
                        "assistance_requested": False,
                        "assistance_reason": "",
                    },
                ],
            }
        ]

        targets = discover_transfer_targets(timeout=3, assistance_only=True)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["agent_name"], "alpha")
        self.assertTrue(targets[0]["assistance_requested"])
        self.assertTrue(targets[0]["allowed_for_transfer"])
        self.assertEqual(targets[0]["created_by_node"], "owner-1")
        self.assertEqual(targets[0]["current_node"], "node-9")


if __name__ == "__main__":
    unittest.main()
