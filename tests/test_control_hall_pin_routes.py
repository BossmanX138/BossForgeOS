import unittest
from unittest.mock import MagicMock, patch

from ui import control_hall


class ControlHallPinRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = control_hall.app.test_client()

    @patch.object(control_hall.ui_runtime_api, "pin_state")
    def test_pin_state_contract(self, mock_state) -> None:
        mock_state.return_value = {"ok": True, "running": False, "view": "", "alpha": 0.95}
        res = self.client.get("/api/pin/state")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertIn("ok", payload)
        self.assertIn("running", payload)
        self.assertIn("alpha", payload)

    @patch.object(control_hall.ui_runtime_api, "pin_launch_payload")
    @patch.object(control_hall.ui_runtime_api, "pin_overlay_path")
    @patch("ui.control_hall.subprocess.Popen")
    @patch("ui.control_hall._terminate_pin_overlay")
    def test_pin_launch_contract(self, _mock_terminate, mock_popen, mock_overlay_path, mock_launch_payload) -> None:
        mock_launch_payload.return_value = ("view_status", 0.8)
        mock_overlay_path.return_value = control_hall.Path(__file__).resolve()
        proc = MagicMock()
        proc.poll.return_value = 1
        mock_popen.return_value = proc
        res = self.client.post("/api/pin/launch", json={"view": "view_status", "alpha": 0.8})
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertTrue(payload.get("ok"))
        self.assertIn("view", payload)
        control_hall.PIN_OVERLAY_PROCESS = None


if __name__ == "__main__":
    unittest.main()
