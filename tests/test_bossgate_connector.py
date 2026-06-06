import hashlib
import hmac
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from core.connectors.bossgate_connector import (
    ALLOWED_TRAVEL_TARGET_TYPES,
    apply_metadata_visibility_profile,
    build_chunk_manifest,
    build_transfer_resume_plan,
    build_transfer_envelope,
    classify_target_type,
    decrypt_json_payload,
    discover_transfer_targets,
    encrypt_json_payload,
    generate_secure_address,
    is_valid_secure_address,
    is_valid_transfer_target,
    scan_rest_endpoints,
    validate_transfer_envelope,
    validate_chunk_manifest,
    validate_transfer_resume_plan,
)


class BossGateConnectorTargetValidationTests(unittest.TestCase):
    def test_classify_target_type_allows_bossforgeos(self) -> None:
        target_type = classify_target_type({"title": "BossForgeOS Node", "description": "BossForge OS runtime"})
        self.assertEqual(target_type, "bossforgeos")

    def test_is_valid_transfer_target_rejects_unknown(self) -> None:
        allowed, target_type = is_valid_transfer_target({"title": "Random IoT Device"})
        self.assertFalse(allowed)
        self.assertEqual(target_type, "unknown")

    @patch("core.connectors.bossgate_connector._http_get_json")
    @patch("core.connectors.bossgate_connector._http_get_headers")
    def test_scan_rest_endpoints_rejects_non_allowlisted_target(self, mock_get_headers, mock_get_json) -> None:
        mock_get_headers.return_value = (
            200,
            {
                "Server": "generic-proxy",
                "X-Powered-By": "random-stack",
                "X-BossGate-Role": "",
                "X-BossGate-Target-Type": "",
            },
        )
        mock_get_json.return_value = (
            200,
            {"Content-Type": "application/json"},
            {
                "info": {"title": "Device API", "description": "Not a travel destination"},
                "paths": {"/health": {"get": {}}},
            },
        )

        result = scan_rest_endpoints("http://example.com")
        self.assertFalse(result["ok"])
        self.assertFalse(result["allowed_for_transfer"])
        self.assertEqual(result["target_type"], "unknown")
        self.assertEqual(result["endpoints"], [])

    @patch("core.connectors.bossgate_connector._http_get_json")
    @patch("core.connectors.bossgate_connector._http_get_headers")
    def test_scan_rest_endpoints_allows_bridgebase_alpha(self, mock_get_headers, mock_get_json) -> None:
        mock_get_headers.return_value = (
            200,
            {
                "Server": "bridgebase-alpha-gateway",
                "X-Powered-By": "bossforge",
                "X-BossGate-Role": "bridgebase_alpha",
                "X-BossGate-Target-Type": "bridgebase_alpha",
            },
        )

        mock_get_json.return_value = (
            200,
            {"Content-Type": "application/json"},
            {
                "info": {"title": "bridgebase_alpha control plane", "description": "BossGate travel node"},
                "paths": {"/api/transfer": {"post": {}}, "/health": {"get": {}}},
            },
        )

        result = scan_rest_endpoints("example.com")
        self.assertTrue(result["ok"])
        self.assertTrue(result["allowed_for_transfer"])
        self.assertIn(result["target_type"], ALLOWED_TRAVEL_TARGET_TYPES)
        self.assertGreaterEqual(len(result["endpoints"]), 1)

    @patch("core.connectors.bossgate_connector.listen_for_beacons")
    def test_discover_transfer_targets_assistance_only(self, mock_listen_for_beacons) -> None:
        mock_listen_for_beacons.return_value = [
            {
                "address": "10.0.0.9",
                "node_id": "node-9",
                "target_type": "bossgate_connector",
                "agents": [
                    {
                        "name": "alpha",
                        "agent_class": "prime",
                        "bossgate_enabled": True,
                        "created_by_node": "owner-1",
                        "current_node": "node-9",
                        "assistance_requested": True,
                        "assistance_reason": "Need triage",
                    },
                    {
                        "name": "beta",
                        "agent_class": "core",
                        "bossgate_enabled": True,
                        "created_by_node": "owner-2",
                        "current_node": "node-9",
                        "assistance_requested": False,
                        "assistance_reason": "",
                    },
                ],
            }
        ]

        targets = discover_transfer_targets(timeout=3, assistance_only=True)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["agent_name"], "alpha")
        self.assertTrue(targets[0]["assistance_requested"])
        self.assertTrue(targets[0]["allowed_for_transfer"])
        self.assertEqual(targets[0]["created_by_node"], "owner-1")
        self.assertEqual(targets[0]["current_node"], "node-9")


