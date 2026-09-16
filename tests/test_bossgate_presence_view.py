import unittest

from core.bossgate.presence_view import (
    build_agent_presence,
    build_node_presence,
    classify_presence_color,
)


class BossGatePresenceViewTests(unittest.TestCase):
    def test_build_node_presence_keeps_neutral_beacon_hidden(self) -> None:
        presence = build_node_presence(
            {
                "node_id": "beacon-1",
                "target_type": "unknown",
                "visited": False,
                "trade_linked": False,
            },
            current_node_id="bossforgeos",
        )
        self.assertEqual(presence["presence_kind"], "node")
        self.assertEqual(presence["discovery_state"], "unrevealed_beacon")
        self.assertEqual(presence["trust_state"], "neutral_unaffiliated")
        self.assertEqual(presence["display_name"], "")

    def test_build_agent_presence_only_emits_public_identity(self) -> None:
        presence = build_agent_presence(
            "promethius",
            {
                "current_node": "remote-node",
                "created_by_node": "bossforgeos",
                "agent_card": {"name": "Promethius", "agent_type": "worker", "rank": "specialist"},
                "disclosure_posture": "hidden",
            },
            current_node_id="bossforgeos",
        )
        self.assertEqual(presence["presence_kind"], "agent")
        self.assertEqual(presence["agent_name"], "promethius")
        self.assertNotIn("profile", presence)
        self.assertEqual(presence["inspection_state"], "origin_forge_required")

    def test_classify_presence_color_maps_trade_and_unknown_states(self) -> None:
        self.assertEqual(classify_presence_color("own", "revealed"), "green")
        self.assertEqual(classify_presence_color("trade_linked", "revealed"), "blue")
        self.assertEqual(classify_presence_color("unknown", "revealed"), "red")
        self.assertEqual(classify_presence_color("neutral_unaffiliated", "unrevealed_beacon"), "grey")


if __name__ == "__main__":
    unittest.main()
