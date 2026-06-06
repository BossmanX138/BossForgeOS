import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json

from core.agents.bossgate_agent import BossGateCommandAgent
from core.agents.model_gateway_agent import ModelGatewayAgent


class BossGateCommandAgentTests(unittest.TestCase):
    AUTH = {"operator_id": "bossforge-owner", "scope_id": "test-scope"}

    def setUp(self) -> None:
        self._old_root = os.environ.get("BOSSFORGE_ROOT")
        self._old_presence_flag = os.environ.get("BOSSGATE_DISABLE_PRESENCE_BROADCAST")
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BOSSFORGE_ROOT"] = self.tmp.name
        os.environ["BOSSGATE_DISABLE_PRESENCE_BROADCAST"] = "1"

    def tearDown(self) -> None:
        self.tmp.cleanup()
        if self._old_root is None:
            os.environ.pop("BOSSFORGE_ROOT", None)
        else:
            os.environ["BOSSFORGE_ROOT"] = self._old_root
        if self._old_presence_flag is None:
            os.environ.pop("BOSSGATE_DISABLE_PRESENCE_BROADCAST", None)
        else:
            os.environ["BOSSGATE_DISABLE_PRESENCE_BROADCAST"] = self._old_presence_flag

    def test_status_ping_command(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        agent.handle_command({"target": "bossgate", "command": "status_ping", "args": {}})
        events = agent.bus.read_latest_events(limit=1)
        self.assertEqual(events[0]["source"], "bossgate")
        self.assertEqual(events[0]["event"], "command:status_ping")
        self.assertTrue(events[0]["data"]["ok"])

    def test_sensitive_operations_require_operator_and_scope(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        discover = agent.discover_targets(timeout=1)
        scan = agent.scan_target("example.com")
        transfer = agent.transfer_agent("missing.bossgate.json", "http://bridgebase.local")
        install = agent.install_agent("missing.bossgate.json")

        for result in (discover, scan, transfer, install):
            self.assertFalse(result["ok"])
            self.assertIn("operator_id and scope_id are required", result["message"])

    def test_authorized_discovery_returns_authorization_context(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        with patch("core.agents.bossgate_agent.discover_transfer_targets", return_value=[]):
            result = agent.discover_targets(timeout=1, operator_id="bossforge-owner", scope_id="local-lab")
        self.assertTrue(result["ok"])
        self.assertEqual(result["authorization"], {"operator_id": "bossforge-owner", "scope_id": "local-lab", "actor_type": "human"})

    def test_discover_and_scan_commands(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        with patch("core.agents.bossgate_agent.discover_transfer_targets", return_value=[{"address": "10.0.0.5"}]):
            discover = agent.discover_targets(timeout=3, assistance_only=True, **self.AUTH)
        self.assertTrue(discover["ok"])
        self.assertEqual(discover["timeout"], 3)
        self.assertTrue(discover["assistance_only"])

        with patch("core.agents.bossgate_agent.scan_rest_endpoints", return_value={"ok": True, "allowed_for_transfer": True, "target_type": "bossforgeos"}):
            scan = agent.scan_target("example.com", **self.AUTH)
        self.assertTrue(scan["ok"])
        self.assertTrue(scan["allowed_for_transfer"])

    def test_package_and_transfer(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="porter",
            endpoint="ollama",
            system_prompt="Transport specialist.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        packaged = agent.package_agent(
            name="porter",
            target_system_id="bridgebase-alpha-01",
            visibility_profile="id_card_only",
            secret_key="pack-key",
            **self.AUTH,
        )
        self.assertTrue(packaged["ok"])
        package_path = Path(packaged["package_file"])
        self.assertTrue(package_path.exists())

        with patch.object(agent, "scan_target", return_value={"ok": True, "allowed_for_transfer": True, "target_type": "bridgebase_alpha"}):
            transferred = agent.transfer_agent(package_file=str(package_path), destination="http://bridgebase.local", dry_run=True, **self.AUTH)
        self.assertTrue(transferred["ok"])
        self.assertEqual(transferred["status"], "validated_only")

    def test_key_rotation_keeps_old_packages_installable(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="rotor",
            endpoint="ollama",
            system_prompt="Rotation test.",
            temperature=0.2,
            max_tokens=500,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        first_pkg = agent.package_agent(name="rotor", target_system_id="bridgebase-alpha-01", **self.AUTH)
        self.assertTrue(first_pkg["ok"])

        rotated = agent.rotate_key(new_key_id="k2", new_secret_key="new-secret", **self.AUTH)
        self.assertTrue(rotated["ok"])
        self.assertEqual(rotated["active_key_id"], "k2")

        installed_old = agent.install_agent(package_file=first_pkg["package_file"], **self.AUTH)
        self.assertTrue(installed_old["ok"])

    def test_non_super_gate_cannot_initiate_travel(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="porter_gateonly",
            endpoint="ollama",
            system_prompt="Transport specialist.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])
        agent = BossGateCommandAgent(interval_seconds=1)
        set_profile = agent.set_node_target_type("bossgate_connector")
        self.assertTrue(set_profile["ok"])
        packaged = agent.package_agent(name="porter_gateonly", target_system_id="bridgebase-alpha-01", secret_key="pack-key", **self.AUTH)
        self.assertTrue(packaged["ok"])
        denied = agent.transfer_agent(
            package_file=packaged["package_file"],
            destination="http://bridgebase.local",
            dry_run=False,
            **self.AUTH,
        )
        self.assertFalse(denied["ok"])
        self.assertIn("only super gates can initiate travel", denied["message"])

    def test_package_agent_assigns_valid_secure_address(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="addrcheck",
            endpoint="ollama",
            system_prompt="Address test.",
            temperature=0.2,
            max_tokens=500,
            tools=[],
        )
        self.assertTrue(created["ok"])
        agent = BossGateCommandAgent(interval_seconds=1)
        packaged = agent.package_agent(name="addrcheck", target_system_id="bridgebase-alpha-01", secret_key="pack-key", **self.AUTH)
        self.assertTrue(packaged["ok"])
        package_doc = json.loads(Path(packaged["package_file"]).read_text(encoding="utf-8"))
        self.assertIn("envelope", package_doc)
        profiles = json.loads((Path(self.tmp.name) / "bus" / "state" / "model_profiles.json").read_text(encoding="utf-8"))
        secure_address = str(profiles["addrcheck"].get("secure_address", ""))
        self.assertTrue(secure_address.startswith("*") and secure_address.endswith("*"))

    def test_map_snapshot_includes_agents_and_travelable_gates(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        discovered = [
            {
                "address": "10.1.2.3",
                "node_id": "node-a",
                "agent_name": "alpha",
                "agent_class": "prime",
                "created_by_node": "node-home",
                "current_node": "node-a",
                "target_type": "bridgebase_alpha",
                "allowed_for_transfer": True,
                "assistance_requested": False,
                "assistance_reason": "",
            },
            {
                "address": "10.1.2.9",
                "node_id": "node-b",
                "agent_name": "",
                "target_type": "bossgate_connector",
                "allowed_for_transfer": False,
            },
        ]
        with patch("core.agents.bossgate_agent.discover_transfer_targets", return_value=discovered):
            snapshot = agent.map_snapshot(refresh=True, timeout=1)
        self.assertTrue(snapshot["ok"])
        self.assertEqual(len(snapshot["agents"]), 1)
        self.assertEqual(snapshot["agents"][0]["agent_name"], "alpha")
        self.assertEqual(len(snapshot["travelable_gates"]), 1)
        self.assertEqual(snapshot["travelable_gates"][0]["node_id"], "node-a")

    def test_transfer_agent_posts_package_when_not_dry_run(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="porter_live",
            endpoint="ollama",
            system_prompt="Transport specialist.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])
        agent = BossGateCommandAgent(interval_seconds=1)
        packaged = agent.package_agent(name="porter_live", target_system_id="bridgebase-alpha-01", secret_key="pack-key", **self.AUTH)
        self.assertTrue(packaged["ok"])

        class _Resp:
            status = 202
            def read(self) -> bytes:
                return json.dumps({"ok": True, "accepted": True}).encode("utf-8")
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False

        with patch.object(agent, "scan_target", return_value={"ok": True, "allowed_for_transfer": True, "target_type": "bridgebase_alpha"}):
            with patch("core.agents.bossgate_agent.request.urlopen", return_value=_Resp()):
                transferred = agent.transfer_agent(
                    package_file=packaged["package_file"],
                    destination="http://bridgebase.local",
                    dry_run=False,
                    **self.AUTH,
                )
        self.assertTrue(transferred["ok"])
        self.assertEqual(transferred["status"], "transfer_posted")
        self.assertEqual(transferred["http_status"], 202)
        self.assertTrue(transferred["move_semantics"]["source_retired"])
        self.assertTrue(transferred["move_semantics"]["retirement"]["profile_removed"])
        self.assertFalse(Path(packaged["package_file"]).exists())

    def test_transfer_agent_handles_http_failure(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="porter_fail",
            endpoint="ollama",
            system_prompt="Transport specialist.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])
        agent = BossGateCommandAgent(interval_seconds=1)
        packaged = agent.package_agent(name="porter_fail", target_system_id="bridgebase-alpha-01", secret_key="pack-key", **self.AUTH)
        self.assertTrue(packaged["ok"])

        with patch.object(agent, "scan_target", return_value={"ok": True, "allowed_for_transfer": True, "target_type": "bridgebase_alpha"}):
            with patch("core.agents.bossgate_agent.request.urlopen", side_effect=RuntimeError("network down")):
                transferred = agent.transfer_agent(
                    package_file=packaged["package_file"],
                    destination="http://bridgebase.local",
                    dry_run=False,
                    **self.AUTH,
                )
        self.assertFalse(transferred["ok"])
        self.assertEqual(transferred["status"], "transfer_failed")

    def test_transfer_agent_posts_resume_plan_from_chunk_checkpoint(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="porter_resume",
            endpoint="ollama",
            system_prompt="Transport specialist.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])
        agent = BossGateCommandAgent(interval_seconds=1)
        packaged = agent.package_agent(name="porter_resume", target_system_id="bridgebase-alpha-01", secret_key="pack-key", **self.AUTH)
        self.assertTrue(packaged["ok"])
        package_path = Path(packaged["package_file"])
        package_doc = json.loads(package_path.read_text(encoding="utf-8"))
        package_doc["envelope"]["chunk_manifest"]["chunk_size"] = 4
        payload = package_doc["envelope"]["encrypted_payload"]
        from core.connectors.bossgate_connector import build_chunk_manifest
        package_doc["envelope"]["chunk_manifest"] = build_chunk_manifest(payload, chunk_size=4)
        package_path.write_text(json.dumps(package_doc), encoding="utf-8")

        class _Resp:
            status = 202
            def read(self) -> bytes:
                return json.dumps({"ok": True, "accepted": True}).encode("utf-8")
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False

        captured = {}
        def _urlopen(req, timeout=30):
            captured.update(json.loads(req.data.decode("utf-8")))
            return _Resp()

        with patch.object(agent, "scan_target", return_value={"ok": True, "allowed_for_transfer": True, "target_type": "bridgebase_alpha"}):
            with patch("core.agents.bossgate_agent.request.urlopen", side_effect=_urlopen):
                transferred = agent.transfer_agent(
                    package_file=packaged["package_file"],
                    destination="http://bridgebase.local",
                    dry_run=False,
                    resume_from_chunk=1,
                    **self.AUTH,
                )
        self.assertTrue(transferred["ok"])
        self.assertEqual(captured["resume_plan"]["completed_chunk_indexes"], [0])
        self.assertEqual(captured["resume_plan"]["next_chunk_index"], 1)

    def test_send_transfer_package_accepts_legacy_package_without_resume(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        package_path = Path(self.tmp.name) / "legacy.bossgate.json"
        package_path.write_text(json.dumps({"envelope": {"payload_hash": "legacy"}}), encoding="utf-8")

        class _Resp:
            status = 202
            def read(self) -> bytes:
                return b'{"ok":true}'
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False

        captured = {}
        def _urlopen(req, timeout=30):
            captured.update(json.loads(req.data.decode("utf-8")))
            return _Resp()

        with patch("core.agents.bossgate_agent.request.urlopen", side_effect=_urlopen):
            transferred = agent._send_transfer_package(package_path, "http://bridgebase.local")
        self.assertTrue(transferred["ok"])
        self.assertEqual(captured["resume_plan"], {})

    def test_install_agent_rejects_replay_after_agent_restart(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="porter_replay",
            endpoint="ollama",
            system_prompt="Transport specialist.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])
        first_agent = BossGateCommandAgent(interval_seconds=1)
        packaged = first_agent.package_agent(name="porter_replay", target_system_id="bridgebase-alpha-01", secret_key="pack-key", **self.AUTH)
        self.assertTrue(packaged["ok"])

        first_install = first_agent.install_agent(packaged["package_file"], secret_key="pack-key", **self.AUTH)
        self.assertTrue(first_install["ok"])
        restarted_agent = BossGateCommandAgent(interval_seconds=1)
        replayed = restarted_agent.install_agent(packaged["package_file"], secret_key="pack-key", **self.AUTH)
        self.assertFalse(replayed["ok"])
        self.assertIn("replay detected", replayed["message"])

    def test_package_agent_keeps_metadata_hidden_for_non_hidden_agent(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="inspectable",
            endpoint="ollama",
            system_prompt="Inspectable only through AgentForge.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
            encrypt_profile=False,
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        packaged = agent.package_agent(
            name="inspectable",
            target_system_id="bridgebase-alpha-01",
            visibility_profile="id_and_model_card",
            secret_key="pack-key",
            **self.AUTH,
        )
        self.assertTrue(packaged["ok"])
        package_doc = json.loads(Path(packaged["package_file"]).read_text(encoding="utf-8"))
        self.assertEqual(package_doc["metadata_visibility"]["profile"], "none")
        self.assertTrue(package_doc["envelope"]["encrypted_payload"])

    def test_unknown_human_operator_is_denied_discovery(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        result = agent.discover_targets(timeout=1, operator_id="unknown-user", scope_id="local-lab")
        self.assertFalse(result["ok"])
        self.assertIn("unknown operator", result["message"])

    def test_viewer_role_cannot_package_agent(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="viewer_denied",
            endpoint="ollama",
            system_prompt="Do not package.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])
        agent = BossGateCommandAgent(interval_seconds=1)
        assigned = agent.authorization_registry.assign_user_roles("bossforge-owner", "read-only", ["viewer"])
        self.assertTrue(assigned["ok"])
        denied = agent.package_agent(
            name="viewer_denied",
            target_system_id="bridgebase-alpha-01",
            operator_id="read-only",
            scope_id="local-lab",
        )
        self.assertFalse(denied["ok"])
        self.assertIn("bossgate.package", denied["message"])

    def test_agent_package_requires_coms_officer_skill(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="under_skilled",
            endpoint="ollama",
            system_prompt="Needs skill.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])
        agent = BossGateCommandAgent(interval_seconds=1)
        denied = agent.package_agent(
            name="under_skilled",
            target_system_id="bridgebase-alpha-01",
            operator_id="under_skilled",
            scope_id="self",
            actor_type="agent",
        )
        self.assertFalse(denied["ok"])
        self.assertIn("bossgate_coms_officer", denied["message"])

    def test_agent_transfer_requires_travel_control_skill(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="stationary",
            endpoint="ollama",
            system_prompt="Cannot self-transfer.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
            skills=["bossgate_coms_officer"],
        )
        self.assertTrue(created["ok"])
        agent = BossGateCommandAgent(interval_seconds=1)
        denied = agent.transfer_agent(
            package_file="missing.bossgate.json",
            destination="http://bridgebase.local",
            operator_id="stationary",
            scope_id="self",
            actor_type="agent",
        )
        self.assertFalse(denied["ok"])
        self.assertIn("bossgate_travel_control", denied["message"])

    def test_agent_install_requires_coms_officer_skill(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="installer_without_skill",
            endpoint="ollama",
            system_prompt="Cannot self-install.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])
        agent = BossGateCommandAgent(interval_seconds=1)
        denied = agent.install_agent(
            package_file="missing.bossgate.json",
            operator_id="installer_without_skill",
            scope_id="self",
            actor_type="agent",
        )
        self.assertFalse(denied["ok"])
        self.assertIn("bossgate_coms_officer", denied["message"])


if __name__ == "__main__":
    unittest.main()
