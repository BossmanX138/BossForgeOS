import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ui import control_hall


class ControlHallIconForgeRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = control_hall.app.test_client()

    @patch.object(control_hall.iconforge_api, "list_backups")
    def test_iconforge_backups_contract(self, mock_list) -> None:
        mock_list.return_value = ({"ok": True, "items": {"k": {"path": "x"}}}, 200)
        res = self.client.get("/api/iconforge/backups")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertIn("ok", payload)
        self.assertIn("items", payload)

    @patch.object(control_hall.iconforge_api, "resolve_preview_path")
    @patch("ui.control_hall.send_file")
    def test_iconforge_preview_contract(self, mock_send_file, mock_resolve) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.png"
            p.write_bytes(b"\x89PNG\r\n\x1a\n")
            mock_send_file.return_value = MagicMock(status_code=200)
            mock_resolve.return_value = (p, None, 200)
            res = self.client.get("/api/iconforge/preview?path=a.png")
            self.assertEqual(res.status_code, 200)

    @patch.object(control_hall.iconforge_api, "apply_icon")
    def test_iconforge_apply_contract(self, mock_apply) -> None:
        mock_apply.return_value = ({"ok": True, "message": "applied"}, 200)
        res = self.client.post("/api/iconforge/apply", json={"target_type": "folder", "target": "C:\\t", "icon": "x.ico"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("ok"))

    @patch.object(control_hall.iconforge_api, "restore_backup")
    def test_iconforge_restore_contract(self, mock_restore) -> None:
        mock_restore.return_value = ({"ok": True, "message": "restored"}, 200)
        res = self.client.post("/api/iconforge/restore", json={"backup_key": "abc"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("ok"))


if __name__ == "__main__":
    unittest.main()
