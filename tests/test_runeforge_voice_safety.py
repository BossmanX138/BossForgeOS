import tempfile
import unittest
from pathlib import Path

from core.agents.runeforge_agent import RuneforgeAgent


class RuneforgeVoiceSafetyTests(unittest.TestCase):
    def test_high_risk_voice_action_requests_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = RuneforgeAgent(root=Path(tmp))

            def fake_parse(_args, timeout_seconds=120):
                return {
                    "ok": True,
                    "parsed": {
                        "ok": True,
                        "confidence": 0.95,
                        "action": {"action_type": "set_volume", "params": {"level": 10}},
                    },
                }

            agent._run_voice_dictation = fake_parse  # type: ignore[method-assign]
            agent._high_risk_action_types = lambda: {"set_volume"}  # type: ignore[method-assign]
            agent._run_os_command_processor = lambda *a, **k: {"ok": False, "returncode": 1}  # type: ignore[method-assign]

            result = agent.run_voice_text({"text": "Runeforge set volume to 10"})
            voice_result = result.get("voice_result", {})

            self.assertTrue(result.get("ok"))
            self.assertEqual(voice_result.get("voice_action"), "request_os_action_approval")
            pending = agent._load_pending_approval()
            self.assertEqual(pending.get("type"), "os_action")

    def test_low_confidence_requires_clarification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = RuneforgeAgent(root=Path(tmp))

            def fake_parse(_args, timeout_seconds=120):
                return {
                    "ok": True,
                    "parsed": {
                        "ok": True,
                        "confidence": 0.3,
                        "action": {"action_type": "open_app", "params": {"path": "notepad.exe"}},
                    },
                }

            agent._run_voice_dictation = fake_parse  # type: ignore[method-assign]

            result = agent.run_voice_text({"text": "Runeforge open app maybe notepad"})
            voice_result = result.get("voice_result", {})

            self.assertFalse(result.get("ok"))
            self.assertEqual(voice_result.get("voice_action"), "clarification_required")

    def test_reject_pending_os_action_cancels_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = RuneforgeAgent(root=Path(tmp))
            requested = agent.request_os_action_approval(
                {
                    "action": {"action_type": "shutdown", "params": {}},
                    "spoken_text": "shutdown now",
                    "source": "test",
                }
            )
            self.assertTrue(requested.get("ok"))

            denied = agent.respond_pending_approval({"approved": False, "source": "test"})
            self.assertTrue(denied.get("ok"))
            self.assertFalse(denied.get("approved"))
            self.assertEqual(agent._load_pending_approval(), {})

    def test_pending_os_action_requires_command_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = RuneforgeAgent(root=Path(tmp))
            requested = agent.request_os_action_approval(
                {
                    "action": {"action_type": "delete_file", "params": {"path": "C:/temp/a.txt"}},
                    "spoken_text": "delete file",
                    "source": "test",
                }
            )
            self.assertTrue(requested.get("ok"))

            outcome = agent.respond_pending_approval({"approved": True, "source": "test"})
            self.assertFalse(outcome.get("ok"))
            self.assertTrue(outcome.get("requires_command_code"))
            self.assertEqual(agent._load_pending_approval().get("type"), "os_action")

    def test_pending_os_action_accepts_voice_code_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = RuneforgeAgent(root=Path(tmp))
            agent.request_os_action_approval(
                {
                    "action": {"action_type": "set_volume", "params": {"level": 5}},
                    "spoken_text": "set volume",
                    "source": "test",
                }
            )

            def fake_processor(args, timeout_seconds=180):
                return {"ok": True, "returncode": 0, "parsed": {"ok": True}, "stdout": "", "stderr": "", "args": args}

            agent._run_os_command_processor = fake_processor  # type: ignore[method-assign]
            result = agent.run_voice_text({"text": "Runeforge command code alpha123"})

            self.assertTrue(result.get("ok"))
            voice_result = result.get("voice_result", {})
            self.assertEqual(voice_result.get("voice_action"), "approve_pending_action")
            self.assertEqual(agent._load_pending_approval(), {})

    def test_close_app_confirmation_does_not_require_command_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = RuneforgeAgent(root=Path(tmp))
            requested = agent.request_os_action_approval(
                {
                    "action": {"action_type": "close_app", "params": {"name": "notepad"}},
                    "spoken_text": "close notepad",
                    "source": "test",
                    "requires_command_code": False,
                }
            )
            self.assertTrue(requested.get("ok"))

            def fake_processor(args, timeout_seconds=180):
                return {"ok": True, "returncode": 0, "parsed": {"ok": True}, "stdout": "", "stderr": "", "args": args}

            agent._run_os_command_processor = fake_processor  # type: ignore[method-assign]
            approved = agent.respond_pending_approval({"approved": True, "source": "test"})

            self.assertTrue(approved.get("ok"))
            self.assertTrue(approved.get("approved"))
            self.assertEqual(agent._load_pending_approval(), {})


if __name__ == "__main__":
    unittest.main()
