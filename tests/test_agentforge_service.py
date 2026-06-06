import os
import tempfile
import unittest
from unittest.mock import patch

from core.agents.model_gateway_agent import ModelGatewayAgent
from modules.agentforge import service


class AgentForgeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_root = os.environ.get("BOSSFORGE_ROOT")
        self._old_presence_flag = os.environ.get("BOSSGATE_DISABLE_PRESENCE_BROADCAST")
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BOSSFORGE_ROOT"] = self.tmp.name
        os.environ["BOSSGATE_DISABLE_PRESENCE_BROADCAST"] = "1"
        self.gateway = ModelGatewayAgent(interval_seconds=1)
        created = self.gateway.create_agent_profile(
            name="viewer",
            endpoint="ollama",
            system_prompt="Proprietary instructions.",
            temperature=0.2,
            max_tokens=600,
            tools=["filesystem"],
        )
        self.assertTrue(created["ok"])
        self.gateway_patch = patch("modules.agentforge.service._gateway", return_value=self.gateway)
        self.gateway_patch.start()

    def tearDown(self) -> None:
        self.gateway_patch.stop()
        self.tmp.cleanup()
        if self._old_root is None:
            os.environ.pop("BOSSFORGE_ROOT", None)
        else:
            os.environ["BOSSFORGE_ROOT"] = self._old_root
        if self._old_presence_flag is None:
            os.environ.pop("BOSSGATE_DISABLE_PRESENCE_BROADCAST", None)
        else:
            os.environ["BOSSGATE_DISABLE_PRESENCE_BROADCAST"] = self._old_presence_flag

    def test_hidden_agent_view_returns_sparse_public_identity_without_address(self) -> None:
        result = service.view_agent_profile("viewer", viewer_id="owner-1", viewer_channel="bossforgeos")
        self.assertTrue(result["ok"])
        self.assertTrue(result["sealed"])
        self.assertNotIn("profile", result)
        self.assertNotIn("secure_address", result)
        self.assertEqual(
            set(result["public_identity_card"]),
            {"name", "public_id", "agent_class", "agent_type", "rank", "rarity", "availability"},
        )

    def test_non_hidden_agent_view_requires_enabled_authenticated_channel(self) -> None:
        service.set_agent_disclosure_posture("viewer", "non_hidden")

        bossforge = service.view_agent_profile("viewer", viewer_id="owner-1", viewer_channel="bossforgeos")
        standalone = service.view_agent_profile("viewer", viewer_id="owner-1", viewer_channel="agentforge_standalone")
        unauthenticated = service.view_agent_profile("viewer", viewer_id="", viewer_channel="bossforgeos")
        bridgebase = service.view_agent_profile("viewer", viewer_id="owner-1", viewer_channel="bridgebase_alpha")

        self.assertFalse(bossforge["sealed"])
        self.assertEqual(bossforge["profile"]["system"], "Proprietary instructions.")
        self.assertFalse(standalone["sealed"])
        self.assertTrue(unauthenticated["sealed"])
        self.assertTrue(bridgebase["sealed"])
        self.assertNotIn("profile", bridgebase)

    def test_authenticated_non_hidden_view_still_redacts_gate_and_lineage(self) -> None:
        service.set_agent_disclosure_posture("viewer", "non_hidden")
        result = service.view_agent_profile("viewer", viewer_id="owner-1", viewer_channel="bossforgeos")
        self.assertFalse(result["sealed"])
        self.assertNotIn("secure_address", result["profile"])
        self.assertNotIn("gate_file", result["profile"])
        self.assertNotIn("runtime_lineage", result["profile"])
        self.assertNotIn("capsule", result["profile"])

    def test_disclosure_posture_update_is_reversible(self) -> None:
        unsealed = service.set_agent_disclosure_posture("viewer", "non_hidden")
        resealed = service.set_agent_disclosure_posture("viewer", "hidden")
        invalid = service.set_agent_disclosure_posture("viewer", "public")

        self.assertTrue(unsealed["ok"])
        self.assertTrue(resealed["ok"])
        self.assertEqual(resealed["disclosure_posture"], "hidden")
        self.assertFalse(invalid["ok"])
        self.assertIn("invalid disclosure_posture", invalid["message"])


if __name__ == "__main__":
    unittest.main()
