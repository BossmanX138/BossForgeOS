import unittest
from unittest.mock import patch

from ui import control_hall


class ControlHallOpsRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = control_hall.app.test_client()

    @patch.object(control_hall.ops_runtime_api, "scheduler_get")
    def test_scheduler_get_contract(self, mock_get) -> None:
        mock_get.return_value = {"ok": True, "jobs": [], "history": []}
        res = self.client.get("/api/scheduler")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertIn("ok", payload)
        self.assertIn("jobs", payload)

    @patch.object(control_hall.ops_runtime_api, "scheduler_post")
    @patch("ui.control_hall._save_json_state")
    def test_scheduler_post_contract(self, mock_save, mock_post) -> None:
        mock_post.return_value = ({"ok": True, "message": "job added", "jobs": [], "history": []}, 200)
        res = self.client.post("/api/scheduler", json={"action": "add", "label": "x", "command": "python -m unittest"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("ok"))
        mock_save.assert_called_once()

    @patch.object(control_hall.ops_runtime_api, "cicd_get")
    def test_cicd_get_contract(self, mock_get) -> None:
        mock_get.return_value = {"ok": True, "last_run": {}, "history": []}
        res = self.client.get("/api/cicd")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertIn("ok", payload)
        self.assertIn("history", payload)

    @patch.object(control_hall.ops_runtime_api, "cicd_post")
    @patch("ui.control_hall._save_json_state")
    def test_cicd_post_contract(self, mock_save, mock_post) -> None:
        mock_post.return_value = ({"ok": True, "last_run": {"ok": True}, "history": []}, 200)
        res = self.client.post("/api/cicd", json={"action": "run", "suite": "quick"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("ok"))
        mock_save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
