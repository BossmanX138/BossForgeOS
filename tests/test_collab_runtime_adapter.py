import unittest

from modules.collab_runtime import api_adapter as collab_api


class CollabRuntimeAdapterTests(unittest.TestCase):
    def test_join_leave_updates_editor_state(self) -> None:
        editors: dict[str, set[str]] = {}
        locks: dict[str, str] = {}
        agent, presence = collab_api.join_agent(editors, locks, {"agent": "Coder", "user": "alice"})
        self.assertEqual(agent, "coder")
        self.assertIn("alice", editors["coder"])
        self.assertIn("alice", presence["editors"])

        agent, presence = collab_api.leave_agent(editors, locks, {"agent": "Coder", "user": "alice"})
        self.assertEqual(agent, "coder")
        self.assertNotIn("coder", editors)
        self.assertEqual(presence["editors"], [])

    def test_lock_unlock_contract(self) -> None:
        editors = {"coder": {"alice"}}
        locks: dict[str, str] = {}
        _, presence = collab_api.lock_agent(editors, locks, {"agent": "coder", "user": "alice"})
        self.assertEqual(locks.get("coder"), "alice")
        self.assertEqual(presence["lock"], "alice")

        _, presence = collab_api.unlock_agent(editors, locks, {"agent": "coder", "user": "alice"})
        self.assertNotIn("coder", locks)
        self.assertIsNone(presence["lock"])

    def test_edit_payload_contract(self) -> None:
        agent, payload = collab_api.edit_agent_payload({"agent": "coder", "user": "alice", "content": {"field": "x"}})
        self.assertEqual(agent, "coder")
        self.assertEqual(payload["user"], "alice")
        self.assertIsInstance(payload["content"], dict)


if __name__ == "__main__":
    unittest.main()