class BossGateProtocolPrimitivesTests(unittest.TestCase):
    def _resign_envelope(self, envelope: dict, secret_key: str) -> None:
        unsigned = {key: value for key, value in envelope.items() if key != "signature"}
        envelope["signature"] = hmac.new(
            secret_key.encode("utf-8"),
            hashlib.sha256(
                json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest().encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def test_generate_secure_address_uses_required_format(self) -> None:
        address = generate_secure_address(wordlist=["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf"])
        self.assertTrue(is_valid_secure_address(address))

    def test_metadata_visibility_profile_hides_unselected_sections(self) -> None:
        profile = apply_metadata_visibility_profile(
            "id_card_only",
            agent_id_card={"agent_id": "a-1"},
            model_card_snapshot={"model_family": "x"},
        )
        self.assertEqual(profile["profile"], "id_card_only")
        self.assertEqual(profile["agent_id_card"], {"agent_id": "a-1"})
        self.assertIsNone(profile["model_card_snapshot"])

    def test_transfer_envelope_build_and_validate(self) -> None:
        envelope = build_transfer_envelope(
            agent_id="agent-1",
            agent_version="1.0.0",
            issuer="bossforge-node",
            target_system_id="bridgebase-alpha-01",
            encrypted_payload="ZW5jcnlwdGVk",
            policy_ref="policy/default",
            secret_key="super-secret",
            expires_in_seconds=120,
        )
        ok, reason = validate_transfer_envelope(envelope, secret_key="super-secret")
        self.assertTrue(ok, reason)

    def test_transfer_envelope_rejects_tampered_payload(self) -> None:
        envelope = build_transfer_envelope(
            agent_id="agent-1",
            agent_version="1.0.0",
            issuer="bossforge-node",
            target_system_id="bridgebase-alpha-01",
            encrypted_payload="ZW5jcnlwdGVk",
            policy_ref="policy/default",
            secret_key="super-secret",
            expires_in_seconds=120,
        )
        envelope["encrypted_payload"] = "tampered"
        ok, reason = validate_transfer_envelope(envelope, secret_key="super-secret")
        self.assertFalse(ok)
        self.assertIn("payload hash mismatch", reason)

    def test_chunk_manifest_build_and_validate(self) -> None:
        manifest = build_chunk_manifest("abcdefghij", chunk_size=4)
        self.assertEqual(manifest["chunk_size"], 4)
        self.assertEqual(manifest["chunk_count"], 3)
        self.assertEqual([chunk["size"] for chunk in manifest["chunks"]], [4, 4, 2])
        ok, reason = validate_chunk_manifest("abcdefghij", manifest)
        self.assertTrue(ok, reason)

    def test_transfer_envelope_rejects_corrupted_chunk_manifest(self) -> None:
        envelope = build_transfer_envelope(
            agent_id="agent-1",
            agent_version="1.0.0",
            issuer="bossforge-node",
            target_system_id="bridgebase-alpha-01",
            encrypted_payload="abcdefghij",
            policy_ref="policy/default",
            secret_key="super-secret",
            chunk_size=4,
        )
        envelope["chunk_manifest"]["chunks"][1]["sha256"] = "0" * 64
        ok, reason = validate_transfer_envelope(envelope, secret_key="super-secret")
        self.assertFalse(ok)
        self.assertIn("chunk checksum mismatch at index 1", reason)

    def test_transfer_envelope_accepts_legacy_envelope_without_chunk_manifest(self) -> None:
        envelope = build_transfer_envelope(
            agent_id="agent-1",
            agent_version="1.0.0",
            issuer="bossforge-node",
            target_system_id="bridgebase-alpha-01",
            encrypted_payload="abcdefghij",
            policy_ref="policy/default",
            secret_key="super-secret",
        )
        envelope.pop("chunk_manifest")
        unsigned = {key: value for key, value in envelope.items() if key != "signature"}
        envelope["signature"] = hmac.new(
            b"super-secret",
            hashlib.sha256(
                json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest().encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        ok, reason = validate_transfer_envelope(envelope, secret_key="super-secret")
        self.assertTrue(ok, reason)

    def test_transfer_resume_plan_tracks_completed_and_pending_chunks(self) -> None:
        envelope = build_transfer_envelope(
            agent_id="agent-1",
            agent_version="1.0.0",
            issuer="bossforge-node",
            target_system_id="bridgebase-alpha-01",
            encrypted_payload="abcdefghij",
            policy_ref="policy/default",
            secret_key="super-secret",
            chunk_size=4,
        )
        plan = build_transfer_resume_plan(envelope, completed_chunk_indexes=[0])
        self.assertEqual(plan["completed_chunk_indexes"], [0])
        self.assertEqual(plan["pending_chunk_indexes"], [1, 2])
        self.assertEqual(plan["next_chunk_index"], 1)
        self.assertFalse(plan["complete"])
        ok, reason = validate_transfer_resume_plan(envelope, plan)
        self.assertTrue(ok, reason)

    def test_transfer_resume_plan_rejects_out_of_range_checkpoint(self) -> None:
        envelope = build_transfer_envelope(
            agent_id="agent-1",
            agent_version="1.0.0",
            issuer="bossforge-node",
            target_system_id="bridgebase-alpha-01",
            encrypted_payload="abcdefghij",
            policy_ref="policy/default",
            secret_key="super-secret",
            chunk_size=4,
        )
        with self.assertRaises(ValueError):
            build_transfer_resume_plan(envelope, completed_chunk_indexes=[3])

    def test_transfer_envelope_rejects_replayed_encrypted_nonce(self) -> None:
        encrypted = encrypt_json_payload({"agent": "porter"}, secret_key="super-secret")
        first = build_transfer_envelope(
            agent_id="agent-1",
            agent_version="1.0.0",
            issuer="bossforge-node",
            target_system_id="bridgebase-alpha-01",
            encrypted_payload=encrypted,
            policy_ref="policy/default",
            secret_key="super-secret",
        )
        second = build_transfer_envelope(
            agent_id="agent-1",
            agent_version="1.0.0",
            issuer="bossforge-node",
            target_system_id="bridgebase-alpha-02",
            encrypted_payload=encrypted,
            policy_ref="policy/default",
            secret_key="super-secret",
        )
        replay_tokens = set()
        ok, reason = validate_transfer_envelope(first, secret_key="super-secret", replay_tokens=replay_tokens)
        self.assertTrue(ok, reason)
        ok, reason = validate_transfer_envelope(second, secret_key="super-secret", replay_tokens=replay_tokens)
        self.assertFalse(ok)
        self.assertIn("replay detected", reason)

    def test_transfer_envelope_rejects_expired_envelope(self) -> None:
        envelope = build_transfer_envelope(
            agent_id="agent-1",
            agent_version="1.0.0",
            issuer="bossforge-node",
            target_system_id="bridgebase-alpha-01",
            encrypted_payload="abcdefghij",
            policy_ref="policy/default",
            secret_key="super-secret",
        )
        envelope["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self._resign_envelope(envelope, "super-secret")
        ok, reason = validate_transfer_envelope(envelope, secret_key="super-secret")
        self.assertFalse(ok)
        self.assertIn("envelope expired", reason)

    def test_transfer_envelope_rejects_wrong_signing_key(self) -> None:
        envelope = build_transfer_envelope(
            agent_id="agent-1",
            agent_version="1.0.0",
            issuer="bossforge-node",
            target_system_id="bridgebase-alpha-01",
            encrypted_payload="abcdefghij",
            policy_ref="policy/default",
            secret_key="super-secret",
        )
        ok, reason = validate_transfer_envelope(envelope, secret_key="wrong-secret")
        self.assertFalse(ok)
        self.assertIn("signature mismatch", reason)

    def test_encrypt_decrypt_json_payload_roundtrip(self) -> None:
        payload = {"agent_name": "porter", "n": 1}
        encrypted = encrypt_json_payload(payload, secret_key="k1", key_id="kid-1")
        self.assertIsInstance(encrypted, str)
        decrypted = decrypt_json_payload(encrypted, secret_key={"kid-1": "k1"})
        self.assertEqual(decrypted, payload)

    def test_decrypt_json_payload_rejects_wrong_key(self) -> None:
        payload = {"agent_name": "porter", "n": 1}
        encrypted = encrypt_json_payload(payload, secret_key="k1")
        with self.assertRaises(Exception):
            decrypt_json_payload(encrypted, secret_key="k2")


if __name__ == "__main__":
    unittest.main()
