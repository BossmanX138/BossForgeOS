"""Publicly verifiable approval assertions; all keys here are test-only."""
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.bossgate.notifications import canonical_json_bytes
from core.bossgate.repair_approval import (
    build_repair_approval_assertion, verify_repair_approval_assertion,
)


class RepairApprovalTests(unittest.TestCase):
    now = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)
    binding = {"account_id": "account-1", "device_id": "device-1", "source_gate": "archivist-gate",
               "repair_job_id": "repair-1", "proposal_version": "1", "proposal_digest": "a" * 64,
               "project_fingerprint": "b" * 64, "action": "approve_repair"}
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    private_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode("ascii")
    public_pem = key.public_key().public_bytes(serialization.Encoding.PEM,
                                              serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")
    public_keys = {"approval-test-1": public_pem}

    def assertion(self, **overrides):
        args = dict(binding=self.binding, private_key_pem=self.private_pem,
                    key_id="approval-test-1", nonce="approval-test-nonce-1", at=self.now)
        args.update(overrides)
        return build_repair_approval_assertion(**args)

    def verify(self, assertion, **overrides):
        args = dict(public_keys=self.public_keys, expected=self.binding, at=self.now)
        args.update(overrides)
        return verify_repair_approval_assertion(assertion, **args)

    def sign(self, assertion):
        assertion["signature"] = base64.b64encode(self.key.sign(canonical_json_bytes(
            {key: value for key, value in assertion.items() if key != "signature"}))).decode("ascii")
        return assertion

    def test_assertion_round_trip_binds_every_approval_field(self):
        assertion = self.assertion(binding=MappingProxyType(self.binding))
        self.assertEqual(assertion["schema"], "bosscrafts.bossgate.repair-approval.v1")
        self.assertEqual({key: assertion[key] for key in self.binding}, self.binding)
        self.assertEqual(assertion["created_at"], "2026-10-23T12:00:00Z")
        self.assertEqual(assertion["expires_at"], "2026-10-23T12:01:00Z")
        self.assertEqual(len(base64.b64decode(assertion["signature"], validate=True)), 64)
        self.assertEqual(self.verify(MappingProxyType(assertion)), (True, "ok"))
        # An independent Ed25519 consumer needs only the public key and canonical JSON.
        self.key.public_key().verify(base64.b64decode(assertion["signature"]),
            json.dumps({k: v for k, v in assertion.items() if k != "signature"},
                       sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode())

    def test_assertion_expires_after_60_seconds(self):
        assertion = self.assertion()
        self.assertEqual(self.verify(assertion, at=self.now + timedelta(seconds=59)), (True, "ok"))
        self.assertFalse(self.verify(assertion, at=self.now + timedelta(seconds=60))[0])
        self.assertFalse(self.verify(assertion, at=self.now - timedelta(microseconds=1))[0])

    def test_builder_clamps_ttl_to_one_through_sixty_seconds(self):
        for ttl, seconds in ((-5, 1), (0, 1), (1, 1), (30, 30), (60, 60), (1000, 60)):
            with self.subTest(ttl=ttl):
                assertion = self.assertion(ttl_seconds=ttl)
                self.assertEqual(assertion["expires_at"],
                                 (self.now + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z"))
        for ttl in (True, "60", 1.5, None):
            with self.assertRaises(ValueError):
                self.assertion(ttl_seconds=ttl)

    def test_assertion_rejects_wrong_public_key(self):
        other = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32)))).public_key()
        pem = other.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        for keys in ({"approval-test-1": pem}, {}, {"other-id": self.public_pem},
                     {"approval-test-1": "bad-pem"}, {"approval-test-1": self.private_pem}, None):
            with self.subTest(keys=type(keys).__name__):
                self.assertFalse(self.verify(self.assertion(), public_keys=keys)[0])

    def test_assertion_rejects_each_wrong_expected_binding(self):
        assertion = self.assertion()
        for field in self.binding:
            with self.subTest(field=field):
                self.assertFalse(self.verify(assertion, expected={**self.binding, field: "wrong"})[0])
                changed = {**assertion, field: "c" * 64 if field in ("proposal_digest", "project_fingerprint") else "changed"}
                self.assertFalse(self.verify(changed)[0])
                if field != "action":
                    self.assertFalse(self.verify(self.sign(changed))[0])

    def test_assertion_rejects_replayed_nonce(self):
        consumed = set()
        assertion = self.assertion()
        self.assertEqual(self.verify(assertion, consumed_nonces=consumed), (True, "ok"))
        self.assertEqual(consumed, {assertion["nonce"]})
        self.assertFalse(self.verify(assertion, consumed_nonces=consumed)[0])

    def test_failed_validation_does_not_consume_nonce(self):
        consumed = set()
        assertion = self.assertion()
        cases = [({**assertion, "signature": base64.b64encode(bytes(64)).decode()}, {}),
                 (assertion, {"expected": {**self.binding, "account_id": "wrong"}}),
                 (assertion, {"at": self.now + timedelta(seconds=60)}),
                 (assertion, {"public_keys": {}})]
        for changed, overrides in cases:
            self.assertFalse(self.verify(changed, consumed_nonces=consumed, **overrides)[0])
            self.assertEqual(consumed, set())
        self.assertEqual(self.verify(assertion, consumed_nonces=consumed), (True, "ok"))

    def test_canonical_signature_survives_dictionary_reordering(self):
        assertion = self.assertion()
        reordered = json.loads(json.dumps(dict(reversed(list(assertion.items()))), indent=4))
        self.assertEqual(self.verify(reordered, expected=dict(reversed(list(self.binding.items())))), (True, "ok"))
        self.assertEqual(self.assertion(binding=dict(reversed(list(self.binding.items())))), assertion)

    def test_assertion_rejects_missing_unknown_or_malformed_fields(self):
        assertion = self.assertion()
        for field in assertion:
            for value in (None, False, 1, "", " "):
                with self.subTest(field=field, value=value):
                    self.assertFalse(self.verify({**assertion, field: value})[0])
            missing = dict(assertion)
            del missing[field]
            self.assertFalse(self.verify(missing)[0])
        for malformed in (None, [], {**assertion, "unexpected": "field"}):
            self.assertFalse(self.verify(malformed)[0])
        for field in self.binding:
            incomplete = dict(self.binding)
            del incomplete[field]
            self.assertFalse(self.verify(assertion, expected=incomplete)[0])
            with self.assertRaises(ValueError):
                self.assertion(binding=incomplete)
        self.assertFalse(self.verify(assertion, expected={**self.binding, "unexpected": "field"})[0])
        with self.assertRaises(ValueError):
            self.assertion(binding={**self.binding, "unexpected": "field"})

    def test_authenticated_invalid_time_action_digests_and_signature_are_rejected(self):
        assertion = self.assertion()
        for field, value in (("created_at", "2026-10-23T12:00:00+00:00"),
                             ("created_at", "2026-10-23t12:00:00z"),
                             ("created_at", "2026-02-30T12:00:00Z"),
                             ("expires_at", "2026-10-23T12:00:00Z"),
                             ("expires_at", "2026-10-23T12:01:01Z"),
                             ("action", "reject_repair"), ("proposal_digest", "A" * 64),
                             ("project_fingerprint", "not-a-digest"), ("key_id", " approval-test-1 ")):
            with self.subTest(field=field, value=value):
                self.assertFalse(self.verify(self.sign({**assertion, field: value}))[0])
        for signature in ("!" + assertion["signature"], assertion["signature"] + "\n",
                          assertion["signature"] + "=", base64.b64encode(b"short").decode()):
            self.assertFalse(self.verify({**assertion, "signature": signature})[0])
        with self.assertRaises(ValueError):
            self.assertion(at=datetime(2026, 10, 23, 12))
        with self.assertRaises(ValueError):
            self.assertion(private_key_pem=self.public_pem)

    def test_generated_nonces_are_distinct(self):
        self.assertNotEqual(self.assertion(nonce=None)["nonce"], self.assertion(nonce=None)["nonce"])

    def test_golden_approval_has_stable_hash_public_signature_and_schema(self):
        import jsonschema
        root = Path(__file__).resolve().parents[1]
        fixture = json.loads((root / "tests/fixtures/bossgate_repair_approval_v1.json").read_text())
        assertion = fixture["assertion"]
        self.assertEqual(assertion["source_gate"], "archivist-gate")
        self.assertEqual(fixture["expected"], self.binding)
        serialized = json.dumps(assertion, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
        self.assertEqual(hashlib.sha256(serialized).hexdigest(), fixture["canonical_sha256"])
        self.assertEqual(self.assertion(), assertion)
        self.assertEqual(verify_repair_approval_assertion(assertion, fixture["public_keys"], self.binding,
                                                       at=self.now), (True, "ok"))
        schema = json.loads((root / "schemas/bossgate_repair_approval_v1.schema.json").read_text())
        validator = jsonschema.Draft7Validator(schema, format_checker=jsonschema.FormatChecker())
        self.assertEqual(list(validator.iter_errors(assertion)), [])
        for field in assertion:
            changed = deepcopy(assertion)
            del changed[field]
            self.assertTrue(list(validator.iter_errors(changed)), field)
        self.assertTrue(list(validator.iter_errors({**assertion, "extra": "field"})))


if __name__ == "__main__":
    unittest.main()
