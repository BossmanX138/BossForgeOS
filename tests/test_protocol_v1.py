import unittest

from core.rune.protocol_v1 import (
    PROTOCOL_VERSION,
    is_compatible,
    load_schema,
    validate_message,
    wrap_command,
    wrap_event,
)


class ProtocolV1Tests(unittest.TestCase):
    # ── wrap helpers ────────────────────────────────────────────────────

    def test_wrap_event_produces_valid_envelope(self) -> None:
        msg = wrap_event("archivist", "status_ping", {"ok": True})
        ok, errors = validate_message(msg)
        self.assertTrue(ok, errors)
        self.assertEqual(msg["protocol_version"], PROTOCOL_VERSION)
        self.assertEqual(msg["type"], "event")
        self.assertEqual(msg["source"], "archivist")
        self.assertEqual(msg["event"], "status_ping")
        self.assertIn("timestamp", msg)

    def test_wrap_command_produces_valid_envelope(self) -> None:
        msg = wrap_command("runeforge", "status_ping", {"x": 1}, issued_by="test")
        ok, errors = validate_message(msg)
        self.assertTrue(ok, errors)
        self.assertEqual(msg["type"], "command")
        self.assertEqual(msg["target"], "runeforge")
        self.assertEqual(msg["command"], "status_ping")
        self.assertEqual(msg["args"], {"x": 1})
        self.assertEqual(msg["issued_by"], "test")

    def test_wrap_event_defaults_data_and_level(self) -> None:
        msg = wrap_event("devlot", "ping")
        self.assertEqual(msg["data"], {})
        self.assertEqual(msg["level"], "info")

    def test_wrap_command_defaults_args_and_issued_by(self) -> None:
        msg = wrap_command("devlot", "reset")
        self.assertEqual(msg["args"], {})
        self.assertEqual(msg["issued_by"], "cli")

    # ── validate_message – error cases ──────────────────────────────────

    def test_validate_message_non_dict_rejected(self) -> None:
        ok, errors = validate_message("not a dict")
        self.assertFalse(ok)
        self.assertTrue(errors)

    def test_validate_message_missing_protocol_version(self) -> None:
        msg = wrap_event("archivist", "ping")
        del msg["protocol_version"]
        ok, errors = validate_message(msg)
        self.assertFalse(ok)
        self.assertTrue(any("protocol_version" in e for e in errors))

    def test_validate_message_missing_type(self) -> None:
        msg = wrap_event("archivist", "ping")
        del msg["type"]
        ok, errors = validate_message(msg)
        self.assertFalse(ok)
        self.assertTrue(any("type" in e for e in errors))

    def test_validate_message_missing_timestamp(self) -> None:
        msg = wrap_event("archivist", "ping")
        del msg["timestamp"]
        ok, errors = validate_message(msg)
        self.assertFalse(ok)
        self.assertTrue(any("timestamp" in e for e in errors))

    def test_validate_message_invalid_type_value(self) -> None:
        msg = {
            "protocol_version": "1.0",
            "type": "broadcast",
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        ok, errors = validate_message(msg)
        self.assertFalse(ok)
        self.assertTrue(any("type" in e for e in errors))

    def test_validate_message_incompatible_version(self) -> None:
        msg = wrap_event("archivist", "ping")
        msg["protocol_version"] = "2.0"
        ok, errors = validate_message(msg)
        self.assertFalse(ok)
        self.assertTrue(any("compatible" in e or "protocol_version" in e for e in errors))

    def test_validate_event_missing_source(self) -> None:
        msg = wrap_event("archivist", "ping")
        del msg["source"]
        ok, errors = validate_message(msg)
        self.assertFalse(ok)
        self.assertTrue(any("source" in e for e in errors))

    def test_validate_event_missing_event_name(self) -> None:
        msg = wrap_event("archivist", "ping")
        del msg["event"]
        ok, errors = validate_message(msg)
        self.assertFalse(ok)
        self.assertTrue(any("event" in e for e in errors))

    def test_validate_event_invalid_level(self) -> None:
        msg = wrap_event("archivist", "ping", level="verbose")
        ok, errors = validate_message(msg)
        self.assertFalse(ok)
        self.assertTrue(any("level" in e for e in errors))

    def test_validate_command_missing_target(self) -> None:
        msg = wrap_command("runeforge", "ping")
        del msg["target"]
        ok, errors = validate_message(msg)
        self.assertFalse(ok)
        self.assertTrue(any("target" in e for e in errors))

    def test_validate_command_missing_command_name(self) -> None:
        msg = wrap_command("runeforge", "ping")
        del msg["command"]
        ok, errors = validate_message(msg)
        self.assertFalse(ok)
        self.assertTrue(any("command" in e for e in errors))

    # ── is_compatible ───────────────────────────────────────────────────

    def test_is_compatible_current_version(self) -> None:
        self.assertTrue(is_compatible(PROTOCOL_VERSION))

    def test_is_compatible_same_major_lower_minor(self) -> None:
        self.assertTrue(is_compatible("1.0"))

    def test_is_compatible_wrong_major(self) -> None:
        self.assertFalse(is_compatible("2.0"))

    def test_is_compatible_invalid_string(self) -> None:
        self.assertFalse(is_compatible("not-a-version"))

    def test_is_compatible_empty_string(self) -> None:
        self.assertFalse(is_compatible(""))

    # ── load_schema ─────────────────────────────────────────────────────

    def test_load_schema_returns_dict_with_required_keys(self) -> None:
        schema = load_schema()
        self.assertIsInstance(schema, dict)
        self.assertIn("$schema", schema)
        self.assertIn("properties", schema)
        self.assertIn("required", schema)


if __name__ == "__main__":
    unittest.main()
