import unittest
from unittest.mock import patch

from ui import control_hall


class ControlHallSecurityRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = control_hall.app.test_client()

    @patch.object(control_hall.security_api, "read_security_state")
    def test_security_state_route_contract(self, mock_state) -> None:
        mock_state.return_value = {"ok": True, "status": "idle", "findings": []}
        res = self.client.get("/api/security/state")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertIn("ok", payload)
        self.assertIn("findings", payload)
        self.assertIsInstance(payload["findings"], list)

    @patch.object(control_hall.security_api, "scan_workspace")
    def test_security_scan_route_contract(self, mock_scan) -> None:
        mock_scan.return_value = ({"ok": True, "findings": []}, 200)
        res = self.client.post("/api/security/scan", json={"path": "."})
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertIn("ok", payload)
        self.assertIn("findings", payload)

    @patch.object(control_hall.security_api, "set_policy")
    def test_security_policy_set_route_contract(self, mock_set) -> None:
        mock_set.return_value = ({"ok": True, "agent": "archivist", "actions": ["scan_workspace"]}, 200)
        res = self.client.post("/api/security/policy/set", json={"agent": "archivist", "actions": ["scan_workspace"]})
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertTrue(payload.get("ok"))


if __name__ == "__main__":
    unittest.main()
