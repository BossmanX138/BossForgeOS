import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.agents.model_gateway_agent import ModelGatewayAgent
from modules.agentforge import service
from modules.agentforge.entitlements import AgentForgeRuntimeContext


class AgentForgeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_root = os.environ.get("BOSSFORGE_ROOT")
        self._old_presence_flag = os.environ.get("BOSSGATE_DISABLE_PRESENCE_BROADCAST")
        self._old_model_source = os.environ.get("BOSSFORGE_DEFAULT_MODEL_SOURCE")
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BOSSFORGE_ROOT"] = self.tmp.name
        os.environ["BOSSGATE_DISABLE_PRESENCE_BROADCAST"] = "1"
        model_source = Path(self.tmp.name) / "test_model"
        model_source.mkdir()
        (model_source / "config.json").write_text('{"model_type":"qwen2"}', encoding="utf-8")
        (model_source / "tokenizer.json").write_text('{"version":"1.0"}', encoding="utf-8")
        (model_source / "model.safetensors").write_bytes(b"tiny-test-weights")
        os.environ["BOSSFORGE_DEFAULT_MODEL_SOURCE"] = str(model_source)
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
        if self._old_model_source is None:
            os.environ.pop("BOSSFORGE_DEFAULT_MODEL_SOURCE", None)
        else:
            os.environ["BOSSFORGE_DEFAULT_MODEL_SOURCE"] = self._old_model_source

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

    def test_integrated_creation_forwards_private_model_selection(self) -> None:
        gateway = Mock()
        gateway.create_agent_profile.return_value = {"ok": True}

        with patch("modules.agentforge.service._gateway", return_value=gateway):
            result = service.create_agent_profile(
                {
                    "name": "wayfinder",
                    "endpoint": "ollama",
                    "model_source_path": "F:/models/qwen",
                    "model_base_source_path": "F:/models/base",
                    "model_runtime_requirements": {"transformers": "local"},
                },
                runtime_context=AgentForgeRuntimeContext(
                    mode="integrated",
                    installation_id="bossforgeos",
                ),
            )

        self.assertTrue(result["ok"])
        self.assertEqual(
            gateway.create_agent_profile.call_args.kwargs["model_source_path"],
            "F:/models/qwen",
        )
        self.assertEqual(
            gateway.create_agent_profile.call_args.kwargs["model_base_source_path"],
            "F:/models/base",
        )

    def test_payload_cannot_claim_subscription_or_integrated_mode(self) -> None:
        result = service.create_agent_profile(
            {
                "name": "forged_claim",
                "endpoint": "ollama",
                "agent_class": "prime",
                "mode": "integrated",
                "subscribed": True,
            },
            runtime_context=AgentForgeRuntimeContext(
                mode="standalone",
                installation_id="local",
            ),
        )

        self.assertFalse(result["ok"])
        self.assertIn("Prime", result["message"])


if __name__ == "__main__":
    unittest.main()
