import json
import tempfile
import unittest
from pathlib import Path

from core.rune.rune_bus import RuneBus


class RuneBusTests(unittest.TestCase):
    def test_emit_command_creates_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bus = RuneBus(Path(tmp))
            path = bus.emit_command("hearth_tender", "status_ping", {"x": 1})
            self.assertTrue(path.exists())

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["target"], "hearth_tender")
            self.assertEqual(payload["command"], "status_ping")
            self.assertEqual(payload["args"], {"x": 1})

    def test_poll_commands_tracks_seen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bus = RuneBus(Path(tmp))
            bus.emit_command("hearth_tender", "status_ping")
            seen = set()

            first = bus.poll_commands(seen)
            second = bus.poll_commands(seen)

            self.assertEqual(len(first), 1)
            self.assertEqual(len(second), 0)


if __name__ == "__main__":
    unittest.main()
