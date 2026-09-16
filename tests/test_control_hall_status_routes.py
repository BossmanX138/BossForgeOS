import unittest
from unittest.mock import patch

from ui import control_hall


class ControlHallStatusRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = control_hall.app.test_client()

    @patch.object(control_hall.bus, 'read_latest_events')
    @patch('ui.control_hall.load_agent_task_state')
    @patch('ui.control_hall.read_agent_state')
    def test_status_includes_agent_state_and_agent_tasks(self, mock_agent_state, mock_agent_tasks, mock_events) -> None:
        mock_events.return_value = [{"event": "x"}]
        mock_agent_state.return_value = {
            "hearth_tender": {
                "display_name": "Hearth-Tender",
                "health": "online",
                "last_seen": "now",
                "endpoint": "",
                "provider": "",
            }
        }
        mock_agent_tasks.return_value = {
            "ok": True,
            "updated_at": "now",
            "items": [
                {
                    "id": "hearth_tender-1",
                    "agent": "Hearth Tender",
                    "task": "Smoke test",
                    "status": "assigned",
                    "started_at": "",
                    "completed_at": "",
                    "updated_at": "now",
                    "note": "",
                }
            ],
        }

        res = self.client.get('/api/status')
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()

        self.assertIn('agent_state', payload)
        self.assertIn('agent_tasks', payload)
        self.assertIsInstance(payload['agent_state'], dict)
        self.assertIsInstance(payload['agent_tasks'], dict)
        self.assertIn('items', payload['agent_tasks'])
        self.assertIsInstance(payload['agent_tasks']['items'], list)


if __name__ == '__main__':
    unittest.main()
