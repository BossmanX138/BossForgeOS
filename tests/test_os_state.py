import tempfile
import unittest
from pathlib import Path

from core.rune.rune_bus import RuneBus
from core.state.os_state import SCHEMA_VERSION, build_os_state, diff_os_states


class OsStateTests(unittest.TestCase):
    def test_build_os_state_contains_expected_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = RuneBus(root)
            bus.write_state("archivist", {"status": "alive"})
            bus.emit_event("archivist", "status_ping", {"ok": True})

            payload = build_os_state(root=root, event_limit=5)

            self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
            self.assertIn("bus", payload)
            self.assertIn("agents", payload)
            self.assertIn("state_tree", payload)
            self.assertIn("recent_events", payload)
            self.assertIn("archivist", payload["state_tree"])

    def test_diff_os_states_detects_changes(self) -> None:
        prev = {
            "state_tree": {
                "archivist": {"status": "idle"},
                "runeforge": {"status": "alive"},
            },
            "agents": {
                "runtime": {
                    "archivist": {"status": "idle"},
                    "runeforge": {"status": "alive"},
                }
            },
        }
        curr = {
            "state_tree": {
                "archivist": {"status": "alive"},
                "security_sentinel": {"status": "alive"},
            },
            "agents": {
                "runtime": {
                    "archivist": {"status": "alive"},
                    "runeforge": {"status": "alive"},
                }
            },
        }

        diff = diff_os_states(prev, curr)

        self.assertIn("runeforge", diff["removed_state_keys"])
        self.assertIn("security_sentinel", diff["added_state_keys"])
        self.assertIn("archivist", diff["changed_state_keys"])
        self.assertTrue(any(item["agent"] == "archivist" for item in diff["agent_status_changes"]))


if __name__ == "__main__":
    unittest.main()
