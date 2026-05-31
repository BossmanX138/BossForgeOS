import unittest

from ui import control_hall


class ControlHallCollabHandlerFlowTests(unittest.TestCase):
    def test_join_invalid_agent_emits_error_and_skips_room_join(self) -> None:
        calls = []

        def emit_fn(event, payload, **kwargs):
            calls.append((event, payload, kwargs))

        joined = []

        def join_room_fn(room):
            joined.append(room)

        control_hall._collab_join_flow({}, {}, {}, emit_fn=emit_fn, join_room_fn=join_room_fn)

        self.assertEqual(joined, [])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "presence")
        self.assertFalse(calls[0][1].get("ok"))

    def test_join_valid_agent_joins_and_broadcasts(self) -> None:
        calls = []

        def emit_fn(event, payload, **kwargs):
            calls.append((event, payload, kwargs))

        joined = []

        def join_room_fn(room):
            joined.append(room)

        control_hall._collab_join_flow({}, {}, {"agent": "coder", "user": "alice"}, emit_fn=emit_fn, join_room_fn=join_room_fn)

        self.assertEqual(joined, ["coder"])
        self.assertEqual(calls[0][0], "presence")
        self.assertTrue(calls[0][1].get("ok"))
        self.assertEqual(calls[0][2].get("room"), "coder")

    def test_edit_invalid_agent_emits_local_error_payload(self) -> None:
        calls = []

        def emit_fn(event, payload, **kwargs):
            calls.append((event, payload, kwargs))

        control_hall._collab_edit_flow({}, emit_fn=emit_fn)

        self.assertEqual(calls[0][0], "agent_edit")
        self.assertFalse(calls[0][1].get("ok"))
        self.assertEqual(calls[0][2], {})


if __name__ == "__main__":
    unittest.main()
