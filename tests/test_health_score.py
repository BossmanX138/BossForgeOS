import unittest
from datetime import datetime, timezone

from core.state.health_score import _grade, score_agent_health, score_all_agents


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class HealthScoreTests(unittest.TestCase):
    # ── _grade helper ────────────────────────────────────────────────────

    def test_grade_a_at_90(self) -> None:
        self.assertEqual(_grade(90), "A")
        self.assertEqual(_grade(100), "A")

    def test_grade_b_at_75(self) -> None:
        self.assertEqual(_grade(75), "B")
        self.assertEqual(_grade(89), "B")

    def test_grade_c_at_60(self) -> None:
        self.assertEqual(_grade(60), "C")
        self.assertEqual(_grade(74), "C")

    def test_grade_d_at_40(self) -> None:
        self.assertEqual(_grade(40), "D")
        self.assertEqual(_grade(59), "D")

    def test_grade_f_below_40(self) -> None:
        self.assertEqual(_grade(39), "F")
        self.assertEqual(_grade(0), "F")

    # ── score_agent_health ───────────────────────────────────────────────

    def test_alive_fresh_agent_scores_high(self) -> None:
        state = {"status": "alive", "timestamp": _now_iso()}
        result = score_agent_health("archivist", state)
        # Should get state_present(20) + alive(30) + recency(25) + no_errors(10) = at least 85
        self.assertGreaterEqual(result["score"], 85)
        self.assertIn(result["grade"], ("A", "B"))

    def test_missing_state_scores_low(self) -> None:
        result = score_agent_health("ghost_agent", {})
        # Nothing contributes except possibly no_errors(10)
        self.assertLessEqual(result["score"], 10)

    def test_stale_state_loses_recency_points(self) -> None:
        state = {"status": "alive", "timestamp": "2020-01-01T00:00:00+00:00"}
        result = score_agent_health("stale_agent", state)
        self.assertEqual(result["factors"]["last_seen_recency"]["contribution"], 0)

    def test_error_events_reduce_score(self) -> None:
        state = {"status": "alive", "timestamp": _now_iso()}
        # Compare error events vs. same-agent info events (both have recent_activity points,
        # so the only difference is the no_recent_errors contribution).
        events_with_error = [
            {"source": "archivist", "level": "error", "timestamp": _now_iso()},
        ]
        events_info_only = [
            {"source": "archivist", "level": "info", "timestamp": _now_iso()},
        ]
        result_errors = score_agent_health("archivist", state, recent_events=events_with_error)
        result_clean = score_agent_health("archivist", state, recent_events=events_info_only)
        self.assertLess(result_errors["score"], result_clean["score"])
        self.assertTrue(result_errors["factors"]["no_recent_errors"]["has_errors"])

    def test_recent_event_activity_adds_points(self) -> None:
        state = {"status": "alive", "timestamp": _now_iso()}
        events = [{"source": "archivist", "level": "info", "timestamp": _now_iso()}]
        result_active = score_agent_health("archivist", state, recent_events=events)
        result_idle = score_agent_health("archivist", state, recent_events=[])
        self.assertGreater(result_active["score"], result_idle["score"])
        self.assertTrue(result_active["factors"]["recent_activity"]["any_in_last_30min"])

    def test_events_from_other_agents_not_counted(self) -> None:
        state = {"status": "alive", "timestamp": _now_iso()}
        events = [{"source": "runeforge", "level": "error", "timestamp": _now_iso()}]
        result = score_agent_health("archivist", state, recent_events=events)
        # Runeforge error should not affect archivist's no_recent_errors factor
        self.assertFalse(result["factors"]["no_recent_errors"]["has_errors"])

    def test_result_contains_expected_keys(self) -> None:
        result = score_agent_health("devlot", {})
        self.assertIn("agent_id", result)
        self.assertIn("score", result)
        self.assertIn("grade", result)
        self.assertIn("factors", result)

    def test_factors_contains_all_expected_keys(self) -> None:
        result = score_agent_health("devlot", {"status": "alive", "timestamp": _now_iso()})
        for key in ("state_present", "status_alive", "last_seen_recency", "recent_activity", "no_recent_errors"):
            self.assertIn(key, result["factors"])

    def test_score_bounded_0_to_100(self) -> None:
        state = {"status": "alive", "timestamp": _now_iso()}
        events = [{"source": "devlot", "level": "info", "timestamp": _now_iso()}]
        result = score_agent_health("devlot", state, recent_events=events)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)

    # ── score_all_agents ─────────────────────────────────────────────────

    def test_score_all_agents_returns_dict_keyed_by_id(self) -> None:
        state_tree = {
            "archivist": {"status": "alive", "timestamp": _now_iso()},
            "runeforge": {"status": "alive", "timestamp": _now_iso()},
        }
        results = score_all_agents(state_tree)
        self.assertIn("archivist", results)
        self.assertIn("runeforge", results)
        for agent_id, result in results.items():
            self.assertEqual(result["agent_id"], agent_id)
            self.assertIn("score", result)

    def test_score_all_agents_empty_tree_returns_empty(self) -> None:
        self.assertEqual(score_all_agents({}), {})


if __name__ == "__main__":
    unittest.main()
