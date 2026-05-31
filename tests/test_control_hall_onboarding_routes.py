import unittest
from unittest.mock import patch

from ui import control_hall


class ControlHallOnboardingRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = control_hall.app.test_client()

    @patch.object(control_hall.onboarding_api, "apply_step")
    @patch("ui.control_hall._save_json_state")
    def test_onboarding_post_contract(self, mock_save, mock_apply) -> None:
        mock_apply.return_value = ({"ok": True, "steps": {"workspace_check": True}, "updated_at": "x"}, 200)
        res = self.client.post("/api/onboarding", json={"step": "workspace_check"})
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertTrue(payload.get("ok"))
        mock_save.assert_called_once()

    @patch.object(control_hall.onboarding_api, "status_payload")
    def test_onboarding_status_contract(self, mock_status) -> None:
        mock_status.return_value = {"ok": True, "completion_percent": 66.7, "steps": {"a": True}}
        res = self.client.get("/api/onboarding/status")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertIn("completion_percent", payload)
        self.assertTrue(payload.get("ok"))

    @patch.object(control_hall.onboarding_api, "apply_step")
    @patch("ui.control_hall._save_json_state")
    def test_onboarding_post_invalid_step_returns_400_and_does_not_save(self, mock_save, mock_apply) -> None:
        mock_apply.return_value = ({"ok": False, "message": "unknown step"}, 400)
        res = self.client.post("/api/onboarding", json={"step": "not_a_step"})
        self.assertEqual(res.status_code, 400)
        payload = res.get_json()
        self.assertFalse(payload.get("ok"))
        mock_save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
