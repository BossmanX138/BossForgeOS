import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from modules.ops_runtime import agent_state_adapter as adapter


class AgentStateAdapterTests(unittest.TestCase):
    def test_health_from_timestamp_states(self) -> None:
        now = datetime.now(timezone.utc)
        self.assertEqual(adapter.health_from_timestamp(None, now), "offline")
        self.assertEqual(adapter.health_from_timestamp("not-a-ts", now), "offline")
        self.assertEqual(adapter.health_from_timestamp((now - timedelta(seconds=10)).isoformat(), now), "online")
        self.assertEqual(adapter.health_from_timestamp((now - timedelta(seconds=120)).isoformat(), now), "stale")
        self.assertEqual(adapter.health_from_timestamp((now - timedelta(seconds=700)).isoformat(), now), "offline")

    def test_model_agent_state_key_normalizes(self) -> None:
        self.assertEqual(adapter.model_agent_state_key(" Refactor Bot! "), "model_agent_refactor_bot_")

    def test_read_agent_state_merges_static_and_dynamic_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)
            (state / "model_agents.json").write_text(json.dumps({"refactorer": {"endpoint": "local_a"}}), encoding="utf-8")
            (state / "model_endpoints.json").write_text(json.dumps({"local_a": {"provider": "ollama"}}), encoding="utf-8")
            (state / "model_agent_refactorer.json").write_text(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")

            result = adapter.read_agent_state(
                state_dir=state,
                static_agents={"hearth_tender": "Hearth-Tender"},
                now=datetime.now(timezone.utc),
            )

        self.assertIn("hearth_tender", result)
        self.assertIn("model_agent_refactorer", result)
        self.assertEqual(result["model_agent_refactorer"]["provider"], "ollama")


if __name__ == "__main__":
    unittest.main()
