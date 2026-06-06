import base64
import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import core.memory_vault.private_memory_vault as private_memory_vault_module
from core.memory_vault import (
    PrivateMemoryVault,
    atomic_write_bytes,
    atomic_write_json,
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
    validate_private_memory_descriptor,
    verify_attestation,
)


class PrivateMemoryCryptoTests(unittest.TestCase):
    def test_canonical_json_is_sorted_compact_and_ascii_escaped(self) -> None:
        payload = {"z": "snowman \u2603", "a": {"b": 2, "a": 1}}

        self.assertEqual(
            canonical_json(payload),
            b'{"a":{"a":1,"b":2},"z":"snowman \\u2603"}',
        )

    def test_derive_memory_key_matches_expected_digest(self) -> None:
        self.assertEqual(
            derive_memory_key("node-1", "scribe"),
            hashlib.sha256(b"node-1:scribe:private-memory-v1").digest(),
        )

    def test_encrypt_and_decrypt_reject_non_32_byte_keys(self) -> None:
        key = derive_memory_key("node-1", "scribe")
        aad = event_aad(
            agent_id="scribe",
            session_id="session-1",
            sequence=1,
            event_id="event-1",
            event_type="note",
            timestamp="2026-06-06T12:00:00+00:00",
            previous_ciphertext_sha256="",
        )

        for bad_key in (b"a" * 16, b"b" * 24, "not-bytes"):
            with self.assertRaisesRegex(ValueError, "memory key"):
                encrypt_bytes(b"payload", bad_key, aad)
            with self.assertRaisesRegex(ValueError, "memory key"):
                decrypt_bytes(encrypt_bytes(b"payload", key, aad), bad_key, aad)

    def test_encrypt_bytes_uses_fresh_nonce_and_twelve_byte_nonce(self) -> None:
        key = derive_memory_key("node-1", "scribe")
        aad = event_aad(
            agent_id="scribe",
            session_id="session-1",
            sequence=1,
            event_id="event-1",
            event_type="note",
            timestamp="2026-06-06T12:00:00+00:00",
            previous_ciphertext_sha256="",
        )

        first = encrypt_bytes(b"payload", key, aad)
        second = encrypt_bytes(b"payload", key, aad)

        self.assertNotEqual(first["nonce_b64"], second["nonce_b64"])
        self.assertEqual(len(base64.b64decode(first["nonce_b64"])), 12)
        self.assertEqual(len(base64.b64decode(second["nonce_b64"])), 12)

    def test_event_aad_has_exact_keys_and_values(self) -> None:
        aad = event_aad(
            agent_id="scribe",
            session_id="Session-1",
            sequence=7,
            event_id="event-7",
            event_type="decision",
            timestamp="2026-06-06T12:00:00+00:00",
            previous_ciphertext_sha256="prev",
        )
        payload = json.loads(aad.decode("utf-8"))

        self.assertEqual(
            payload,
            {
                "agent_id": "scribe",
                "event_id": "event-7",
                "event_type": "decision",
                "previous_ciphertext_sha256": "prev",
                "sequence": 7,
                "session_id": "Session-1",
                "timestamp": "2026-06-06T12:00:00+00:00",
            },
        )
        self.assertEqual(
            list(payload.keys()),
            [
                "agent_id",
                "event_id",
                "event_type",
                "previous_ciphertext_sha256",
                "sequence",
                "session_id",
                "timestamp",
            ],
        )

    def test_event_aad_and_event_result_snapshot_original_payload(self) -> None:
        payload = {
            "text": "We decided to ship Project Anvil.",
            "project": "Anvil",
            "meta": {"owner": "Boss", "tags": ["alpha"]},
        }

        event = normalize_memory_event(
            agent_id="scribe",
            session_id="session-1",
            sequence=2,
            event_type="decision",
            payload=payload,
            timestamp="2026-06-06T12:00:00+00:00",
        )

        event_id_before = event["event_id"]
        search_terms_before = list(event["search_terms"])
        importance_before = json.loads(json.dumps(event["importance"]))
        payload["text"] = "mutated"
        payload["project"] = "Changed"
        payload["meta"]["owner"] = "Changed"
        payload["meta"]["tags"].append("beta")

        self.assertEqual(event["event_id"], event_id_before)
        self.assertEqual(event["search_terms"], search_terms_before)
        self.assertEqual(event["importance"], importance_before)
        self.assertEqual(event["payload"]["text"], "We decided to ship Project Anvil.")
        self.assertEqual(event["payload"]["project"], "Anvil")
        self.assertEqual(event["payload"]["meta"]["owner"], "Boss")
        self.assertEqual(event["payload"]["meta"]["tags"], ["alpha"])

    def test_normalize_memory_event_has_exact_keys(self) -> None:
        event = normalize_memory_event(
            agent_id="scribe",
            session_id="session-1",
            sequence=1,
            event_type="note",
            payload={"text": "hello"},
            timestamp="2026-06-06T12:00:00+00:00",
        )

        self.assertEqual(
            list(event.keys()),
            [
                "schema_version",
                "event_id",
                "agent_id",
                "session_id",
                "sequence",
                "event_type",
                "timestamp",
                "payload",
                "search_terms",
                "topics",
                "relationships",
                "importance",
            ],
        )

    def test_atomic_write_bytes_replaces_content_and_writes_canonical_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "nested" / "memory.json"

            atomic_write_bytes(target, b"first")
            self.assertEqual(target.read_bytes(), b"first")
            self.assertTrue(target.parent.exists())

            atomic_write_json(target, {"z": 2, "a": 1})
            self.assertEqual(target.read_bytes(), b'{"a":1,"z":2}')

    def test_atomic_write_cleanup_on_failure_removes_temp_and_preserves_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "vault" / "memory.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"original")

            with patch.object(Path, "replace", side_effect=RuntimeError("replace failed")):
                with self.assertRaisesRegex(RuntimeError, "replace failed"):
                    atomic_write_bytes(target, b"updated")

            self.assertEqual(target.read_bytes(), b"original")
            self.assertFalse(any(target.parent.glob(f".{target.name}.*")))

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
        self.assertEqual(decrypt_bytes(envelope, key, aad), b"proprietary decision")
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
            payload={"text": "I promise to follow up."},
            timestamp="2026-06-06T12:00:00+00:00",
        )
        second = normalize_memory_event(
            agent_id="scribe",
            session_id="session-1",
            sequence=7,
            event_type="commitment",
            payload={"text": "I promise to follow up."},
            timestamp="2026-06-06T12:00:00+00:00",
        )

        self.assertEqual(first["event_id"], second["event_id"])

    def test_manual_importance_and_reason_categories(self) -> None:
        reason_inputs = [
            ("commitment", {"text": "I promise to do it."}, "commitment"),
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

        ordinary_note = normalize_memory_event(
            agent_id="scribe",
            session_id="session-1",
            sequence=5,
            event_type="note",
            payload={"text": "We will review this tomorrow."},
            timestamp="2026-06-06T12:00:00+00:00",
        )
        self.assertEqual(ordinary_note["importance"]["level"], "normal")
        self.assertNotIn("commitment", ordinary_note["importance"]["reason_codes"])

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
            ["agent", "agent", "employer", "organization", "project", "user"],
        )
        self.assertEqual(
            event["relationships"],
            [
                {"type": "agent", "key": "helper"},
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

    def test_numeric_payload_values_do_not_enter_search_terms(self) -> None:
        event = normalize_memory_event(
            agent_id="scribe",
            session_id="session-1",
            sequence=11,
            event_type="note",
            payload={
                "text": "Ticket 42 is open",
                "count": 1234,
                "enabled": True,
                "ratio": 2.5,
            },
            timestamp="2026-06-06T12:00:00+00:00",
        )

        self.assertIn("ticket", event["search_terms"])
        self.assertNotIn("42", event["search_terms"])
        self.assertNotIn("1234", event["search_terms"])
        self.assertNotIn("true", event["search_terms"])
        self.assertNotIn("2", event["search_terms"])

    def test_punctuation_keywords_classify_without_broad_will(self) -> None:
        refusal_cases = ["I can't do that", "I won't do that"]
        for sequence, text in enumerate(refusal_cases, start=12):
            event = normalize_memory_event(
                agent_id="scribe",
                session_id="session-1",
                sequence=sequence,
                event_type="note",
                payload={"text": text},
                timestamp="2026-06-06T12:00:00+00:00",
            )
            self.assertIn("refusal", event["importance"]["reason_codes"])

        commitment = normalize_memory_event(
            agent_id="scribe",
            session_id="session-1",
            sequence=14,
            event_type="note",
            payload={"text": "follow-up promised"},
            timestamp="2026-06-06T12:00:00+00:00",
        )
        self.assertIn("commitment", commitment["importance"]["reason_codes"])

        ordinary_future = normalize_memory_event(
            agent_id="scribe",
            session_id="session-1",
            sequence=15,
            event_type="note",
            payload={"text": "We will review this tomorrow."},
            timestamp="2026-06-06T12:00:00+00:00",
        )
        self.assertEqual(ordinary_future["importance"]["level"], "normal")
        self.assertNotIn("commitment", ordinary_future["importance"]["reason_codes"])

    def test_unrelated_words_do_not_trigger_importance_keywords(self) -> None:
        texts = [
            "A friendship note for the weekend.",
            "The insecure layer was updated.",
            "A profound summary of the incident.",
            "The terror alert was reviewed.",
        ]

        for sequence, text in enumerate(texts, start=20):
            event = normalize_memory_event(
                agent_id="scribe",
                session_id="session-1",
                sequence=sequence,
                event_type="note",
                payload={"text": text},
                timestamp="2026-06-06T12:00:00+00:00",
            )
            self.assertEqual(event["importance"]["level"], "normal")
            self.assertEqual(event["importance"]["reason_codes"], [])

    def test_session_ids_use_same_strict_path_safe_contract(self) -> None:
        for value in ("", ".", "..", "bad id", "bad/id", "bad\\id", "bad,id", "bad\tid"):
            with self.assertRaisesRegex(ValueError, "session_id"):
                event_aad(
                    agent_id="scribe",
                    session_id=value,
                    sequence=1,
                    event_id="event-1",
                    event_type="note",
                    timestamp="2026-06-06T12:00:00+00:00",
                    previous_ciphertext_sha256="",
                )
            with self.assertRaisesRegex(ValueError, "session_id"):
                normalize_memory_event(
                    agent_id="scribe",
                    session_id=value,
                    sequence=1,
                    event_type="note",
                    payload={"text": "ok"},
                    timestamp="2026-06-06T12:00:00+00:00",
                )
        self.assertEqual(
            json.loads(
                event_aad(
                    agent_id="scribe",
                    session_id="Session-1",
                    sequence=1,
                    event_id="event-1",
                    event_type="note",
                    timestamp="2026-06-06T12:00:00+00:00",
                    previous_ciphertext_sha256="",
                ).decode("utf-8")
            )["session_id"],
            "Session-1",
        )

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

        non_object = encrypt_bytes(canonical_json(["not", "an", "object"]), key, aad)
        with self.assertRaisesRegex(ValueError, "object"):
            decrypt_json(non_object, key, aad)

    def test_decrypt_bytes_rejects_malformed_envelopes(self) -> None:
        key = derive_memory_key("node-1", "scribe")
        aad = event_aad(
            agent_id="scribe",
            session_id="session-1",
            sequence=10,
            event_id="event-10",
            event_type="note",
            timestamp="2026-06-06T12:00:00+00:00",
            previous_ciphertext_sha256="prev",
        )
        envelope = encrypt_bytes(b"payload", key, aad)

        malformed_cases = [
            None,
            [],
            {**envelope, "version": 2},
            {"alg": "AES-256-GCM"},
            {**envelope, "nonce_b64": "@@@"},
            {**envelope, "nonce_b64": base64.b64encode(b"short").decode("ascii")},
            {**envelope, "ciphertext_sha256": "0" * 64},
            {**envelope, "alg": "AES-128-GCM"},
        ]
        for bad in malformed_cases:
            with self.assertRaisesRegex(ValueError, "authentication"):
                decrypt_bytes(bad, key, aad)

        with self.assertRaisesRegex(ValueError, "authentication"):
            decrypt_bytes(envelope, key, aad + b"x")

    def test_attestation_sign_and_verify_tamper_rejection(self) -> None:
        key = derive_memory_key("node-1", "scribe")
        payload = {"agent_id": "scribe", "event_id": "event-10", "version": 1}
        signature = sign_attestation(payload, key)

        self.assertEqual(signature, sign_attestation(payload, key))
        verify_attestation(payload, signature, key)

        with self.assertRaisesRegex(ValueError, "signature mismatch"):
            verify_attestation(
                {"agent_id": "scribe", "event_id": "event-10", "version": 2},
                signature,
                key,
            )
        with self.assertRaisesRegex(ValueError, "signature mismatch"):
            verify_attestation(payload, signature[:-1] + ("0" if signature[-1] != "0" else "1"), key)

class PrivateMemoryJournalTests(unittest.TestCase):
    def _make_vault(self, root: Path) -> PrivateMemoryVault:
        return PrivateMemoryVault(
            vault_root=root,
            agent_id="scribe",
            node_secret="super-secret-node-key",
            key_ref="key-2026-06",
        )

    def _verification_key(self) -> bytes:
        return derive_memory_key("super-secret-node-key", "scribe")

    def _decrypt_manifest(self, vault: PrivateMemoryVault) -> dict:
        return decrypt_json(
            json.loads(vault.manifest_path.read_text("utf-8")),
            vault._key,
            private_memory_vault_module._artifact_aad(
                owner_agent_id=vault.agent_id,
                artifact_kind="vault.manifest",
            ),
        )

    def _decrypt_state(self, vault: PrivateMemoryVault, session_id: str) -> dict:
        session_root = vault.agent_root / "active" / session_id
        return decrypt_json(
            json.loads((session_root / "session.state.enc").read_text("utf-8")),
            vault._key,
            private_memory_vault_module._artifact_aad(
                owner_agent_id=vault.agent_id,
                artifact_kind="session.state",
                session_id=session_id,
            ),
        )

    def test_initialize_descriptor_manifest_and_attestation_verified_and_no_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._make_vault(Path(tmp))

            descriptor = vault.initialize()

            self.assertEqual(
                descriptor,
                {
                    "schema_version": "1.0",
                    "owner_agent_id": "scribe",
                    "ciphertext_ref": str((Path(tmp) / "scribe" / "vault.manifest.enc").resolve()),
                    "attestation_sha256": hashlib.sha256(
                        (Path(tmp) / "scribe" / "vault.attestation.json").read_bytes()
                    ).hexdigest(),
                    "key_ref": "key-2026-06",
                    "verified": True,
                },
            )

            validated = validate_private_memory_descriptor(
                descriptor,
                expected_agent_id="scribe",
                vault_root=Path(tmp),
                verification_key=self._verification_key(),
            )
            self.assertEqual(validated, descriptor)
            self.assertEqual(
                self._decrypt_manifest(vault),
                {
                    "schema_version": "1.0",
                    "owner_agent_id": "scribe",
                    "key_ref": "key-2026-06",
                },
            )

            attestation = json.loads((Path(tmp) / "scribe" / "vault.attestation.json").read_text("utf-8"))
            self.assertEqual(
                list(attestation.keys()),
                [
                    "alg",
                    "key_ref",
                    "manifest_sha256",
                    "owner",
                    "schema",
                    "signature",
                    "verified",
                ],
            )
            self.assertEqual(attestation["owner"], "scribe")
            self.assertEqual(attestation["key_ref"], "key-2026-06")
            self.assertTrue(attestation["verified"])
            self.assertNotIn("super-secret-node-key", canonical_json(attestation).decode("utf-8"))

            for file_path in (Path(tmp) / "scribe").rglob("*"):
                if file_path.is_file():
                    contents = file_path.read_bytes()
                    self.assertNotIn(b"super-secret-node-key", contents)

    def test_initialize_is_idempotent_for_same_owner_and_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._make_vault(Path(tmp))

            first = vault.initialize()
            second = vault.initialize()

            self.assertEqual(second, first)

    def test_append_two_events_builds_chain_and_required_artifacts_without_plaintext_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = self._make_vault(root)
            vault.initialize()

            first = vault.append_event(
                "session-1",
                "decision",
                {"text": "vault-secret-phrase alpha", "project": "Anvil", "topics": ["launch"]},
                timestamp="2026-06-06T12:00:00+00:00",
            )
            second = vault.append_event(
                "session-1",
                "note",
                {"text": "follow-up on vault-secret-phrase", "user": "Boss"},
                timestamp="2026-06-06T12:05:00+00:00",
            )

            self.assertEqual(first["sequence"], 1)
            self.assertEqual(second["sequence"], 2)
            self.assertEqual(first["previous_ciphertext_sha256"], "")
            self.assertEqual(second["previous_ciphertext_sha256"], first["ciphertext_sha256"])

            session_root = root / "scribe" / "active" / "session-1"
            for relative in (
                Path("journal/000001.event.enc"),
                Path("journal/000002.event.enc"),
                Path("search.index.enc"),
                Path("important.index.enc"),
                Path("relationship.index.enc"),
                Path("session.state.enc"),
            ):
                self.assertTrue((session_root / relative).exists(), str(relative))

            verified = vault.verify_active_session("session-1")
            self.assertEqual(
                verified,
                {
                    "verified": True,
                    "owner_agent_id": "scribe",
                    "session_id": "session-1",
                    "event_count": 2,
                    "last_sequence": 2,
                    "last_ciphertext_sha256": second["ciphertext_sha256"],
                },
            )

            for file_path in (root / "scribe").rglob("*"):
                if file_path.is_file():
                    self.assertNotIn(b"vault-secret-phrase", file_path.read_bytes(), str(file_path))

    def test_append_event_recovers_after_state_write_failure_and_next_append_continues_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = self._make_vault(root)
            vault.initialize()
            original_atomic_write_json = private_memory_vault_module.atomic_write_json
            session_root = root / "scribe" / "active" / "session-1"

            def failing_atomic_write_json(path: Path, payload: object) -> None:
                target = Path(path)
                if (
                    target.name == "session.state.enc"
                    and (session_root / "journal" / "000001.event.enc").exists()
                    and (session_root / "search.index.enc").exists()
                    and (session_root / "important.index.enc").exists()
                    and (session_root / "relationship.index.enc").exists()
                ):
                    raise RuntimeError("state write failed")
                original_atomic_write_json(target, payload)

            with patch.object(private_memory_vault_module, "atomic_write_json", side_effect=failing_atomic_write_json):
                with self.assertRaisesRegex(RuntimeError, "state write failed"):
                    vault.append_event(
                        "session-1",
                        "decision",
                        {"text": "Ship Anvil.", "project": "Anvil", "important": True},
                        timestamp="2026-06-06T12:00:00Z",
                    )

            self.assertTrue((session_root / "journal" / "000001.event.enc").exists())
            stale_state = self._decrypt_state(vault, "session-1")
            self.assertEqual(stale_state["last_sequence"], 0)
            self.assertEqual(stale_state["last_ciphertext_sha256"], "")

            rebuilt = vault.read_active_indexes("session-1")
            self.assertEqual(len(rebuilt["search"]["events"]), 1)

            recovered_state = self._decrypt_state(vault, "session-1")
            self.assertEqual(recovered_state["last_sequence"], 1)
            self.assertRegex(recovered_state["last_ciphertext_sha256"], r"^[0-9a-f]{64}$")
            self.assertFalse(recovered_state["indexes_need_rebuild"])

            second = vault.append_event(
                "session-1",
                "note",
                {"text": "Boss requested a follow-up.", "user": "Boss"},
                timestamp="2026-06-06T12:05:00+00:00",
            )
            self.assertEqual(second["sequence"], 2)
            self.assertEqual(vault.verify_active_session("session-1")["last_sequence"], 2)

    def test_live_indexes_capture_search_topics_importance_and_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._make_vault(Path(tmp))
            vault.initialize()

            important = vault.append_event(
                "session-1",
                "decision",
                {
                    "text": "We decided to ship Project Anvil immediately.",
                    "project": "Anvil",
                    "topics": ["launch", "priority"],
                    "agent": "helper-alpha",
                    "counterpart_agent": "helper-beta",
                    "important": True,
                    "summary": "Ship Anvil now.",
                },
                timestamp="2026-06-06T12:00:00+00:00",
            )
            ordinary = vault.append_event(
                "session-1",
                "note",
                {
                    "text": "Boss asked helper-alpha for a checklist.",
                    "user": "Boss",
                    "agent": "helper-alpha",
                    "topics": ["checklist"],
                },
                timestamp="2026-06-06T12:10:00+00:00",
            )

            indexes = vault.read_active_indexes("session-1")
            search = indexes["search"]
            important_index = indexes["important"]
            relationships = indexes["relationships"]

            self.assertEqual(search["terms"]["anvil"], [important["event_id"]])
            self.assertEqual(search["terms"]["helper"], [important["event_id"], ordinary["event_id"]])
            self.assertEqual(search["topics"]["launch"], [important["event_id"]])
            self.assertEqual(search["topics"]["checklist"], [ordinary["event_id"]])
            self.assertEqual(
                search["events"][important["event_id"]],
                {
                    "sequence": 1,
                    "timestamp": "2026-06-06T12:00:00+00:00",
                    "event_type": "decision",
                },
            )

            self.assertEqual(important_index["event_ids"], [important["event_id"]])
            self.assertEqual(important_index["events"][important["event_id"]]["level"], "high")
            self.assertIn("manual", important_index["events"][important["event_id"]]["reason_codes"])
            self.assertLessEqual(len(important_index["events"][important["event_id"]]["summary"]), 400)

            self.assertEqual(
                relationships["agent"]["helper-alpha"]["interaction_count"],
                2,
            )
            self.assertEqual(
                relationships["agent"]["helper-beta"]["interaction_count"],
                1,
            )
            self.assertEqual(
                relationships["agent"]["helper-alpha"]["significant_event_ids"],
                [important["event_id"]],
            )
            self.assertEqual(
                relationships["agent"]["helper-beta"]["significant_event_ids"],
                [important["event_id"]],
            )
            self.assertEqual(
                relationships["project"]["Anvil"]["significant_event_ids"],
                [important["event_id"]],
            )

    def test_verify_active_session_rejects_deleted_swapped_replayed_corrupt_and_extra_journal_artifacts(self) -> None:
        def build_session(root: Path) -> PrivateMemoryVault:
            vault = self._make_vault(root)
            vault.initialize()
            vault.append_event(
                "session-1",
                "decision",
                {"text": "first secret", "project": "Anvil"},
                timestamp="2026-06-06T12:00:00+00:00",
            )
            vault.append_event(
                "session-1",
                "note",
                {"text": "second secret", "user": "Boss"},
                timestamp="2026-06-06T12:05:00+00:00",
            )
            vault.append_event(
                "session-1",
                "note",
                {"text": "third secret", "user": "Boss"},
                timestamp="2026-06-06T12:10:00+00:00",
            )
            return vault

        with tempfile.TemporaryDirectory() as tmp:
            vault = build_session(Path(tmp))
            first_path = vault.agent_root / "active" / "session-1" / "journal" / "000001.event.enc"
            first_path.unlink()
            with self.assertRaisesRegex(ValueError, "missing|sequence|journal"):
                vault.verify_active_session("session-1")

        with tempfile.TemporaryDirectory() as tmp:
            vault = build_session(Path(tmp))
            journal_root = vault.agent_root / "active" / "session-1" / "journal"
            first_blob = (journal_root / "000001.event.enc").read_bytes()
            second_blob = (journal_root / "000002.event.enc").read_bytes()
            atomic_write_bytes(journal_root / "000001.event.enc", second_blob)
            atomic_write_bytes(journal_root / "000002.event.enc", first_blob)
            with self.assertRaisesRegex(ValueError, "sequence|hash|metadata|authentication"):
                vault.verify_active_session("session-1")

        with tempfile.TemporaryDirectory() as tmp:
            vault = build_session(Path(tmp))
            journal_root = vault.agent_root / "active" / "session-1" / "journal"
            atomic_write_bytes(
                journal_root / "000003.event.enc",
                (journal_root / "000001.event.enc").read_bytes(),
            )
            with self.assertRaisesRegex(ValueError, "replay|hash|metadata|sequence|authentication"):
                vault.verify_active_session("session-1")

        with tempfile.TemporaryDirectory() as tmp:
            vault = build_session(Path(tmp))
            third_path = vault.agent_root / "active" / "session-1" / "journal" / "000003.event.enc"
            payload = json.loads(third_path.read_text("utf-8"))
            payload["envelope"]["ciphertext_b64"] = base64.b64encode(b"corrupt").decode("ascii")
            atomic_write_json(third_path, payload)
            with self.assertRaisesRegex(ValueError, "authentication|digest"):
                vault.verify_active_session("session-1")

        with tempfile.TemporaryDirectory() as tmp:
            vault = build_session(Path(tmp))
            journal_root = vault.agent_root / "active" / "session-1" / "journal"
            extra = json.loads((journal_root / "000003.event.enc").read_text("utf-8"))
            extra["sequence"] = 4
            atomic_write_json(journal_root / "000004.event.enc", extra)
            with self.assertRaisesRegex(ValueError, "extra|sequence|journal"):
                vault.verify_active_session("session-1")

    def test_missing_or_corrupt_indexes_rebuild_from_journal_and_clear_state_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._make_vault(Path(tmp))
            vault.initialize()
            important = vault.append_event(
                "session-1",
                "decision",
                {"text": "We decided to ship Anvil.", "project": "Anvil", "important": True},
                timestamp="2026-06-06T12:00:00+00:00",
            )
            vault.append_event(
                "session-1",
                "note",
                {"text": "Boss asked for status.", "user": "Boss"},
                timestamp="2026-06-06T12:05:00+00:00",
            )

            session_root = vault.agent_root / "active" / "session-1"
            (session_root / "search.index.enc").unlink()
            atomic_write_json(session_root / "important.index.enc", {"broken": True})

            state = self._decrypt_state(vault, "session-1")
            state["indexes_need_rebuild"] = True
            atomic_write_json(
                session_root / "session.state.enc",
                encrypt_json(
                    state,
                    vault._key,
                    private_memory_vault_module._artifact_aad(
                        owner_agent_id=vault.agent_id,
                        artifact_kind="session.state",
                        session_id="session-1",
                    ),
                ),
            )

            indexes = vault.read_active_indexes("session-1")
            self.assertEqual(indexes["important"]["event_ids"], [important["event_id"]])
            self.assertEqual(indexes["relationships"]["project"]["Anvil"]["interaction_count"], 1)
            self.assertFalse(self._decrypt_state(vault, "session-1")["indexes_need_rebuild"])

    def test_timestamp_must_be_utc_aware_and_z_normalizes_to_plus_00_00(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._make_vault(Path(tmp))
            vault.initialize()

            vault.append_event(
                "session-1",
                "note",
                {"text": "Normalized UTC timestamp."},
                timestamp="2026-06-06T12:00:00Z",
            )
            indexes = vault.read_active_indexes("session-1")
            only_event_id = next(iter(indexes["search"]["events"]))
            self.assertEqual(
                indexes["search"]["events"][only_event_id]["timestamp"],
                "2026-06-06T12:00:00+00:00",
            )

            for bad_timestamp in (
                "2026-06-06T12:00:00",
                "2026-06-06T12:00:00-04:00",
                "not-a-time",
            ):
                with self.assertRaisesRegex(ValueError, "timestamp"):
                    vault.append_event(
                        "session-2",
                        "note",
                        {"text": "bad"},
                        timestamp=bad_timestamp,
                    )

    def test_event_write_failure_does_not_advance_sequence_or_create_journal_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._make_vault(Path(tmp))
            vault.initialize()
            original_atomic_write_json = private_memory_vault_module.atomic_write_json

            def failing_atomic_write_json(path: Path, payload: object) -> None:
                if Path(path).name.endswith(".event.enc"):
                    raise RuntimeError("event write failed")
                original_atomic_write_json(path, payload)

            with patch.object(private_memory_vault_module, "atomic_write_json", side_effect=failing_atomic_write_json):
                with self.assertRaisesRegex(RuntimeError, "event write failed"):
                    vault.append_event(
                        "session-1",
                        "note",
                        {"text": "vault-secret-phrase"},
                        timestamp="2026-06-06T12:00:00+00:00",
                    )

            session_root = vault.agent_root / "active" / "session-1"
            self.assertFalse((session_root / "journal").exists())
            self.assertEqual(self._decrypt_state(vault, "session-1")["last_sequence"], 0)

    def test_index_write_failure_preserves_event_advances_state_marks_rebuild_and_next_read_repairs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._make_vault(Path(tmp))
            vault.initialize()
            original_atomic_write_json = private_memory_vault_module.atomic_write_json

            def failing_atomic_write_json(path: Path, payload: object) -> None:
                if Path(path).name == "search.index.enc":
                    raise RuntimeError("index write failed")
                original_atomic_write_json(path, payload)

            with patch.object(private_memory_vault_module, "atomic_write_json", side_effect=failing_atomic_write_json):
                with self.assertRaisesRegex(RuntimeError, "index write failed"):
                    vault.append_event(
                        "session-1",
                        "decision",
                        {"text": "Ship Anvil.", "project": "Anvil", "important": True},
                        timestamp="2026-06-06T12:00:00+00:00",
                    )

            session_root = vault.agent_root / "active" / "session-1"
            self.assertTrue((session_root / "journal" / "000001.event.enc").exists())
            state = self._decrypt_state(vault, "session-1")
            self.assertEqual(state["last_sequence"], 1)
            self.assertTrue(state["indexes_need_rebuild"])

            indexes = vault.read_active_indexes("session-1")
            self.assertFalse(self._decrypt_state(vault, "session-1")["indexes_need_rebuild"])
            self.assertEqual(list(indexes["relationships"]["project"].keys()), ["Anvil"])

    def test_late_index_write_failures_leave_mixed_indexes_and_next_read_rebuilds_all_consistently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for failing_name in ("important.index.enc", "relationship.index.enc"):
                with self.subTest(failing_name=failing_name):
                    root = Path(tmp) / failing_name.replace(".", "-")
                    root.mkdir(parents=True, exist_ok=True)
                    vault = self._make_vault(root)
                    vault.initialize()
                    original_atomic_write_json = private_memory_vault_module.atomic_write_json

                    def failing_atomic_write_json(path: Path, payload: object) -> None:
                        if Path(path).name == failing_name:
                            raise RuntimeError(f"{failing_name} write failed")
                        original_atomic_write_json(path, payload)

                    with patch.object(
                        private_memory_vault_module,
                        "atomic_write_json",
                        side_effect=failing_atomic_write_json,
                    ):
                        with self.assertRaisesRegex(RuntimeError, failing_name):
                            vault.append_event(
                                "session-1",
                                "decision",
                                {"text": "Ship Anvil now.", "project": "Anvil", "important": True},
                                timestamp="2026-06-06T12:00:00+00:00",
                            )

                    session_root = vault.agent_root / "active" / "session-1"
                    self.assertTrue((session_root / "journal" / "000001.event.enc").exists())
                    self.assertTrue((session_root / "search.index.enc").exists())
                    self.assertTrue(self._decrypt_state(vault, "session-1")["indexes_need_rebuild"])

                    indexes = vault.read_active_indexes("session-1")
                    self.assertEqual(list(indexes["search"]["events"].values())[0]["sequence"], 1)
                    self.assertEqual(indexes["important"]["event_ids"], [next(iter(indexes["important"]["events"]))])
                    self.assertEqual(indexes["relationships"]["project"]["Anvil"]["interaction_count"], 1)
                    self.assertFalse(self._decrypt_state(vault, "session-1")["indexes_need_rebuild"])

    def test_descriptor_validation_rejects_sibling_rebound_unverified_and_bad_digest_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = self._make_vault(root)
            descriptor = vault.initialize()

            with self.assertRaisesRegex(ValueError, "verified"):
                validate_private_memory_descriptor(
                    {**descriptor, "verified": False},
                    expected_agent_id="scribe",
                    vault_root=root,
                    verification_key=self._verification_key(),
                )
            with self.assertRaisesRegex(ValueError, "64 hex"):
                validate_private_memory_descriptor(
                    {**descriptor, "attestation_sha256": "bad-digest"},
                    expected_agent_id="scribe",
                    vault_root=root,
                    verification_key=self._verification_key(),
                )
            with self.assertRaisesRegex(ValueError, "path mismatch|escape"):
                validate_private_memory_descriptor(
                    {**descriptor, "ciphertext_ref": str((root / "sibling" / "vault.manifest.enc").resolve())},
                    expected_agent_id="scribe",
                    vault_root=root,
                    verification_key=self._verification_key(),
                )
            with self.assertRaisesRegex(ValueError, "owner_agent_id"):
                validate_private_memory_descriptor(
                    {**descriptor, "owner_agent_id": "other"},
                    expected_agent_id="scribe",
                    vault_root=root,
                    verification_key=self._verification_key(),
                )

    def test_descriptor_validation_rejects_forged_attestation_signature_when_verification_key_supplied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = self._make_vault(root)
            descriptor = vault.initialize()
            attestation_path = root / "scribe" / "vault.attestation.json"
            attestation = json.loads(attestation_path.read_text("utf-8"))
            attestation["signature"] = "0" * 64
            atomic_write_json(attestation_path, attestation)
            forged_descriptor = {
                **descriptor,
                "attestation_sha256": hashlib.sha256(attestation_path.read_bytes()).hexdigest(),
            }

            with self.assertRaisesRegex(ValueError, "signature"):
                validate_private_memory_descriptor(
                    forged_descriptor,
                    expected_agent_id="scribe",
                    vault_root=root,
                    verification_key=self._verification_key(),
                )

    def test_symlinked_owner_directory_is_rejected_and_validation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            outside = Path(tmp) / "outside"
            root.mkdir()
            outside.mkdir()
            owner_link = root / "scribe"
            try:
                owner_link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable on this host")

            vault = self._make_vault(root)
            with self.assertRaisesRegex(ValueError, "symlink|outside|escape"):
                vault.initialize()
            self.assertEqual(list(outside.iterdir()), [])

            descriptor = {
                "schema_version": "1.0",
                "owner_agent_id": "scribe",
                "ciphertext_ref": str((owner_link / "vault.manifest.enc").resolve()),
                "attestation_sha256": "0" * 64,
                "key_ref": "key-2026-06",
                "verified": True,
            }
            with self.assertRaisesRegex(ValueError, "symlink|outside|escape|path mismatch"):
                validate_private_memory_descriptor(
                    descriptor,
                    expected_agent_id="scribe",
                    vault_root=root,
                    verification_key=self._verification_key(),
                )

    def test_descriptor_validation_rejects_mocked_resolved_owner_escape_without_symlink_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            vault = self._make_vault(root)
            descriptor = vault.initialize()

            outside_owner = Path(tmp) / "outside-owner"
            outside_owner.mkdir()
            (outside_owner / "vault.manifest.enc").write_bytes((root / "scribe" / "vault.manifest.enc").read_bytes())
            (outside_owner / "vault.attestation.json").write_bytes((root / "scribe" / "vault.attestation.json").read_bytes())

            original_resolve = private_memory_vault_module.Path.resolve
            owner_path = root / "scribe"
            owner_manifest = owner_path / "vault.manifest.enc"
            owner_attestation = owner_path / "vault.attestation.json"

            def fake_resolve(path_obj: Path, strict: bool = False) -> Path:
                raw = Path(path_obj)
                if raw == owner_path:
                    return outside_owner
                if raw == owner_manifest:
                    return outside_owner / "vault.manifest.enc"
                if raw == owner_attestation:
                    return outside_owner / "vault.attestation.json"
                return original_resolve(raw, strict=strict)

            with patch.object(private_memory_vault_module.Path, "resolve", autospec=True, side_effect=fake_resolve):
                with self.assertRaisesRegex(ValueError, "outside|escape|rebind|owner"):
                    validate_private_memory_descriptor(
                        descriptor,
                        expected_agent_id="scribe",
                        vault_root=root,
                        verification_key=self._verification_key(),
                    )

    def test_windows_junction_owner_rebinding_is_rejected_when_available(self) -> None:
        import os

        if os.name != "nt":
            self.skipTest("junction regression only applies on Windows")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            source_root = Path(tmp) / "source"
            outside = Path(tmp) / "outside"
            root.mkdir()
            source_root.mkdir()
            outside.mkdir()

            source_vault = self._make_vault(source_root)
            source_descriptor = source_vault.initialize()

            junction_path = root / "scribe"
            from subprocess import run

            mklink = run(
                ["cmd", "/c", "mklink", "/J", str(junction_path), str(outside)],
                capture_output=True,
                text=True,
            )
            if mklink.returncode != 0:
                self.skipTest("mklink /J unavailable on this host")

            (outside / "vault.manifest.enc").write_bytes((source_root / "scribe" / "vault.manifest.enc").read_bytes())
            (outside / "vault.attestation.json").write_bytes(
                (source_root / "scribe" / "vault.attestation.json").read_bytes()
            )

            rebound_descriptor = {
                **source_descriptor,
                "ciphertext_ref": str(junction_path / "vault.manifest.enc"),
                "attestation_sha256": hashlib.sha256((outside / "vault.attestation.json").read_bytes()).hexdigest(),
            }

            rebound_vault = self._make_vault(root)
            with self.assertRaisesRegex(ValueError, "outside|escape|rebind|owner|reparse|symlink"):
                rebound_vault.initialize()
            with self.assertRaisesRegex(ValueError, "outside|escape|rebind|owner|reparse|symlink"):
                validate_private_memory_descriptor(
                    rebound_descriptor,
                    expected_agent_id="scribe",
                    vault_root=root,
                    verification_key=self._verification_key(),
                )

    def test_initialize_fails_if_persisted_manifest_or_attestation_is_corrupted_after_write(self) -> None:
        def run_case(root: Path, corrupt_name: str) -> None:
            vault = self._make_vault(root)
            original_atomic_write_json = private_memory_vault_module.atomic_write_json

            def corrupting_atomic_write_json(path: Path, payload: object) -> None:
                target = Path(path)
                original_atomic_write_json(target, payload)
                if target.name == corrupt_name:
                    target.write_text("{\"corrupt\":true}", encoding="utf-8")

            with patch.object(
                private_memory_vault_module,
                "atomic_write_json",
                side_effect=corrupting_atomic_write_json,
            ):
                with self.assertRaisesRegex(ValueError, "manifest|attestation|authentication|metadata|signature"):
                    vault.initialize()

        with tempfile.TemporaryDirectory() as tmp:
            run_case(Path(tmp) / "manifest", "vault.manifest.enc")
            run_case(Path(tmp) / "attestation", "vault.attestation.json")

    def test_concurrent_appends_produce_contiguous_unique_sequences_and_valid_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._make_vault(Path(tmp))
            vault.initialize()

            results: list[dict] = []
            errors: list[Exception] = []
            lock = threading.Lock()

            def worker(index: int) -> None:
                try:
                    result = vault.append_event(
                        "session-1",
                        "note",
                        {"text": f"event {index}", "user": "Boss"},
                    )
                    with lock:
                        results.append(result)
                except Exception as exc:  # pragma: no cover - diagnostic path
                    with lock:
                        errors.append(exc)

            threads = [threading.Thread(target=worker, args=(index,)) for index in range(10)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            self.assertEqual(sorted(item["sequence"] for item in results), list(range(1, 11)))
            self.assertEqual(len({item["event_id"] for item in results}), 10)
            self.assertEqual(vault.verify_active_session("session-1")["last_sequence"], 10)

    def test_no_plaintext_secret_appears_in_journal_index_state_or_manifest_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = self._make_vault(root)
            vault.initialize()
            vault.append_event(
                "session-1",
                "decision",
                {
                    "text": "customer-secret-token should never appear plaintext",
                    "reason": "customer-secret-token",
                    "project": "Anvil",
                    "important": True,
                },
                timestamp="2026-06-06T12:00:00+00:00",
            )

            for file_path in (root / "scribe").rglob("*"):
                if file_path.is_file():
                    self.assertNotIn(b"customer-secret-token", file_path.read_bytes(), str(file_path))


if __name__ == "__main__":
    unittest.main()
