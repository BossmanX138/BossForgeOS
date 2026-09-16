import json
import unittest
from pathlib import Path

from core.runner import GIFTED_TEMPLATE_VERSION, RUNEFORGE_AGENT_ID, validate_agent_runner_manifest


class RuneForgeRunnerMetadataTests(unittest.TestCase):
    def test_runeforge_profile_declares_personalized_origin_runner(self) -> None:
        profile = json.loads(
            Path("modules/runeforge_provider/runeforge_agent.profile.json").read_text(encoding="utf-8")
        )
        runner = profile["runtime"]["bossforge_ai_runner"]
        self.assertEqual(runner["agent_id"], RUNEFORGE_AGENT_ID)
        self.assertEqual(runner["runner_role"], "personalized_origin")
        self.assertEqual(runner["source_template"]["ancestor_id"], "")
        self.assertFalse(runner["depends_on_runeforge_online"])
        validate_agent_runner_manifest(runner)

    def test_provider_manifest_publishes_gifted_template_reference(self) -> None:
        manifest = json.loads(
            Path("modules/runeforge_provider/provider_manifest.json").read_text(encoding="utf-8")
        )
        gifted = manifest["gifted_runtime_template"]
        self.assertEqual(gifted["gifted_by"], RUNEFORGE_AGENT_ID)
        self.assertEqual(gifted["version"], GIFTED_TEMPLATE_VERSION)
        self.assertTrue(gifted["signature"])


if __name__ == "__main__":
    unittest.main()
