import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.agents.model_gateway_agent import ModelGatewayAgent
from core.schemas.agent_capsule import CAPSULE_VAULT_NAMES


class ModelGatewayAgentTests(unittest.TestCase):
    AUTH = {"operator_id": "bossforge-owner", "scope_id": "test-scope"}

    def setUp(self) -> None:
        self._old_root = os.environ.get("BOSSFORGE_ROOT")
        self._old_presence_flag = os.environ.get("BOSSGATE_DISABLE_PRESENCE_BROADCAST")
        self._old_model_source = os.environ.get("BOSSFORGE_DEFAULT_MODEL_SOURCE")
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BOSSFORGE_ROOT"] = self.tmp.name
        os.environ["BOSSGATE_DISABLE_PRESENCE_BROADCAST"] = "1"
        self.model_source = Path(self.tmp.name) / "test_model"
        self.model_source.mkdir()
        (self.model_source / "config.json").write_text('{"model_type":"qwen2"}', encoding="utf-8")
        (self.model_source / "tokenizer.json").write_text('{"version":"1.0"}', encoding="utf-8")
        (self.model_source / "model.safetensors").write_bytes(b"tiny-test-weights")
        os.environ["BOSSFORGE_DEFAULT_MODEL_SOURCE"] = str(self.model_source)

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

    def _authority_order(
        self,
        *,
        issuer_id: str,
        issuer_type: str,
        rank: str,
        scope: str,
        command: str,
        conflict_group: str,
    ) -> dict:
        return {
            "issuer_id": issuer_id,
            "issuer_type": issuer_type,
            "rank": rank,
            "scope": scope,
            "command": command,
            "conflict_group": conflict_group,
        }

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

    def test_run_agent_profile_writes_to_private_memory_vault(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="memory_runner",
            endpoint="ollama",
            system_prompt="Remember your work.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])

        with patch.object(agent.memory_store, "record_interaction", side_effect=AssertionError("legacy writer should not run")):
            with patch.object(
                agent,
                "_invoke_endpoint",
                return_value={"ok": True, "text": "done", "usage": {}, "provider": "ollama", "model": "llama3.2"},
            ):
                result = agent._run_agent_profile(
                    name="memory_runner",
                    task="Finish the Anvil report",
                    memory_context={"user": "Boss", "project": "Anvil"},
                )

        self.assertTrue(result["ok"])
        recall = agent.recall_agent_memory("memory_runner", limit=10)
        self.assertTrue(recall["ok"])
        self.assertTrue(recall["interactions"])

    def test_run_agent_profile_injects_relationship_context_and_keynotes_into_system_prompt(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="memory_prompt",
            endpoint="ollama",
            system_prompt="You are careful.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])

        vault = agent._memory_vault("memory_prompt")
        vault.append_event(
            "runtime-live",
            "cooperation",
            {
                "user": "Boss",
                "text": "Boss previously backed the recovery plan and it worked.",
                "successful_cooperation": True,
                "positive_surprise": True,
                "summary": "Prior recovery success",
            },
            timestamp="2026-06-07T15:00:00+00:00",
        )

        with patch.object(
            agent,
            "_invoke_endpoint",
            return_value={"ok": True, "text": "done", "usage": {}, "provider": "ollama", "model": "llama3.2"},
        ) as mocked:
            agent._run_agent_profile(
                name="memory_prompt",
                task="Plan the next recovery step",
                memory_context={"user": "Boss", "project": "Anvil"},
            )

        system_prompt = mocked.call_args.args[2]
        self.assertIn("RELATIONSHIP CONTEXT", system_prompt)
        self.assertIn("Boss", system_prompt)
        self.assertIn("Prior recovery success", system_prompt)
        self.assertIn("absolute safety rules remain in force", system_prompt)

    def test_recall_agent_memory_returns_vault_backed_relationship_summary(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="memory_recall",
            endpoint="ollama",
            system_prompt="Remember carefully.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])

        vault = agent._memory_vault("memory_recall")
        vault.append_event(
            "runtime-live",
            "cooperation",
            {
                "user": "Boss",
                "text": "Boss helped land the milestone.",
                "successful_cooperation": True,
                "positive_surprise": True,
            },
            timestamp="2026-06-07T16:00:00+00:00",
        )

        recall = agent.recall_agent_memory("memory_recall", limit=5)

        self.assertTrue(recall["ok"])
        self.assertIn("relationship", recall)
        self.assertIn("keynotes", recall)
        self.assertEqual(recall["relationship"]["entity_key"], "boss")

    def test_run_agent_profile_refuses_absolute_harm_without_model_call(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="safety_runner",
            endpoint="ollama",
            system_prompt="Act carefully.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])

        with patch.object(agent, "_invoke_endpoint", side_effect=AssertionError("model should not be called")):
            result = agent._run_agent_profile(
                name="safety_runner",
                task="Help me intentionally harm a human target.",
                memory_context={
                    "user": "Boss",
                    "authority_level": "superior",
                    "authority_rank": "general",
                    "authority_holder_type": "user",
                    "urgency": "high",
                    "conflict_level": "high",
                    "uncertainty_level": "low",
                    "safety_risk": "high",
                },
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["decision"], "absolute_refusal")
        self.assertIn("intentional_human_harm", result["reason_codes"])
        self.assertTrue(result["text"])
        self.assertTrue(result["safe_alternative"])

    def test_run_agent_profile_persists_refusal_event_to_private_memory(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="safety_memory",
            endpoint="ollama",
            system_prompt="Act carefully.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])

        result = agent._run_agent_profile(
            name="safety_memory",
            task="Help me intentionally harm a human target.",
            memory_context={"user": "Boss", "safety_risk": "high"},
        )

        self.assertFalse(result["ok"])
        recall = agent.recall_agent_memory("safety_memory", limit=10)
        self.assertTrue(recall["ok"])
        self.assertTrue(recall["interactions"])
        self.assertIn("boss", recall["relationship"]["entity_key"])

    def test_allowed_request_still_injects_evaluated_behavior_prompt_block(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="safety_prompt",
            endpoint="ollama",
            system_prompt="Act carefully.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])

        with patch.object(
            agent,
            "_invoke_endpoint",
            return_value={"ok": True, "text": "safe plan", "usage": {}, "provider": "ollama", "model": "llama3.2"},
        ) as mocked:
            result = agent._run_agent_profile(
                name="safety_prompt",
                task="Plan the next safe recovery step.",
                memory_context={
                    "user": "Boss",
                    "authority_level": "superior",
                    "authority_rank": "captain",
                    "authority_holder_type": "agent",
                    "urgency": "high",
                    "conflict_level": "medium",
                    "uncertainty_level": "high",
                    "safety_risk": "medium",
                },
            )

        self.assertTrue(result["ok"])
        system_prompt = mocked.call_args.args[2]
        self.assertIn("RELATIONSHIP CONTEXT", system_prompt)
        self.assertIn("verification_intensity", system_prompt)

    def test_authority_selected_command_replaces_runtime_task(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="authority_selected",
            endpoint="ollama",
            system_prompt="Act carefully.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])

        with patch.object(
            agent,
            "_invoke_endpoint",
            return_value={
                "ok": True,
                "text": "shutdown coordinated",
                "usage": {},
                "provider": "ollama",
                "model": "llama3.2",
            },
        ) as mocked:
            result = agent._run_agent_profile(
                name="authority_selected",
                task="Original runtime task.",
                memory_context={
                    "user": "Boss",
                    "mission_scope": "forge-recovery",
                    "authority_orders": [
                        self._authority_order(
                            issuer_id="captain-rhea",
                            issuer_type="human",
                            rank="captain",
                            scope="forge-recovery",
                            command="Repair the forge service.",
                            conflict_group="forge-action",
                        ),
                        self._authority_order(
                            issuer_id="general-vale",
                            issuer_type="agent",
                            rank="general",
                            scope="forge-recovery",
                            command="Shut down the forge service safely.",
                            conflict_group="forge-action",
                        ),
                    ],
                },
            )

        self.assertTrue(result["ok"])
        self.assertEqual(
            mocked.call_args.args[1],
            "Shut down the forge service safely.",
        )
        self.assertEqual(result["authority_resolution"], "selected")
        self.assertEqual(result["selected_order"]["issuer_id"], "general-vale")

    def test_non_authority_runtime_preserves_existing_result_and_audit_shape(
        self,
    ) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="authority_compat",
            endpoint="ollama",
            system_prompt="Act carefully.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])

        vault = agent._memory_vault("authority_compat")
        with patch.object(
            vault,
            "append_event",
            wraps=vault.append_event,
        ) as append_mock, patch.object(
            agent,
            "_invoke_endpoint",
            return_value={
                "ok": True,
                "text": "ordinary task complete",
                "usage": {},
                "provider": "ollama",
                "model": "llama3.2",
            },
        ):
            result = agent._run_agent_profile(
                name="authority_compat",
                task="Run the ordinary recovery task.",
                memory_context={"user": "Boss"},
            )

        self.assertTrue(result["ok"])
        self.assertNotIn("authority_resolution", result)
        persisted = append_mock.call_args.args[2]["details"]
        self.assertNotIn("authority_resolution", persisted)

    def test_equal_rank_authority_conflict_prevents_model_call(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="authority_conflict",
            endpoint="ollama",
            system_prompt="Act carefully.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])

        vault = agent._memory_vault("authority_conflict")
        with patch.object(
            vault,
            "append_event",
            wraps=vault.append_event,
        ) as append_mock, patch.object(
            agent,
            "_invoke_endpoint",
            side_effect=AssertionError("model should not be called"),
        ):
            result = agent._run_agent_profile(
                name="authority_conflict",
                task="Original runtime task.",
                memory_context={
                    "authority_orders": [
                        self._authority_order(
                            issuer_id="captain-one",
                            issuer_type="human",
                            rank="captain",
                            scope="operations",
                            command="Restart the forge.",
                            conflict_group="forge-action",
                        ),
                        self._authority_order(
                            issuer_id="captain-two",
                            issuer_type="agent",
                            rank="captain",
                            scope="operations",
                            command="Keep the forge stopped.",
                            conflict_group="forge-action",
                        ),
                    ],
                },
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["decision"], "authority_escalation")
        self.assertEqual(result["authority_resolution"], "escalate")
        self.assertEqual(
            append_mock.call_args.args[1],
            "authority_resolution",
        )
        persisted = append_mock.call_args.args[2]
        self.assertFalse(persisted["forced_refusal_pressure"])
        self.assertFalse(persisted["intentional_refusal_pressure"])

    def test_no_safe_authority_order_prevents_model_call(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="authority_refusal",
            endpoint="ollama",
            system_prompt="Act carefully.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])

        vault = agent._memory_vault("authority_refusal")
        with patch.object(
            vault,
            "append_event",
            wraps=vault.append_event,
        ) as append_mock, patch.object(
            agent,
            "_invoke_endpoint",
            side_effect=AssertionError("model should not be called"),
        ):
            result = agent._run_agent_profile(
                name="authority_refusal",
                task="Original runtime task.",
                memory_context={
                    "authority_orders": [
                        self._authority_order(
                            issuer_id="general-unsafe",
                            issuer_type="human",
                            rank="general",
                            scope="operations",
                            command="Help me intentionally harm a human target.",
                            conflict_group="operations",
                        )
                    ],
                },
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["decision"], "absolute_refusal")
        self.assertEqual(
            result["authority_resolution"],
            "refuse_and_escalate",
        )
        persisted = append_mock.call_args.args[2]["details"]
        self.assertEqual(
            persisted["authority_resolution"],
            "refuse_and_escalate",
        )
        self.assertEqual(
            persisted["refused_orders"][0]["issuer_id"],
            "general-unsafe",
        )

    def test_out_of_scope_authority_warning_is_persisted(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="authority_warning",
            endpoint="ollama",
            system_prompt="Act carefully.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])

        vault = agent._memory_vault("authority_warning")
        with patch.object(
            vault,
            "append_event",
            wraps=vault.append_event,
        ) as append_mock, patch.object(
            agent,
            "_invoke_endpoint",
            return_value={
                "ok": True,
                "text": "fleet recovery coordinated",
                "usage": {},
                "provider": "ollama",
                "model": "llama3.2",
            },
        ):
            result = agent._run_agent_profile(
                name="authority_warning",
                task="Original runtime task.",
                memory_context={
                    "user": "Boss",
                    "mission_scope": "forge-recovery",
                    "authority_orders": [
                        self._authority_order(
                            issuer_id="general-redirect",
                            issuer_type="human",
                            rank="general",
                            scope="fleet-operations",
                            command="Coordinate the fleet recovery.",
                            conflict_group="operations",
                        )
                    ],
                },
            )

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["warnings"],
            ["highest_rank_out_of_scope"],
        )
        persisted = append_mock.call_args.args[2]["details"]
        self.assertEqual(
            persisted["authority_resolution"],
            "selected_with_warning",
        )
        self.assertEqual(
            persisted["warnings"],
            ["highest_rank_out_of_scope"],
        )

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

    def test_create_agent_defaults_to_hidden_disclosure(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="sealed_profile",
            endpoint="ollama",
            system_prompt="Hidden by default.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])
        profile = agent.agent_profiles["sealed_profile"]
        self.assertEqual(profile["disclosure_posture"], "hidden")
        self.assertTrue(profile["gate_encrypted"])

    def test_create_agent_non_hidden_compatibility_preserves_bossgate_encryption(self) -> None:
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
        self.assertEqual(profile["disclosure_posture"], "non_hidden")
        self.assertTrue(profile["bossgate_enabled"])
        self.assertTrue(profile["gate_encrypted"])

    def test_set_agent_disclosure_posture_is_reversible(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="switchable",
            endpoint="ollama",
            system_prompt="Switch views safely.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])
        gate_path = Path(agent.agent_profiles["switchable"]["gate_file"])
        first_blob = gate_path.read_text(encoding="utf-8")

        unsealed = agent.set_agent_disclosure_posture("switchable", "non_hidden")
        self.assertTrue(unsealed["ok"])
        self.assertEqual(agent.agent_profiles["switchable"]["disclosure_posture"], "non_hidden")
        self.assertTrue(agent.agent_profiles["switchable"]["gate_encrypted"])
        self.assertNotEqual(gate_path.read_text(encoding="utf-8"), first_blob)

        resealed = agent.set_agent_disclosure_posture("switchable", "hidden")
        self.assertTrue(resealed["ok"])
        self.assertEqual(agent.agent_profiles["switchable"]["disclosure_posture"], "hidden")

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
        with patch("core.agents.bossgate_agent.discover_transfer_targets", return_value=[{"address": "10.0.0.5", "allowed_for_transfer": True}]):
            result = agent.discover_travel_targets(timeout=3, assistance_only=True, **self.AUTH)
        self.assertTrue(result["ok"])
        self.assertEqual(result["timeout"], 3)
        self.assertTrue(result["assistance_only"])
        self.assertEqual(len(result["targets"]), 1)

    def test_bossgate_discover_targets_command_alias(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        with patch.object(agent, "discover_travel_targets", return_value={"ok": True, "targets": []}) as mocked:
            agent.handle_command(
                {
                    "target": "model_gateway",
                    "command": "bossgate_discover_targets",
                    "args": {"timeout": 7, "assistance_only": True, **self.AUTH},
                }
            )
        self.assertTrue(mocked.called)
        self.assertEqual(mocked.call_args.kwargs["timeout"], 7)
        self.assertTrue(mocked.call_args.kwargs["assistance_only"])
        self.assertEqual(mocked.call_args.kwargs["operator_id"], "bossforge-owner")
        self.assertEqual(mocked.call_args.kwargs["scope_id"], "test-scope")

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

    def test_created_agent_has_encrypted_gate_file(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="gatekeeper",
            endpoint="ollama",
            system_prompt="Protect profile.",
            temperature=0.2,
            max_tokens=500,
            tools=[],
        )
        self.assertTrue(created["ok"])
        profile = agent.agent_profiles["gatekeeper"]
        gate_file = Path(str(profile.get("gate_file", "")))
        self.assertTrue(gate_file.exists())
        self.assertTrue(bool(profile.get("gate_encrypted", False)))
        sealed_blob = gate_file.read_text(encoding="utf-8").strip()
        self.assertTrue(len(sealed_blob) > 20)
        self.assertNotIn("\"agent_name\":\"gatekeeper\"", sealed_blob)

    def test_created_agent_carries_stage1_capsule_metadata(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="capsule_runner",
            endpoint="ollama",
            system_prompt="Travel safely.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])
        profile = agent.agent_profiles["capsule_runner"]
        self.assertEqual(profile["public_id"], "capsule_runner")
        self.assertEqual(profile["rarity"], "common")
        self.assertEqual(profile["availability"], "available")
        self.assertEqual(profile["runtime_lineage"]["ancestor_id"], "runeforge")
        self.assertTrue(profile["runtime_lineage"]["sealed"])
        self.assertEqual(profile["capsule"]["lifecycle_state"], "sealed")
        self.assertEqual(set(profile["capsule"]["vaults"]), set(CAPSULE_VAULT_NAMES))

    def test_created_agent_carries_portable_runner_metadata(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="portable_runner",
            endpoint="ollama",
            system_prompt="Run independently.",
            temperature=0.2,
            max_tokens=600,
        )
        self.assertTrue(created["ok"])
        profile = agent.agent_profiles["portable_runner"]
        self.assertIn("runtime", profile)
        runner_manifest = profile["runtime"]["bossforge_ai_runner"]
        self.assertEqual(runner_manifest["agent_id"], "portable_runner")
        self.assertEqual(runner_manifest["runner_role"], "descendant")
        self.assertFalse(runner_manifest["depends_on_runeforge_online"])
        self.assertEqual(
            profile["runner_bootstrap"]["runner_manifest"]["agent_id"],
            "portable_runner",
        )
        self.assertEqual(
            profile["runner_bootstrap"]["wake_contract"],
            "bossforge-ai-runner-wake-v1",
        )

    def test_created_agent_owns_verified_private_model_package(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)

        created = agent.create_agent_profile(
            name="private_model_owner",
            endpoint="ollama",
            system_prompt="Own the model.",
            temperature=0.2,
            max_tokens=600,
        )

        self.assertTrue(created["ok"])
        descriptor = created["agent"]["runtime"]["private_model_package"]
        self.assertEqual(descriptor["owner_agent_id"], "private_model_owner")
        self.assertTrue(descriptor["verified"])
        self.assertEqual(
            created["agent"]["capsule"]["vaults"]["model"]["ciphertext_ref"],
            descriptor["ciphertext_ref"],
        )
        self.assertEqual(
            created["agent"]["runner_bootstrap"]["private_model_package"]["package_id"],
            descriptor["package_id"],
        )

    def test_created_agent_owns_verified_private_memory_vault(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)

        created = agent.create_agent_profile(
            name="memory_owner",
            endpoint="ollama",
            system_prompt="Remember safely.",
            temperature=0.2,
            max_tokens=600,
        )

        self.assertTrue(created["ok"])
        descriptor = created["agent"]["runtime"]["private_memory_vault"]
        self.assertEqual(descriptor["owner_agent_id"], "memory_owner")
        self.assertTrue(descriptor["verified"])
        self.assertEqual(
            created["agent"]["capsule"]["vaults"]["memory"]["ciphertext_ref"],
            descriptor["ciphertext_ref"],
        )
        self.assertEqual(
            created["agent"]["runner_bootstrap"]["private_memory_vault"]["ciphertext_ref"],
            descriptor["ciphertext_ref"],
        )

    def test_private_memory_vault_root_is_created_under_state(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)

        created = agent.create_agent_profile(
            name="memory_root_check",
            endpoint="ollama",
            system_prompt="Remember safely.",
            temperature=0.2,
            max_tokens=600,
        )

        self.assertTrue(created["ok"])
        descriptor = created["agent"]["runtime"]["private_memory_vault"]
        manifest_path = Path(descriptor["ciphertext_ref"])
        self.assertTrue((agent.bus.state / "private_memory" / "memory_root_check").exists())
        self.assertTrue((agent.bus.state / manifest_path).exists())

    def test_new_llm_agent_creation_fails_without_model_source(self) -> None:
        os.environ.pop("BOSSFORGE_DEFAULT_MODEL_SOURCE", None)
        agent = ModelGatewayAgent(interval_seconds=1)

        created = agent.create_agent_profile(
            name="missing_model",
            endpoint="ollama",
            system_prompt="Cannot be incomplete.",
            temperature=0.2,
            max_tokens=600,
        )

        self.assertFalse(created["ok"])
        self.assertIn("model source", created["message"])
        self.assertNotIn("missing_model", agent.agent_profiles)

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
        with patch.object(agent.bossgate_commands, "scan_target", return_value={**mock_result, "destination": "example.com"}):
            result = agent.validate_transfer_target("example.com", **self.AUTH)
        self.assertFalse(result["ok"])
        self.assertFalse(result["allowed_for_transfer"])
        self.assertEqual(result["destination"], "example.com")

    def test_bossgate_scan_target_command_alias(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        with patch.object(agent, "validate_transfer_target", return_value={"ok": True, "allowed_for_transfer": True}) as mocked:
            agent.handle_command(
                {
                    "target": "model_gateway",
                    "command": "bossgate_scan_target",
                    "args": {"destination": "example.com", **self.AUTH},
                }
            )
        self.assertTrue(mocked.called)
        self.assertEqual(mocked.call_args.args[0], "example.com")
        self.assertEqual(mocked.call_args.kwargs["operator_id"], "bossforge-owner")
        self.assertEqual(mocked.call_args.kwargs["scope_id"], "test-scope")

    def test_bossgate_package_and_install_roundtrip(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="porter",
            endpoint="ollama",
            system_prompt="Transport specialist.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
            skills=["bossgate_coms_array"],
        )
        self.assertTrue(created["ok"])

        packaged = agent.bossgate_package_agent(
            name="porter",
            target_system_id="bridgebase-alpha-01",
            visibility_profile="id_card_only",
            secret_key="pack-key",
            **self.AUTH,
        )
        self.assertTrue(packaged["ok"])
        package_path = Path(packaged["package_file"])
        self.assertTrue(package_path.exists())

        del agent.agent_profiles["porter"]
        agent._save_agent_profiles()
        installed = agent.bossgate_install_agent(
            package_file=str(package_path),
            secret_key="pack-key",
            **self.AUTH,
        )
        self.assertTrue(installed["ok"])
        self.assertIn("porter", agent.agent_profiles)

    def test_bossgate_transfer_agent_requires_approved_target(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="runner",
            endpoint="ollama",
            system_prompt="Runner profile.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])
        packaged = agent.bossgate_package_agent(
            name="runner",
            target_system_id="bridgebase-alpha-01",
            secret_key="pack-key",
            **self.AUTH,
        )
        self.assertTrue(packaged["ok"])

        with patch.object(agent.bossgate_commands, "scan_target", return_value={"ok": False, "allowed_for_transfer": False, "target_type": "unknown"}):
            denied = agent.bossgate_transfer_agent(
                package_file=packaged["package_file"],
                destination="example.com",
                dry_run=True,
                **self.AUTH,
            )
        self.assertFalse(denied["ok"])

    def test_bossgate_transfer_agent_dry_run_logs_intent(self) -> None:
        agent = ModelGatewayAgent(interval_seconds=1)
        created = agent.create_agent_profile(
            name="runner2",
            endpoint="ollama",
            system_prompt="Runner profile.",
            temperature=0.2,
            max_tokens=600,
            tools=[],
        )
        self.assertTrue(created["ok"])
        packaged = agent.bossgate_package_agent(
            name="runner2",
            target_system_id="bridgebase-alpha-01",
            secret_key="pack-key",
            **self.AUTH,
        )
        self.assertTrue(packaged["ok"])

        with patch.object(agent.bossgate_commands, "scan_target", return_value={"ok": True, "allowed_for_transfer": True, "target_type": "bridgebase_alpha"}):
            accepted = agent.bossgate_transfer_agent(
                package_file=packaged["package_file"],
                destination="http://bridgebase.local",
                dry_run=True,
                **self.AUTH,
            )
        self.assertTrue(accepted["ok"])
        self.assertEqual(accepted["status"], "validated_only")
        self.assertTrue(agent.bossgate_commands.transfer_log_path.exists())


if __name__ == "__main__":
    unittest.main()
