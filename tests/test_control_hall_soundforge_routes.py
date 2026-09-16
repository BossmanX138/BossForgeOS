import unittest
from unittest.mock import patch

from ui import control_hall


class ControlHallSoundforgeRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = control_hall.app.test_client()

    def test_soundforge_config_rejects_non_object(self) -> None:
        res = self.client.post('/api/soundforge/config', json={'config': 'bad'})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json().get('ok'))

    def test_activate_scheme_requires_name(self) -> None:
        res = self.client.post('/api/soundforge/activate_scheme', json={})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json().get('ok'))

    def test_migrate_legacy_rejects_invalid_collision_policy(self) -> None:
        res = self.client.post('/api/soundforge/migrate_legacy', json={'collision_policy': 'invalid'})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json().get('ok'))

    def test_finalize_rejects_invalid_collision_policy(self) -> None:
        res = self.client.post('/api/soundforge/finalize_soundstage_removal', json={'collision_policy': 'invalid'})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json().get('ok'))

    @patch.object(control_hall.soundforge_api, 'finalize_soundstage_removal')
    def test_finalize_maps_failed_result_to_409(self, mock_finalize) -> None:
        mock_finalize.return_value = {'ok': False, 'message': 'conflict'}
        res = self.client.post('/api/soundforge/finalize_soundstage_removal', json={'collision_policy': 'rename'})
        self.assertEqual(res.status_code, 409)
        self.assertFalse(res.get_json().get('ok'))


if __name__ == '__main__':
    unittest.main()
