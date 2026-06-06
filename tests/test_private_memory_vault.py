import json
import tempfile
import unittest
from pathlib import Path

from core.memory_vault import (
    canonical_json,
    decrypt_bytes,
    decrypt_json,
    derive_memory_key,
    encrypt_bytes,
    encrypt_json,
    event_aad,
    normalize_agent_id,
    normalize_memory_event,
    sign_attestation,
    verify_attestation,
)


class PrivateMemoryCryptoTests(unittest.TestCase):
    def test_event_envelope_requires_matching_aad(self) -> None:
        key = derive_memory_key("node-1", "scribe")
        aad = event_aad(
            agent_id="scribe",
            session_id="session-1",
            sequence=1,
            event_id="event-1",
            event_type="decision",
            timestamp="2026-06-06T12:00:00+00:00",
            previous_ciphertext_sha256="",
        )

        envelope = encrypt_bytes(b"proprietary decision", key, aad)
        serialized = canonical_json(envelope)

        self.assertNotIn(b"proprietary decision", serialized)
        self.assertEqual(
            decrypt_bytes(envelope, key, aad),
            b"proprietary decision",
        )
        with self.assertRaisesRegex(ValueError, "authentication"):
            decrypt_bytes(
                envelope,
                key,
                event_aad(
                    agent_id="scribe",
                    session_id="session-1",
                    sequence=1,
                    event_id="event-1",
                    event_type="decision",
                    timestamp="2026-06-06T12:00:00+00:00",
                    previous_ciphertext_sha256="tampered",
                ),
            )

    def test_normalize_event_classifies_importance_and_relationships(self) -> None:
        event = normalize_memory_event(
            agent_id="scribe",
            session_id="session-1",
            sequence=1,
            event_type="decision",
            payload={
                "text": "We decided to ship Project Anvil.",
                "project": "Anvil",
                "user": "Boss",
            },
            timestamp="2026-06-06T12:00:00+00:00",
        )

        self.assertEqual(event["importance"]["level"], "high")
        self.assertIn("decision", event["importance"]["reason_codes"])
        self.assertIn({"type": "project", "key": "Anvil"}, event["relationships"])
        self.assertIn({"type": "user", "key": "Boss"}, event["relationships"])
        self.assertIn("anvil", event["search_terms"])

    def test_empty_node_secret_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "secret"):
            derive_memory_key("", "scribe")

    def test_invalid_and_path_unsafe_agent_ids_rejected(self) -> None:
        for value in ("", ".", "..", "scribe/alpha", "scribe\\alpha", "Scribe"):
            with self.assertRaisesRegex(ValueError, "agent_id"):
                normalize_agent_id(value)

    def test_deterministic_event_id_for_identical_inputs(self) -> None:
        first = normalize_memory_event(
            agent_id="scribe",
            session_id="session-1",
            sequence=7,
            event_type="commitment",
            payload={"text": "I will follow up."},
            timestamp="2026-06-06T12:00:00+00:00",
        )
        second = normalize_memory_event(
            agent_id="scribe",
            session_id="session-1",
            sequence=7,
            event_type="commitment",
            payload={"text": "I will follow up."},
            timestamp="2026-06-06T12:00:00+00:00",
        )

        self.assertEqual(first["event_id"], second["event_id"])

    def test_manual_importance_and_reason_categories(self) -> None:
        reason_inputs = [
            ("commitment", {"text": "I will do it."}, "commitment"),
            ("relationship_change", {"text": "We changed our contact with Alex."}, "relationship_change"),
            ("lifecycle", {"text": "The project started."}, "lifecycle"),
            ("refusal", {"text": "I cannot comply."}, "refusal"),
            ("failure", {"text": "The upload failed."}, "failure"),
            ("recovery", {"text": "We recovered service."}, "recovery"),
            ("security", {"text": "Security review completed."}, "security"),
            ("discovery", {"text": "We discovered a new issue."}, "discovery"),
            ("milestone", {"text": "We reached the milestone."}, "milestone"),
        ]

        for event_type, payload, expected_reason in reason_inputs:
            event = normalize_memory_event(
                agent_id="scribe",
                session_id="session-1",
                sequence=3,
                event_type=event_type,
                payload=payload,
                timestamp="2026-06-06T12:00:00+00:00",
            )
            self.assertIn(expected_reason, event["importance"]["reason_codes"])
            self.assertEqual(event["importance"]["level"], "high")

        manual = normalize_memory_event(
            agent_id="scribe",
            session_id="session-1",
            sequence=4,
            event_type="note",
            payload={"important": True, "text": "Heads up."},
            timestamp="2026-06-06T12:00:00+00:00",
        )
        self.assertTrue(manual["importance"]["manually_marked"])
        self.assertIn("manual", manual["importance"]["reason_codes"])

    def test_only_supported_relationship_fields_and_search_tokens_are_normalized(self) -> None:
        event = normalize_memory_event(
            agent_id="scribe",
            session_id="session-1",
            sequence=8,
            event_type="note",
            payload={
                "text": "Alpha 123 and /unsafe path?",
                "project": "Anvil",
                "user": "Boss",
                "agent": "helper",
                "counterpart_agent": "peer-one",
                "employer": "BossForge",
                "organization": "Forge Ops",
                "unsupported": "ignore me",
            },
            timestamp="2026-06-06T12:00:00+00:00",
        )

        relationship_types = [item["type"] for item in event["relationships"]]
        self.assertEqual(
            relationship_types,
            ["agent", "employer", "organization", "project", "user"],
        )
        self.assertEqual(
            event["relationships"],
            [
                {"type": "agent", "key": "peer-one"},
                {"type": "employer", "key": "BossForge"},
                {"type": "organization", "key": "Forge Ops"},
                {"type": "project", "key": "Anvil"},
                {"type": "user", "key": "Boss"},
            ],
        )
        self.assertTrue(all(token == token.lower() for token in event["search_terms"]))
        self.assertTrue(all(token.isalnum() for token in event["search_terms"]))
        self.assertTrue(all(len(token) >= 3 for token in event["search_terms"]))
        self.assertIn("alpha", event["search_terms"])
        self.assertIn("anvil", event["search_terms"])

    def test_encrypt_json_roundtrip_and_wrong_aad_failure(self) -> None:
        key = derive_memory_key("node-1", "scribe")
        aad = event_aad(
            agent_id="scribe",
            session_id="session-1",
            sequence=9,
            event_id="event-9",
            event_type="note",
            timestamp="2026-06-06T12:00:00+00:00",
            previous_ciphertext_sha256="prev",
        )
        payload = {"alpha": 1, "nested": {"beta": True}}

        envelope = encrypt_json(payload, key, aad)
        self.assertEqual(decrypt_json(envelope, key, aad), payload)
        with self.assertRaisesRegex(ValueError, "authentication"):
            decrypt_json(envelope, key, aad + b"x")

    def test_attestation_sign_and_verify_tamper_rejection(self) -> None:
        key = derive_memory_key("node-1", "scribe")
        payload = {"agent_id": "scribe", "event_id": "event-10", "version": 1}
        signature = sign_attestation(payload, key)

        self.assertEqual(signature, sign_attestation(payload, key))
        verify_attestation(payload, key, signature)

        with self.assertRaisesRegex(ValueError, "signature mismatch"):
            verify_attestation(payload, key, signature[:-1] + ("0" if signature[-1] != "0" else "1"))


if __name__ == "__main__":
    unittest.main()
