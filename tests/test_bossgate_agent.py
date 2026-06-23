import os
import tempfile
import unittest
import time
from pathlib import Path
from unittest.mock import patch
import json

from core.agents.bossgate_agent import BossGateCommandAgent
from core.agents.model_gateway_agent import ModelGatewayAgent
from core.security.agent_profile_store import load_agent_profiles_store


class BossGateCommandAgentTests(unittest.TestCase):
    AUTH = {"operator_id": "bossforge-owner", "scope_id": "test-scope"}

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
        if self._old_model_source is None:
            os.environ.pop("BOSSFORGE_DEFAULT_MODEL_SOURCE", None)
        else:
            os.environ["BOSSFORGE_DEFAULT_MODEL_SOURCE"] = self._old_model_source

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
            self.assertEqual(result["reason_codes"], ["missing_authorization_context"])

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

    def test_keyring_loader_migrates_legacy_flat_keyring(self) -> None:
        legacy_path = Path(self.tmp.name) / "bus" / "state" / "bossgate_keys.json"
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text(json.dumps({"default": "legacy-seed", "k2": "rotated-secret"}, indent=2), encoding="utf-8")

        agent = BossGateCommandAgent(interval_seconds=1)

        self.assertEqual(agent._keyring["active_key_id"], "default")
        self.assertEqual(agent._keyring["keys"]["default"], "legacy-seed")
        self.assertEqual(agent._keyring["keys"]["k2"], "rotated-secret")

        persisted = json.loads(legacy_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["active_key_id"], "default")
        self.assertEqual(sorted(persisted["keys"].keys()), ["default", "k2"])

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
        self.assertEqual(denied["reason_codes"], ["travel_initiator_not_super_gate"])

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
        profiles, _ = load_agent_profiles_store(
            Path(self.tmp.name) / "bus" / "state" / "model_profiles.json",
            gateway.node_id,
        )
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

    def test_build_interface_map_combines_discovery_and_scan_outputs(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        discovered = [
            {
                "address": "http://bridgebase.local:8443",
                "node_id": "node-bridge",
                "target_type": "bridgebase_alpha",
                "allowed_for_transfer": True,
                "agent_name": "dockmaster",
            }
        ]
        scanned = {
            "ok": True,
            "allowed_for_transfer": True,
            "target_type": "bridgebase_alpha",
            "base_url": "http://bridgebase.local:8443",
            "endpoints": [
                {"path": "/api/transfer", "methods": ["post"]},
                {"path": "/health", "methods": ["get"]},
            ],
            "metadata": {
                "title": "bridgebase_alpha control plane",
                "description": "BossGate travel node",
                "x-bossgate-target-type": "bridgebase_alpha",
            },
        }
        with patch("core.agents.bossgate_agent.discover_transfer_targets", return_value=discovered):
            with patch("core.agents.bossgate_agent.scan_rest_endpoints", return_value=scanned):
                interface_map = agent.build_interface_map(
                    destination="http://bridgebase.local:8443",
                    timeout=2,
                    **self.AUTH,
                )

        self.assertTrue(interface_map["ok"])
        self.assertEqual(interface_map["target_type"], "bridgebase_alpha")
        self.assertEqual(interface_map["ports"], [8443])
        self.assertEqual(len(interface_map["documented_endpoints"]), 2)
        self.assertEqual(interface_map["documented_endpoints"][0]["methods"], ["POST"])
        self.assertEqual(interface_map["discovery_matches"][0]["node_id"], "node-bridge")
        self.assertIn("rest_json", interface_map["protocol_features"])
        self.assertIn("transfer_endpoint", interface_map["protocol_features"])
        self.assertIn("health_endpoint", interface_map["protocol_features"])
        self.assertTrue(Path(interface_map["interface_map_file"]).exists())

    def test_generate_connector_skeleton_uses_least_privilege_defaults(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        interface_map = {
            "ok": True,
            "destination": "http://bridgebase.local:8443",
            "base_url": "http://bridgebase.local:8443",
            "target_type": "bridgebase_alpha",
            "allowed_for_transfer": True,
            "ports": [8443],
            "metadata": {"title": "bridgebase_alpha control plane"},
            "documented_endpoints": [
                {"path": "/api/transfer", "methods": ["POST"]},
                {"path": "/health", "methods": ["GET"]},
                {"path": "/status", "methods": ["GET", "HEAD"]},
            ],
            "protocol_features": ["documented_api", "health_endpoint", "rest_json", "transfer_endpoint"],
            "discovery_matches": [{"node_id": "node-bridge", "address": "http://bridgebase.local:8443"}],
            "interface_map_file": str(Path(self.tmp.name) / "bridgebase-map.json"),
        }
        with patch.object(agent, "build_interface_map", return_value=interface_map):
            skeleton = agent.generate_connector_skeleton(
                destination="http://bridgebase.local:8443",
                **self.AUTH,
            )

        self.assertTrue(skeleton["ok"])
        self.assertEqual(skeleton["target_type"], "bridgebase_alpha")
        self.assertEqual(skeleton["default_access"], "read_only")
        self.assertTrue(Path(skeleton["skeleton_file"]).exists())
        enabled = skeleton["enabled_operations"]
        gated = skeleton["approval_required_operations"]
        self.assertEqual([item["path"] for item in enabled], ["/health", "/status"])
        self.assertEqual(enabled[1]["methods"], ["GET", "HEAD"])
        self.assertEqual([item["path"] for item in gated], ["/api/transfer"])
        self.assertFalse(gated[0]["enabled_by_default"])
        self.assertEqual(gated[0]["methods"], ["POST"])

    def test_write_connector_operation_requires_and_applies_explicit_approval(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        skeleton_path = Path(self.tmp.name) / "bridgebase-skeleton.json"
        skeleton_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "target_type": "bridgebase_alpha",
                    "default_access": "read_only",
                    "enabled_operations": [{"path": "/health", "methods": ["GET"]}],
                    "approval_required_operations": [
                        {
                            "path": "/api/transfer",
                            "methods": ["POST"],
                            "enabled_by_default": False,
                            "approval_required": True,
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        requested = agent.enable_connector_operation(
            skeleton_file=str(skeleton_path),
            path="/api/transfer",
            methods=["POST"],
            operator_id="bossforge-owner",
            scope_id="connector-rollout",
        )
        self.assertTrue(requested["ok"])
        self.assertEqual(requested["status"], "approval_requested")
        self.assertTrue(requested["approval_id"])
        self.assertTrue(agent.connector_pending_approval_path.exists())

        approved = agent.respond_connector_operation_approval(
            approval_id=requested["approval_id"],
            approved=True,
            operator_id="bossforge-owner",
            scope_id="connector-rollout",
        )
        self.assertTrue(approved["ok"])
        self.assertEqual(approved["status"], "operation_enabled")

        payload = json.loads(skeleton_path.read_text(encoding="utf-8"))
        gated = payload["approval_required_operations"][0]
        self.assertTrue(gated["enabled"])
        self.assertFalse(gated["approval_required"])
        self.assertEqual(gated["approved_by"]["operator_id"], "bossforge-owner")

    def test_end_to_end_connector_generation_for_approved_target(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        discovered = [
            {
                "address": "http://bridgebase.local:8443",
                "node_id": "node-bridge",
                "target_type": "bridgebase_alpha",
                "allowed_for_transfer": True,
                "agent_name": "dockmaster",
            }
        ]
        scanned = {
            "ok": True,
            "allowed_for_transfer": True,
            "target_type": "bridgebase_alpha",
            "base_url": "http://bridgebase.local:8443",
            "endpoints": [
                {"path": "/api/transfer", "methods": ["post"]},
                {"path": "/health", "methods": ["get"]},
            ],
            "metadata": {
                "title": "bridgebase_alpha control plane",
                "description": "BossGate travel node",
                "x-bossgate-target-type": "bridgebase_alpha",
            },
        }
        with patch("core.agents.bossgate_agent.discover_transfer_targets", return_value=discovered):
            with patch("core.agents.bossgate_agent.scan_rest_endpoints", return_value=scanned):
                interface_map = agent.build_interface_map(
                    destination="http://bridgebase.local:8443",
                    timeout=2,
                    **self.AUTH,
                )
                self.assertTrue(interface_map["ok"])

                skeleton = agent.generate_connector_skeleton(
                    destination="http://bridgebase.local:8443",
                    timeout=2,
                    **self.AUTH,
                )
                self.assertTrue(skeleton["ok"])
                self.assertEqual(skeleton["enabled_operations"][0]["path"], "/health")
                self.assertEqual(skeleton["approval_required_operations"][0]["path"], "/api/transfer")

        requested = agent.enable_connector_operation(
            skeleton_file=skeleton["skeleton_file"],
            path="/api/transfer",
            methods=["POST"],
            operator_id="bossforge-owner",
            scope_id="connector-rollout",
        )
        self.assertEqual(requested["status"], "approval_requested")

        approved = agent.respond_connector_operation_approval(
            approval_id=requested["approval_id"],
            approved=True,
            operator_id="bossforge-owner",
            scope_id="connector-rollout",
        )
        self.assertEqual(approved["status"], "operation_enabled")

        payload = json.loads(Path(skeleton["skeleton_file"]).read_text(encoding="utf-8"))
        gated = payload["approval_required_operations"][0]
        self.assertTrue(gated["enabled"])
        self.assertFalse(gated["approval_required"])

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

    def test_install_agent_accepts_legacy_package_without_wrapper(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="legacy_wrapped_agent",
            endpoint="ollama",
            system_prompt="Legacy package test.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        packaged = agent.package_agent(name="legacy_wrapped_agent", target_system_id="bridgebase-alpha-01", secret_key="legacy-wrap-key", **self.AUTH)
        self.assertTrue(packaged["ok"])

        package_path = Path(packaged["package_file"])
        package_doc = json.loads(package_path.read_text(encoding="utf-8"))
        package_path.write_text(json.dumps(dict(package_doc["envelope"]), indent=2), encoding="utf-8")

        installed = agent.install_agent(package_file=str(package_path), secret_key="legacy-wrap-key", **self.AUTH)
        self.assertTrue(installed["ok"])
        self.assertEqual(installed["agent_name"], "legacy_wrapped_agent")

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
        self.assertEqual(result["reason_codes"], ["unknown_operator"])

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
        self.assertEqual(denied["reason_codes"], ["missing_permission"])

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
        self.assertEqual(denied["reason_codes"], ["missing_agent_skill"])

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
        self.assertEqual(denied["reason_codes"], ["missing_agent_skill"])

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
        self.assertEqual(denied["reason_codes"], ["missing_agent_skill"])

    def test_transfer_agent_denies_unapproved_target_with_reason_code(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="porter_unapproved",
            endpoint="ollama",
            system_prompt="Transport specialist.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        packaged = agent.package_agent(
            name="porter_unapproved",
            target_system_id="bridgebase-alpha-01",
            secret_key="pack-key",
            **self.AUTH,
        )
        self.assertTrue(packaged["ok"])

        with patch.object(
            agent,
            "scan_target",
            return_value={
                "ok": False,
                "allowed_for_transfer": False,
                "target_type": "unknown",
            },
        ):
            denied = agent.transfer_agent(
                package_file=packaged["package_file"],
                destination="http://unknown.local",
                dry_run=True,
                **self.AUTH,
            )

        self.assertFalse(denied["ok"])
        self.assertEqual(denied["reason_codes"], ["target_not_approved_for_transfer"])

    def test_lifecycle_actions_emit_canonical_events_with_correlation_ids(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="porter_events",
            endpoint="ollama",
            system_prompt="Transport specialist.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        packaged = agent.package_agent(
            name="porter_events",
            target_system_id="bridgebase-alpha-01",
            secret_key="pack-key",
            **self.AUTH,
        )
        self.assertTrue(packaged["ok"])
        package_correlation = packaged.get("correlation_id")
        self.assertTrue(package_correlation)

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
        transfer_correlation = transferred.get("correlation_id")
        self.assertTrue(transfer_correlation)

        gateway.create_agent_profile(
            name="porter_install_events",
            endpoint="ollama",
            system_prompt="Install specialist.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        packaged_install = agent.package_agent(
            name="porter_install_events",
            target_system_id="bridgebase-alpha-01",
            secret_key="pack-key",
            output_file=str(Path(self.tmp.name) / "installable_package.bossgate.json"),
            **self.AUTH,
        )
        self.assertTrue(packaged_install["ok"])
        installed = agent.install_agent(packaged_install["package_file"], secret_key="pack-key", **self.AUTH)
        self.assertTrue(installed["ok"])
        install_correlation = installed.get("correlation_id")
        self.assertTrue(install_correlation)

        rotated = agent.rotate_key(new_key_id="audit-k2", new_secret_key="audit-secret", **self.AUTH)
        self.assertTrue(rotated["ok"])
        rotate_correlation = rotated.get("correlation_id")
        self.assertTrue(rotate_correlation)

        events = agent.bus.read_latest_events(limit=12)
        lifecycle = [item for item in events if str(item.get("event", "")).startswith("lifecycle:")]
        by_event = {item["event"]: item for item in lifecycle}

        self.assertIn("lifecycle:package_agent", by_event)
        self.assertIn("lifecycle:transfer_agent", by_event)
        self.assertIn("lifecycle:install_agent", by_event)
        self.assertIn("lifecycle:rotate_key", by_event)

        self.assertEqual(by_event["lifecycle:package_agent"]["data"]["correlation_id"], package_correlation)
        self.assertEqual(by_event["lifecycle:transfer_agent"]["data"]["correlation_id"], transfer_correlation)
        self.assertEqual(by_event["lifecycle:install_agent"]["data"]["correlation_id"], install_correlation)
        self.assertEqual(by_event["lifecycle:rotate_key"]["data"]["correlation_id"], rotate_correlation)
        self.assertEqual(by_event["lifecycle:transfer_agent"]["data"]["status"], "transfer_posted")

    def test_transfer_ledger_records_auditable_correlation_metadata(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="porter_ledger",
            endpoint="ollama",
            system_prompt="Transport specialist.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        packaged = agent.package_agent(
            name="porter_ledger",
            target_system_id="bridgebase-alpha-01",
            secret_key="pack-key",
            **self.AUTH,
        )
        self.assertTrue(packaged["ok"])

        with patch.object(agent, "scan_target", return_value={"ok": True, "allowed_for_transfer": True, "target_type": "bridgebase_alpha"}):
            transferred = agent.transfer_agent(
                package_file=packaged["package_file"],
                destination="http://bridgebase.local",
                dry_run=True,
                resume_from_chunk=2,
                **self.AUTH,
            )
        self.assertTrue(transferred["ok"])

        records = [
            json.loads(line)
            for line in agent.transfer_log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["record_type"], "bossgate_transfer_ledger_v1")
        self.assertEqual(record["action"], "transfer_agent")
        self.assertEqual(record["correlation_id"], transferred["correlation_id"])
        self.assertEqual(record["status"], "validated_only")
        self.assertEqual(record["authorization"], {"operator_id": "bossforge-owner", "scope_id": "test-scope", "actor_type": "human"})
        self.assertEqual(record["resume_from_chunk"], 2)
        self.assertEqual(record["schema_version"], 1)
        self.assertTrue(record["timestamp_utc"].endswith("+00:00"))

    def test_usage_report_aggregates_local_transfer_ledger(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="porter_usage",
            endpoint="ollama",
            system_prompt="Transport specialist.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        packaged = agent.package_agent(
            name="porter_usage",
            target_system_id="bridgebase-alpha-01",
            secret_key="pack-key",
            **self.AUTH,
        )
        self.assertTrue(packaged["ok"])

        with patch.object(agent, "scan_target", return_value={"ok": True, "allowed_for_transfer": True, "target_type": "bridgebase_alpha"}):
            dry_run = agent.transfer_agent(
                package_file=packaged["package_file"],
                destination="http://bridgebase.local",
                dry_run=True,
                **self.AUTH,
            )
        self.assertTrue(dry_run["ok"])

        packaged_live = agent.package_agent(
            name="porter_usage",
            target_system_id="bridgebase-alpha-01",
            secret_key="pack-key",
            **self.AUTH,
        )
        self.assertTrue(packaged_live["ok"])
        with patch.object(agent, "scan_target", return_value={"ok": True, "allowed_for_transfer": True, "target_type": "bridgebase_alpha"}):
            with patch("core.agents.bossgate_agent.request.urlopen", side_effect=RuntimeError("network down")):
                failed = agent.transfer_agent(
                    package_file=packaged_live["package_file"],
                    destination="http://bridgebase.local",
                    dry_run=False,
                    **self.AUTH,
                )
        self.assertFalse(failed["ok"])

        assigned = agent.authorization_registry.assign_user_roles("bossforge-owner", "finance-analyst", ["commerce_manager"])
        self.assertTrue(assigned["ok"])
        report = agent.usage_report(limit=10, operator_id="finance-analyst", scope_id="test-scope")
        self.assertTrue(report["ok"])
        self.assertEqual(report["summary"]["total_records"], 2)
        self.assertEqual(report["summary"]["dry_run_count"], 1)
        self.assertEqual(report["summary"]["live_transfer_count"], 1)
        self.assertEqual(report["summary"]["status_counts"]["validated_only"], 1)
        self.assertEqual(report["summary"]["status_counts"]["transfer_failed"], 1)
        self.assertEqual(report["summary"]["success_count"], 1)
        self.assertEqual(report["summary"]["failure_count"], 1)
        self.assertEqual(report["recent_entries"][0]["status"], "validated_only")
        self.assertEqual(report["recent_entries"][1]["status"], "transfer_failed")

    def test_operator_telemetry_flows_include_correlation_ids(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)

        with patch("core.agents.bossgate_agent.discover_transfer_targets", return_value=[]):
            discover = agent.discover_targets(timeout=1, **self.AUTH)
        self.assertTrue(discover["ok"])
        self.assertTrue(discover.get("correlation_id"))

        with patch("core.agents.bossgate_agent.scan_rest_endpoints", return_value={"ok": True, "allowed_for_transfer": True, "target_type": "bridgebase_alpha"}):
            scan = agent.scan_target("http://bridgebase.local", **self.AUTH)
        self.assertTrue(scan["ok"])
        self.assertTrue(scan.get("correlation_id"))

        assigned = agent.authorization_registry.assign_user_roles("bossforge-owner", "finance-analyst", ["commerce_manager"])
        self.assertTrue(assigned["ok"])
        report = agent.usage_report(limit=5, operator_id="finance-analyst", scope_id="test-scope")
        self.assertTrue(report["ok"])
        self.assertTrue(report.get("correlation_id"))

        with patch("core.agents.bossgate_agent.discover_transfer_targets", return_value=[]):
            agent.handle_command(
                {
                    "target": "bossgate",
                    "command": "bossgate_discover_targets",
                    "args": {"timeout": 1, **self.AUTH},
                }
            )
        with patch("core.agents.bossgate_agent.scan_rest_endpoints", return_value={"ok": True, "allowed_for_transfer": True, "target_type": "bridgebase_alpha"}):
            agent.handle_command(
                {
                    "target": "bossgate",
                    "command": "bossgate_scan_target",
                    "args": {"destination": "http://bridgebase.local", **self.AUTH},
                }
            )
        agent.handle_command(
            {
                "target": "bossgate",
                "command": "bossgate_usage_report",
                "args": {"limit": 5, "operator_id": "finance-analyst", "scope_id": "test-scope"},
            }
        )
        events = agent.bus.read_latest_events(limit=6)
        discover_command = next(item for item in events if item["event"] == "command:bossgate_discover_targets")
        scan_command = next(item for item in events if item["event"] == "command:bossgate_scan_target")
        usage_command = next(item for item in events if item["event"] == "command:bossgate_usage_report")
        self.assertTrue(discover_command["data"].get("correlation_id"))
        self.assertTrue(scan_command["data"].get("correlation_id"))
        self.assertTrue(usage_command["data"].get("correlation_id"))

    def test_build_interface_map_command_emits_result(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        discovered = [
            {
                "address": "http://bridgebase.local:8443",
                "node_id": "node-bridge",
                "target_type": "bridgebase_alpha",
                "allowed_for_transfer": True,
            }
        ]
        scanned = {
            "ok": True,
            "allowed_for_transfer": True,
            "target_type": "bridgebase_alpha",
            "base_url": "http://bridgebase.local:8443",
            "endpoints": [{"path": "/api/transfer", "methods": ["post"]}],
            "metadata": {"title": "bridgebase_alpha control plane"},
        }
        with patch("core.agents.bossgate_agent.discover_transfer_targets", return_value=discovered):
            with patch("core.agents.bossgate_agent.scan_rest_endpoints", return_value=scanned):
                agent.handle_command(
                    {
                        "target": "bossgate",
                        "command": "bossgate_build_interface_map",
                        "args": {"destination": "http://bridgebase.local:8443", **self.AUTH},
                    }
                )
        event = agent.bus.read_latest_events(limit=1)[0]
        self.assertEqual(event["event"], "command:bossgate_build_interface_map")
        self.assertTrue(event["data"]["ok"])
        self.assertEqual(event["data"]["target_type"], "bridgebase_alpha")

    def test_generate_connector_skeleton_command_emits_result(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        skeleton = {
            "ok": True,
            "target_type": "bridgebase_alpha",
            "default_access": "read_only",
            "enabled_operations": [{"path": "/health", "methods": ["GET"]}],
            "approval_required_operations": [{"path": "/api/transfer", "methods": ["POST"], "enabled_by_default": False}],
            "skeleton_file": str(Path(self.tmp.name) / "bridgebase-skeleton.json"),
        }
        with patch.object(agent, "generate_connector_skeleton", return_value=skeleton):
            agent.handle_command(
                {
                    "target": "bossgate",
                    "command": "bossgate_generate_connector_skeleton",
                    "args": {"destination": "http://bridgebase.local:8443", **self.AUTH},
                }
            )
        event = agent.bus.read_latest_events(limit=1)[0]
        self.assertEqual(event["event"], "command:bossgate_generate_connector_skeleton")
        self.assertTrue(event["data"]["ok"])
        self.assertEqual(event["data"]["default_access"], "read_only")

    def test_enable_connector_operation_command_emits_approval_request(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        approval = {
            "ok": True,
            "status": "approval_requested",
            "approval_id": "connop-123",
        }
        with patch.object(agent, "enable_connector_operation", return_value=approval):
            agent.handle_command(
                {
                    "target": "bossgate",
                    "command": "bossgate_enable_connector_operation",
                    "args": {
                        "skeleton_file": "state/bridgebase-skeleton.json",
                        "path": "/api/transfer",
                        "methods": ["POST"],
                        **self.AUTH,
                    },
                }
            )
        event = agent.bus.read_latest_events(limit=1)[0]
        self.assertEqual(event["event"], "command:bossgate_enable_connector_operation")
        self.assertTrue(event["data"]["ok"])
        self.assertEqual(event["data"]["status"], "approval_requested")

    def test_license_issue_and_validate_roundtrip_for_commerce_manager(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="licensed_agent",
            endpoint="ollama",
            system_prompt="Licensable agent.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        assigned = agent.authorization_registry.assign_user_roles("bossforge-owner", "finance-analyst", ["commerce_manager"])
        self.assertTrue(assigned["ok"])

        issued = agent.issue_license(
            agent_name="licensed_agent",
            customer_id="acme-labs",
            license_tier="rental",
            expires_in_seconds=3600,
            operator_id="finance-analyst",
            scope_id="billing",
        )
        self.assertTrue(issued["ok"])
        self.assertTrue(issued["correlation_id"])
        license_path = Path(issued["license_file"])
        self.assertTrue(license_path.exists())

        payload = json.loads(license_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["agent_name"], "licensed_agent")
        self.assertEqual(payload["customer_id"], "acme-labs")
        self.assertEqual(payload["license_tier"], "rental")
        self.assertEqual(payload["status"], "active")

        validated = agent.validate_license(
            license_file=str(license_path),
            agent_name="licensed_agent",
            operator_id="finance-analyst",
            scope_id="billing",
        )
        self.assertTrue(validated["ok"])
        self.assertEqual(validated["license_status"], "active")
        self.assertEqual(validated["agent_name"], "licensed_agent")
        self.assertTrue(validated["correlation_id"])

    def test_validate_license_rejects_expired_license(self) -> None:
        agent = BossGateCommandAgent(interval_seconds=1)
        assigned = agent.authorization_registry.assign_user_roles("bossforge-owner", "finance-analyst", ["commerce_manager"])
        self.assertTrue(assigned["ok"])

        license_path = Path(self.tmp.name) / "expired_license.bossgate.json"
        license_path.write_text(
            json.dumps(
                {
                    "license_version": 1,
                    "license_id": "lic-expired-001",
                    "agent_name": "licensed_agent",
                    "customer_id": "acme-labs",
                    "license_tier": "rental",
                    "issuer_node": "bossforgeos-test",
                    "issued_at": int(time.time()) - 7200,
                    "expires_at": int(time.time()) - 3600,
                    "status": "active",
                }
            ),
            encoding="utf-8",
        )

        denied = agent.validate_license(
            license_file=str(license_path),
            agent_name="licensed_agent",
            operator_id="finance-analyst",
            scope_id="billing",
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["reason_codes"], ["license_expired"])

    def test_revoke_license_marks_document_and_validation_denies(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="licensed_agent_revoked",
            endpoint="ollama",
            system_prompt="Licensable agent.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        assigned = agent.authorization_registry.assign_user_roles("bossforge-owner", "finance-analyst", ["commerce_manager"])
        self.assertTrue(assigned["ok"])
        issued = agent.issue_license(
            agent_name="licensed_agent_revoked",
            customer_id="acme-labs",
            license_tier="rental",
            expires_in_seconds=3600,
            operator_id="finance-analyst",
            scope_id="billing",
        )
        self.assertTrue(issued["ok"])

        revoked = agent.revoke_license(
            license_file=issued["license_file"],
            reason="billing default",
            operator_id="finance-analyst",
            scope_id="billing",
        )
        self.assertTrue(revoked["ok"])
        self.assertEqual(revoked["license_status"], "revoked")

        payload = json.loads(Path(issued["license_file"]).read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "revoked")
        self.assertEqual(payload["revocation_reason"], "billing default")

        denied = agent.validate_license(
            license_file=issued["license_file"],
            agent_name="licensed_agent_revoked",
            operator_id="finance-analyst",
            scope_id="billing",
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["reason_codes"], ["license_revoked"])

    def test_remote_debug_open_creates_scoped_time_bound_session(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="support_target",
            endpoint="ollama",
            system_prompt="Support target.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        assigned = agent.authorization_registry.assign_user_roles("bossforge-owner", "support-tech", ["support_engineer"])
        self.assertTrue(assigned["ok"])

        opened = agent.remote_debug_open(
            agent_name="support_target",
            session_scope=["logs.read", "state.inspect"],
            ttl_seconds=600,
            operator_id="support-tech",
            scope_id="incident-42",
        )
        self.assertTrue(opened["ok"])
        self.assertTrue(opened["session_token"])
        self.assertTrue(opened["session_id"])
        self.assertEqual(opened["agent_name"], "support_target")
        self.assertEqual(opened["session_scope"], ["logs.read", "state.inspect"])
        self.assertEqual(opened["status"], "remote_debug_open")
        self.assertGreater(opened["expires_at"], opened["issued_at"])

        sessions_path = agent.remote_debug_sessions_path
        self.assertTrue(sessions_path.exists())
        payload = json.loads(sessions_path.read_text(encoding="utf-8"))
        self.assertIn(opened["session_id"], payload["sessions"])
        stored = payload["sessions"][opened["session_id"]]
        self.assertEqual(stored["agent_name"], "support_target")
        self.assertEqual(stored["session_scope"], ["logs.read", "state.inspect"])
        self.assertEqual(stored["operator_id"], "support-tech")

        events = agent.bus.read_latest_events(limit=6)
        lifecycle = next(item for item in events if item["event"] == "lifecycle:remote_debug_open")
        self.assertEqual(lifecycle["data"]["session_id"], opened["session_id"])
        self.assertEqual(lifecycle["data"]["session_scope"], ["logs.read", "state.inspect"])

    def test_remote_debug_close_marks_session_closed(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="support_target_close",
            endpoint="ollama",
            system_prompt="Support target.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        assigned = agent.authorization_registry.assign_user_roles("bossforge-owner", "support-tech", ["support_engineer"])
        self.assertTrue(assigned["ok"])
        opened = agent.remote_debug_open(
            agent_name="support_target_close",
            session_scope=["logs.read"],
            ttl_seconds=600,
            operator_id="support-tech",
            scope_id="incident-43",
        )
        self.assertTrue(opened["ok"])

        closed = agent.remote_debug_close(
            session_id=opened["session_id"],
            operator_id="support-tech",
            scope_id="incident-43",
        )
        self.assertTrue(closed["ok"])
        self.assertEqual(closed["status"], "remote_debug_closed")
        self.assertEqual(closed["session_id"], opened["session_id"])

        payload = json.loads(agent.remote_debug_sessions_path.read_text(encoding="utf-8"))
        stored = payload["sessions"][opened["session_id"]]
        self.assertEqual(stored["status"], "closed")
        self.assertIn("closed_at", stored)

        transcript_path = agent.remote_debug_transcripts_path
        self.assertTrue(transcript_path.exists())
        transcript_lines = [
            json.loads(line)
            for line in transcript_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(transcript_lines), 2)
        opened_entry, closed_entry = transcript_lines
        self.assertEqual(opened_entry["event"], "remote_debug_open")
        self.assertEqual(closed_entry["event"], "remote_debug_close")
        self.assertEqual(opened_entry["session_id"], opened["session_id"])
        self.assertEqual(closed_entry["session_id"], opened["session_id"])
        self.assertEqual(opened_entry["correlation_id"], opened["correlation_id"])
        self.assertEqual(closed_entry["correlation_id"], closed["correlation_id"])
        self.assertEqual(closed_entry["status"], "closed")
        self.assertEqual(closed_entry["agent_name"], "support_target_close")

    def test_remote_debug_emergency_revoke_force_closes_agent_sessions(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="support_target_revoke",
            endpoint="ollama",
            system_prompt="Support target.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        assigned = agent.authorization_registry.assign_user_roles("bossforge-owner", "support-tech", ["support_engineer"])
        self.assertTrue(assigned["ok"])
        first = agent.remote_debug_open(
            agent_name="support_target_revoke",
            session_scope=["logs.read"],
            ttl_seconds=600,
            operator_id="support-tech",
            scope_id="incident-44",
        )
        second = agent.remote_debug_open(
            agent_name="support_target_revoke",
            session_scope=["state.inspect"],
            ttl_seconds=600,
            operator_id="support-tech",
            scope_id="incident-44",
        )
        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])

        revoked = agent.remote_debug_close(
            agent_name="support_target_revoke",
            emergency_revoke=True,
            operator_id="support-tech",
            scope_id="incident-44",
        )
        self.assertTrue(revoked["ok"])
        self.assertEqual(revoked["status"], "remote_debug_emergency_revoked")
        self.assertEqual(sorted(revoked["closed_session_ids"]), sorted([first["session_id"], second["session_id"]]))

        payload = json.loads(agent.remote_debug_sessions_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["sessions"][first["session_id"]]["status"], "revoked")
        self.assertEqual(payload["sessions"][second["session_id"]]["status"], "revoked")

        transcript_lines = [
            json.loads(line)
            for line in agent.remote_debug_transcripts_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        revoked_entries = [entry for entry in transcript_lines if entry["event"] == "remote_debug_close" and entry["status"] == "revoked"]
        self.assertEqual(len(revoked_entries), 2)
        self.assertEqual(
            sorted(entry["session_id"] for entry in revoked_entries),
            sorted([first["session_id"], second["session_id"]]),
        )
        self.assertTrue(all(entry["correlation_id"] == revoked["correlation_id"] for entry in revoked_entries))
        self.assertTrue(all(entry["emergency_revoke"] for entry in revoked_entries))

    def test_remote_debug_command_rejects_expired_session_token(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="support_target_expired",
            endpoint="ollama",
            system_prompt="Support target.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        assigned = agent.authorization_registry.assign_user_roles("bossforge-owner", "support-tech", ["support_engineer"])
        self.assertTrue(assigned["ok"])
        opened = agent.remote_debug_open(
            agent_name="support_target_expired",
            session_scope=["logs.read"],
            ttl_seconds=600,
            operator_id="support-tech",
            scope_id="incident-45",
        )
        self.assertTrue(opened["ok"])

        payload = json.loads(agent.remote_debug_sessions_path.read_text(encoding="utf-8"))
        payload["sessions"][opened["session_id"]]["expires_at"] = int(time.time()) - 1
        agent.remote_debug_sessions_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        denied = agent.remote_debug_command(
            session_id=opened["session_id"],
            session_token=opened["session_token"],
            command_name="tail_logs",
            requested_scope="logs.read",
            operator_id="support-tech",
            scope_id="incident-45",
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["reason_codes"], ["remote_debug_session_expired"])

    def test_remote_debug_command_rejects_out_of_scope_command(self) -> None:
        gateway = ModelGatewayAgent(interval_seconds=1)
        created = gateway.create_agent_profile(
            name="support_target_scope",
            endpoint="ollama",
            system_prompt="Support target.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])

        agent = BossGateCommandAgent(interval_seconds=1)
        assigned = agent.authorization_registry.assign_user_roles("bossforge-owner", "support-tech", ["support_engineer"])
        self.assertTrue(assigned["ok"])
        opened = agent.remote_debug_open(
            agent_name="support_target_scope",
            session_scope=["logs.read"],
            ttl_seconds=600,
            operator_id="support-tech",
            scope_id="incident-46",
        )
        self.assertTrue(opened["ok"])

        denied = agent.remote_debug_command(
            session_id=opened["session_id"],
            session_token=opened["session_token"],
            command_name="inspect_state",
            requested_scope="state.inspect",
            operator_id="support-tech",
            scope_id="incident-46",
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["reason_codes"], ["remote_debug_scope_denied"])


if __name__ == "__main__":
    unittest.main()
