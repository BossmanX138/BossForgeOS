import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.agents.model_gateway_agent import ModelGatewayAgent


class ModelGatewayAgentTests(unittest.TestCase):
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

    def test_default_endpoints_written(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        self.assertIn("ollama", agent.endpoints)
        self.assertTrue(agent.config_path.exists())

    def test_list_endpoints_command_emits_event(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        agent.handle_command({"target": "model_gateway", "command": "list_endpoints", "args": {}})

        events = agent.bus.read_latest_events(limit=1)
        self.assertEqual(events[0]["source"], "model_gateway")
        self.assertEqual(events[0]["event"], "command:list_endpoints")
        self.assertTrue(events[0]["data"]["ok"])

    def test_refactor_routes_to_invoke(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        with patch.object(agent, "_invoke_endpoint", return_value={"ok": True, "text": "refactored"}) as mocked:
            agent.handle_command(
                {
                    "target": "model_gateway",
                    "command": "refactor_code",
                    "args": {
                        "endpoint": "ollama",
                        "language": "python",
                        "instructions": "make it cleaner",
                        "code": "print('x')",
                    },
                }
            )

            self.assertTrue(mocked.called)
            kwargs = mocked.call_args.args
            self.assertEqual(kwargs[0], "ollama")
            self.assertIn("make it cleaner", kwargs[1])

    def test_serve_and_stop_server_commands(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)

        with patch("core.agents.model_gateway_agent.subprocess.Popen") as popen:
            proc = popen.return_value
            proc.pid = 4321
            proc.poll.return_value = None

            agent.handle_command(
                {
                    "target": "model_gateway",
                    "command": "serve_model",
                    "args": {"server": "vllm", "model": "Qwen2", "host": "127.0.0.1", "port": 8000},
                }
            )

            self.assertIn("vllm", agent.servers)

            agent.handle_command(
                {
                    "target": "model_gateway",
                    "command": "stop_model_server",
                    "args": {"server": "vllm"},
                }
            )

            self.assertTrue(proc.terminate.called)

    def test_stop_all_servers(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)

        proc = Mock()
        proc.pid = 77
        proc.poll.return_value = None
        proc.wait.return_value = None
        agent.servers["ollama"] = proc

        result = agent._stop_all_servers()
        self.assertTrue(result["ok"])
        self.assertTrue(proc.terminate.called)

    def test_create_and_run_model_agent_profile(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)

        create = agent._create_agent_profile(
            name="refactorer",
            endpoint="ollama",
            system_prompt="You refactor code.",
            temperature=0.1,
            max_tokens=800,
        )
        self.assertTrue(create["ok"])
        self.assertIn("refactorer", agent.agent_profiles)
        self.assertTrue((agent.bus.state / "model_agent_refactorer.json").exists())

        with patch.object(agent, "_invoke_endpoint", return_value={"ok": True, "text": "done"}) as mocked:
            run = agent._run_agent_profile(name="refactorer", task="Refactor this function")
            self.assertTrue(run["ok"])
            self.assertEqual(run["agent"], "refactorer")
            self.assertTrue(mocked.called)
            self.assertTrue((agent.bus.state / "model_agent_refactorer.json").exists())

    def test_handle_command_create_delete_agent(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)

        agent.handle_command(
            {
                "target": "model_gateway",
                "command": "create_agent",
                "args": {"name": "planner", "endpoint": "ollama", "system": "Plan things."},
            }
        )
        self.assertIn("planner", agent.agent_profiles)

        agent.handle_command(
            {
                "target": "model_gateway",
                "command": "delete_agent",
                "args": {"name": "planner"},
            }
        )
        self.assertNotIn("planner", agent.agent_profiles)

    def test_mcp_server_registry_roundtrip(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)

        created = agent.set_mcp_server(
            name="filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "."],
            env={"LOG_LEVEL": "info"},
        )
        self.assertTrue(created["ok"])
        self.assertIn("filesystem", agent.mcp_servers)

        removed = agent.remove_mcp_server("filesystem")
        self.assertTrue(removed["ok"])
        self.assertNotIn("filesystem", agent.mcp_servers)

    def test_create_agent_with_tools(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        agent.set_mcp_server(name="filesystem", command="fs-mcp")

        created = agent.create_agent_profile(
            name="toolsmith",
            endpoint="ollama",
            system_prompt="Use tools when needed.",
            temperature=0.2,
            max_tokens=900,
            tools=["filesystem"],
        )
        self.assertTrue(created["ok"])
        self.assertEqual(agent.agent_profiles["toolsmith"]["tools"], ["filesystem"])

    def test_create_agent_with_state_machine(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        machine = {
            "initial_state": "Idle",
            "states": {
                "Idle": {"on_task": "Executing"},
                "Executing": {"on_success": "Completed", "on_error": "Blocked"},
                "Completed": {"on_task": "Executing"},
                "Blocked": {"on_retry": "Executing", "on_abort": "Idle"},
            },
        }

        created = agent.create_agent_profile(
            name="stateful",
            endpoint="ollama",
            system_prompt="Handle work with explicit state transitions.",
            temperature=0.2,
            max_tokens=700,
            tools=[],
            state_machine=machine,
        )
        self.assertTrue(created["ok"])
        self.assertIn("state_machine", agent.agent_profiles["stateful"])
        self.assertEqual(agent.agent_profiles["stateful"]["state_machine"].get("initial_state"), "Idle")

    def test_bossgate_enabled_profile_forces_llm(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="traveler",
            endpoint="ollama",
            system_prompt="Travel-capable agent.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
            agent_class="core",
            has_llm=False,
            bossgate_enabled=True,
        )
        self.assertTrue(created["ok"])
        profile = agent.agent_profiles["traveler"]
        self.assertTrue(profile["bossgate_enabled"])
        self.assertTrue(profile["has_llm"])

    def test_create_agent_can_disable_encryption(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="plain_profile",
            endpoint="ollama",
            system_prompt="Local non-encrypted profile.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
            encrypt_profile=False,
            bossgate_enabled=True,
        )
        self.assertTrue(created["ok"])
        profile = agent.agent_profiles["plain_profile"]
        self.assertFalse(profile["encrypt_profile"])
        self.assertFalse(profile["bossgate_enabled"])

    def test_export_import_json_config(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        agent.set_mcp_server(name="filesystem", command="fs-mcp")
        agent.create_agent_profile(
            name="planner",
            endpoint="ollama",
            system_prompt="Plan tasks.",
            temperature=0.2,
            max_tokens=500,
            tools=["filesystem"],
        )

        export_path = Path(self.tmp.name) / "model_config.json"
        exported = agent.export_config(str(export_path))
        self.assertTrue(exported["ok"])
        self.assertTrue(export_path.exists())

        imported_agent = ModelGatewayAgent(interval_seconds=1)
        imported = imported_agent.import_config(str(export_path), merge=False)
        self.assertTrue(imported["ok"])
        self.assertIn("planner", imported_agent.agent_profiles)
        self.assertIn("filesystem", imported_agent.mcp_servers)

    def test_export_import_yaml_config(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        agent.create_agent_profile(
            name="scribe",
            endpoint="ollama",
            system_prompt="Write docs.",
            temperature=0.1,
            max_tokens=700,
            tools=[],
        )

        export_path = Path(self.tmp.name) / "model_config.yaml"
        exported = agent.export_config(str(export_path), format_hint="yaml")
        self.assertTrue(exported["ok"])
        self.assertTrue(export_path.exists())

        imported_agent = ModelGatewayAgent(interval_seconds=1)
        imported = imported_agent.import_config(str(export_path), format_hint="yaml", merge=False)
        self.assertTrue(imported["ok"])
        self.assertIn("scribe", imported_agent.agent_profiles)

    def test_discover_travel_targets_command(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        with patch("core.agents.model_gateway_agent.discover_transfer_targets", return_value=[{"address": "10.0.0.5", "allowed_for_transfer": True}]):
            result = agent.discover_travel_targets(timeout=3, assistance_only=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["timeout"], 3)
        self.assertTrue(result["assistance_only"])
        self.assertEqual(len(result["targets"]), 1)

    def test_set_and_list_agent_assistance_requests(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        agent.create_agent_profile(
            name="helper",
            endpoint="ollama",
            system_prompt="Help other agents.",
            temperature=0.2,
            max_tokens=500,
            tools=[],
        )
        set_result = agent.set_agent_assistance_request(name="helper", requested=True, reason="Need debugging backup")
        self.assertTrue(set_result["ok"])
        self.assertTrue(set_result["assistance_requested"])

        listed = agent.list_assistance_requests()
        self.assertTrue(listed["ok"])
        self.assertIn("helper", listed["requests"])

    def test_assistance_requests_persist_between_instances(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        agent.create_agent_profile(
            name="watcher",
            endpoint="ollama",
            system_prompt="Watch and assist.",
            temperature=0.2,
            max_tokens=500,
            tools=[],
        )
        set_result = agent.set_agent_assistance_request(name="watcher", requested=True, reason="Escalation requested")
        self.assertTrue(set_result["ok"])

        fresh_agent = ModelGatewayAgent(interval_seconds=1)
        listed = fresh_agent.list_assistance_requests()
        self.assertTrue(listed["ok"])
        self.assertIn("watcher", listed["requests"])
        self.assertTrue(listed["requests"]["watcher"]["requested"])

    def test_created_agent_records_owner_node(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="cartographer",
            endpoint="ollama",
            system_prompt="Track locations.",
            temperature=0.2,
            max_tokens=500,
            tools=[],
        )
        self.assertTrue(created["ok"])
        profile = agent.agent_profiles["cartographer"]
        self.assertEqual(profile["created_by_node"], agent.node_id)
        self.assertEqual(profile["current_node"], agent.node_id)

    def test_owned_agent_locations_refresh_uses_discovery(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        agent.create_agent_profile(
            name="pathfinder",
            endpoint="ollama",
            system_prompt="Navigate.",
            temperature=0.2,
            max_tokens=500,
            tools=[],
        )
        discovered = [
            {
                "address": "10.1.2.3",
                "node_id": "remote-node-1",
                "agent_name": "pathfinder",
                "agent_class": "prime",
                "created_by_node": agent.node_id,
                "current_node": "remote-node-1",
                "target_type": "bossgate_connector",
                "allowed_for_transfer": True,
                "assistance_requested": True,
                "assistance_reason": "Need help",
            }
        ]
        with patch("core.agents.model_gateway_agent.discover_transfer_targets", return_value=discovered):
            result = agent.list_owned_agent_locations(refresh=True)

        self.assertTrue(result["ok"])
        self.assertIn("pathfinder", result["agents"])
        entry = result["agents"]["pathfinder"]
        self.assertEqual(entry["node_id"], "remote-node-1")
        self.assertEqual(entry["source"], "beacon")

    def test_validate_transfer_target_command(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        mock_result = {
            "ok": False,
            "allowed_for_transfer": False,
            "target_type": "unknown",
            "reason": "Destination rejected",
            "base_url": "http://example.com",
            "endpoints": [],
            "metadata": {},
        }
        with patch("core.agents.model_gateway_agent.scan_rest_endpoints", return_value=mock_result):
            result = agent.validate_transfer_target("example.com")
        self.assertFalse(result["ok"])
        self.assertFalse(result["allowed_for_transfer"])
        self.assertEqual(result["destination"], "example.com")


if __name__ == "__main__":
    unittest.main()
