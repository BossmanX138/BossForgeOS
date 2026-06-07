import unittest
from copy import deepcopy

from core.runner.bossforge_ai_runner import (
    GIFTED_TEMPLATE_VERSION,
    RUNEFORGE_AGENT_ID,
    build_agent_runner_manifest,
    build_runner_bootstrap,
    build_runeforge_origin_manifest,
    build_signed_gifted_template,
    validate_agent_runner_manifest,
    validate_runner_bootstrap,
    verify_signed_template,
)


class BossForgeAIRunnerTests(unittest.TestCase):
    def test_gifted_template_is_signed_and_verifiable(self) -> None:
        template = build_signed_gifted_template()
        self.assertEqual(template["template_id"], "bossforge-ai-runner-neutral")
        self.assertEqual(template["version"], GIFTED_TEMPLATE_VERSION)
        self.assertEqual(template["gifted_by"], RUNEFORGE_AGENT_ID)
        self.assertTrue(template["signature"])
        self.assertTrue(verify_signed_template(template))

    def test_template_signature_rejects_tampering(self) -> None:
        template = build_signed_gifted_template()
        tampered = dict(template)
        tampered["runtime_requirements"] = dict(template["runtime_requirements"])
        tampered["runtime_requirements"]["python"] = "3.99"
        self.assertFalse(verify_signed_template(tampered))

    def test_runeforge_origin_manifest_stays_personalized(self) -> None:
        manifest = build_runeforge_origin_manifest()
        self.assertEqual(manifest["agent_id"], RUNEFORGE_AGENT_ID)
        self.assertEqual(manifest["runner_role"], "personalized_origin")
        self.assertEqual(manifest["source_template"]["ancestor_id"], "")
        self.assertFalse(manifest["depends_on_runeforge_online"])
        validate_agent_runner_manifest(manifest)

    def test_descendant_manifest_is_detached_copy(self) -> None:
        manifest = build_agent_runner_manifest("wayfinder")
        self.assertEqual(manifest["agent_id"], "wayfinder")
        self.assertEqual(manifest["runner_role"], "descendant")
        self.assertEqual(manifest["source_template"]["ancestor_id"], RUNEFORGE_AGENT_ID)
        self.assertEqual(manifest["source_template"]["version"], GIFTED_TEMPLATE_VERSION)
        self.assertTrue(manifest["source_template"]["signature"])
        self.assertTrue(manifest["detached_after_creation"])
        self.assertFalse(manifest["depends_on_runeforge_online"])
        validate_agent_runner_manifest(manifest)

    def test_runner_bootstrap_references_agent_local_runner_and_vaults(self) -> None:
        manifest = build_agent_runner_manifest("wayfinder")
        bootstrap = build_runner_bootstrap("wayfinder", manifest)
        self.assertEqual(bootstrap["agent_id"], "wayfinder")
        self.assertEqual(bootstrap["runner_manifest"]["agent_id"], "wayfinder")
        self.assertEqual(bootstrap["wake_contract"], "bossforge-ai-runner-wake-v1")
        self.assertEqual(bootstrap["vault_bindings"]["runner"], "capsule.vaults.runner")
        self.assertEqual(bootstrap["vault_bindings"]["model"], "capsule.vaults.model")
        validate_runner_bootstrap(bootstrap)

    def test_runner_bootstrap_binds_verified_private_model_package(self) -> None:
        manifest = build_agent_runner_manifest("wayfinder")
        descriptor = {
            "schema_version": "1.0",
            "package_id": "pmv-123",
            "owner_agent_id": "wayfinder",
            "package_path": "F:/vaults/wayfinder/pmv-123",
            "ciphertext_ref": "private_models/wayfinder/pmv-123",
            "attestation_sha256": "a" * 64,
            "key_ref": "agent-model-key:wayfinder",
            "verified": True,
        }

        bootstrap = build_runner_bootstrap("wayfinder", manifest, descriptor)

        self.assertEqual(bootstrap["private_model_package"], descriptor)
        validate_runner_bootstrap(bootstrap)

    def test_runner_bootstrap_binds_verified_private_memory_vault(self) -> None:
        manifest = build_agent_runner_manifest("wayfinder")
        descriptor = {
            "schema_version": "1.0",
            "owner_agent_id": "wayfinder",
            "ciphertext_ref": "private_memory/wayfinder/vault.manifest.enc",
            "attestation_sha256": "b" * 64,
            "key_ref": "node:test:agent:wayfinder:private-memory-v1",
            "verified": True,
        }

        bootstrap = build_runner_bootstrap(
            "wayfinder",
            manifest,
            private_memory_vault=descriptor,
        )

        self.assertEqual(bootstrap["private_memory_vault"], descriptor)
        validate_runner_bootstrap(bootstrap)

    def test_runner_bootstrap_rejects_private_model_owned_by_sibling(self) -> None:
        manifest = build_agent_runner_manifest("wayfinder")
        descriptor = {
            "schema_version": "1.0",
            "package_id": "pmv-123",
            "owner_agent_id": "sibling",
            "package_path": "F:/vaults/sibling/pmv-123",
            "ciphertext_ref": "private_models/sibling/pmv-123",
            "attestation_sha256": "a" * 64,
            "key_ref": "agent-model-key:sibling",
            "verified": True,
        }

        with self.assertRaisesRegex(ValueError, "owner"):
            build_runner_bootstrap("wayfinder", manifest, descriptor)

    def test_runner_bootstrap_rejects_private_memory_owned_by_sibling(self) -> None:
        manifest = build_agent_runner_manifest("wayfinder")
        descriptor = {
            "schema_version": "1.0",
            "owner_agent_id": "other-agent",
            "ciphertext_ref": "private_memory/other-agent/vault.manifest.enc",
            "attestation_sha256": "b" * 64,
            "key_ref": "node:test:agent:other-agent:private-memory-v1",
            "verified": True,
        }

        with self.assertRaisesRegex(ValueError, "owner"):
            build_runner_bootstrap("wayfinder", manifest, private_memory_vault=descriptor)

    def test_signed_template_declares_development_integrity_scheme(self) -> None:
        template = build_signed_gifted_template()
        self.assertEqual(
            template["signature_scheme"],
            "bossforge-runner-template-dev-integrity-v1",
        )
        self.assertTrue(verify_signed_template(template))

    def test_runner_manifest_validation_rejects_forged_template_metadata(self) -> None:
        cases = {
            "forged signature": ("source_template", "signature", "forged"),
            "wrong contract version": ("runner_contract_version", None, "9.9"),
            "attached descendant": ("detached_after_creation", None, False),
            "missing independent version": ("independent_runner_version", None, ""),
            "wrong template id": ("source_template", "template_id", "evil-runner"),
            "wrong template version": ("source_template", "version", "gifted-runtime-v999"),
            "mixed case agent id": ("agent_id", None, "WayFinder"),
        }

        for label, (key, nested_key, value) in cases.items():
            with self.subTest(label=label):
                manifest = build_agent_runner_manifest("wayfinder")
                if nested_key is None:
                    manifest[key] = value
                else:
                    manifest[key] = dict(manifest[key])
                    manifest[key][nested_key] = value
                with self.assertRaises(ValueError):
                    validate_agent_runner_manifest(manifest)

    def test_runner_manifest_validation_rejects_absent_independent_version(self) -> None:
        manifest = build_agent_runner_manifest("wayfinder")
        del manifest["independent_runner_version"]

        with self.assertRaises(ValueError):
            validate_agent_runner_manifest(manifest)

    def test_runner_bootstrap_validation_rejects_invalid_install_and_attestation(self) -> None:
        manifest = build_agent_runner_manifest("wayfinder")
        cases = {
            "install_contract": "bossforge-ai-runner-install-v999",
            "attestation_contract": "bossforge-ai-runner-attestation-v999",
        }

        for key, value in cases.items():
            with self.subTest(key=key):
                bootstrap = build_runner_bootstrap("wayfinder", manifest)
                tampered = deepcopy(bootstrap)
                tampered[key] = value
                with self.assertRaises(ValueError):
                    validate_runner_bootstrap(tampered)

    def test_runner_manifest_validation_rejects_non_runeforge_personalized_origin(self) -> None:
        manifest = build_runeforge_origin_manifest()
        manifest["agent_id"] = "wayfinder"

        with self.assertRaises(ValueError):
            validate_agent_runner_manifest(manifest)

    def test_runner_manifest_validation_rejects_tampered_independent_version(self) -> None:
        cases = [
            build_runeforge_origin_manifest(),
            build_agent_runner_manifest("wayfinder"),
        ]

        for manifest in cases:
            with self.subTest(agent_id=manifest["agent_id"]):
                manifest["independent_runner_version"] = "tampered-runner-v1"
                with self.assertRaises(ValueError):
                    validate_agent_runner_manifest(manifest)

    def test_runner_bootstrap_validation_rejects_mixed_case_agent_id(self) -> None:
        manifest = build_agent_runner_manifest("wayfinder")
        bootstrap = build_runner_bootstrap("wayfinder", manifest)
        bootstrap["agent_id"] = "WayFinder"

        with self.assertRaises(ValueError):
            validate_runner_bootstrap(bootstrap)


if __name__ == "__main__":
    unittest.main()
