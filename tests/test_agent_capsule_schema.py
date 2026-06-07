import unittest

from core.runner import build_agent_runner_manifest
from core.schemas.agent_schema import normalize_agent_profile, validate_agent_profile
from core.schemas.agent_capsule import (
    CAPSULE_LIFECYCLE_STATES,
    CAPSULE_VAULT_NAMES,
    assert_rarity_unchanged,
    build_authenticated_profile_view,
    build_capsule_manifest,
    build_public_identity_card,
    transition_lifecycle,
    validate_capsule_manifest,
)


class AgentCapsuleSchemaTests(unittest.TestCase):
    def _profile(self) -> dict:
        return {
            "id": "wayfinder",
            "name": "Wayfinder",
            "agent_class": "prime",
            "agent_type": "ranger",
            "rank": "captain",
            "rarity": "rare",
            "availability": "idle",
            "secure_address": "amber-slate-river-gate-north-star-ember",
            "skills": ["bossgate_travel_control"],
            "sigils": ["sigil_transporter"],
            "runtime_lineage": {
                "ancestor_id": "runeforge",
                "gifted_template_version": "gifted-runtime-v1",
                "sealed": True,
            },
        }

    def test_public_identity_card_is_sparse_and_address_free(self) -> None:
        card = build_public_identity_card(self._profile())
        self.assertEqual(
            card,
            {
                "name": "Wayfinder",
                "public_id": "wayfinder",
                "agent_class": "prime",
                "agent_type": "ranger",
                "rank": "captain",
                "rarity": "rare",
                "availability": "idle",
            },
        )
        self.assertNotIn("secure_address", card)
        self.assertNotIn("runtime_lineage", card)
        self.assertNotIn("skills", card)
        self.assertNotIn("sigils", card)

    def test_capsule_manifest_contains_only_encrypted_vault_descriptors(self) -> None:
        manifest = build_capsule_manifest(self._profile())
        self.assertEqual(set(manifest["vaults"]), set(CAPSULE_VAULT_NAMES))
        self.assertTrue(all(vault["encrypted"] is True for vault in manifest["vaults"].values()))
        self.assertEqual(manifest["runtime_lineage"]["ancestor_id"], "runeforge")
        self.assertTrue(manifest["runtime_lineage"]["sealed"])
        validate_capsule_manifest(manifest)

    def test_invalid_lifecycle_transition_is_rejected(self) -> None:
        self.assertIn("sealed", CAPSULE_LIFECYCLE_STATES)
        self.assertEqual(transition_lifecycle("sealed", "installed"), "installed")
        with self.assertRaisesRegex(ValueError, "invalid capsule lifecycle transition"):
            transition_lifecycle("sealed", "dreaming")

    def test_rarity_cannot_change_after_creation(self) -> None:
        assert_rarity_unchanged({"rarity": "rare"}, {"rarity": "rare"})
        with self.assertRaisesRegex(ValueError, "agent rarity is immutable"):
            assert_rarity_unchanged({"rarity": "rare"}, {"rarity": "legendary"})

    def test_authenticated_view_redacts_address_lineage_and_capsule(self) -> None:
        profile = self._profile()
        profile["gate_file"] = "state/agent_gates/wayfinder.bossgate"
        profile["capsule"] = build_capsule_manifest(profile)
        view = build_authenticated_profile_view(profile)
        self.assertNotIn("secure_address", view)
        self.assertNotIn("gate_file", view)
        self.assertNotIn("runtime_lineage", view)
        self.assertNotIn("capsule", view)
        self.assertEqual(view["skills"], ["bossgate_travel_control"])

    def test_capsule_model_vault_binds_private_model_ciphertext(self) -> None:
        profile = self._profile()
        profile["runtime"] = {
            "private_model_package": {
                "schema_version": "1.0",
                "package_id": "pmv-123",
                "owner_agent_id": "wayfinder",
                "package_path": "F:/vaults/wayfinder/pmv-123",
                "ciphertext_ref": "private_models/wayfinder/pmv-123",
                "attestation_sha256": "a" * 64,
                "key_ref": "agent-model-key:wayfinder",
                "verified": True,
            }
        }

        manifest = build_capsule_manifest(profile)

        self.assertEqual(
            manifest["vaults"]["model"]["ciphertext_ref"],
            "private_models/wayfinder/pmv-123",
        )

    def test_capsule_memory_vault_binds_private_memory_ciphertext(self) -> None:
        profile = self._profile()
        profile["runtime"] = {
            "private_memory_vault": {
                "schema_version": "1.0",
                "owner_agent_id": "wayfinder",
                "ciphertext_ref": "private_memory/wayfinder/vault.manifest.enc",
                "attestation_sha256": "b" * 64,
                "key_ref": "node:test:agent:wayfinder:private-memory-v1",
                "verified": True,
            }
        }

        manifest = build_capsule_manifest(profile)

        self.assertEqual(
            manifest["vaults"]["memory"]["ciphertext_ref"],
            "private_memory/wayfinder/vault.manifest.enc",
        )

    def test_authenticated_view_redacts_private_model_package(self) -> None:
        profile = self._profile()
        profile["private_model_package"] = {"package_id": "pmv-secret"}

        view = build_authenticated_profile_view(profile)

        self.assertNotIn("private_model_package", view)

    def test_authenticated_view_redacts_nested_private_memory_descriptors(self) -> None:
        profile = self._profile()
        profile["runtime"] = {
            "private_memory_vault": {
                "ciphertext_ref": "private_memory/wayfinder/vault.manifest.enc",
            }
        }
        profile["runner_bootstrap"] = {
            "private_memory_vault": {
                "ciphertext_ref": "private_memory/wayfinder/vault.manifest.enc",
            }
        }

        view = build_authenticated_profile_view(profile)

        self.assertNotIn("private_memory_vault", view.get("runtime", {}))
        self.assertNotIn("private_memory_vault", view.get("runner_bootstrap", {}))

    def test_canonical_profile_normalizes_capsule_fields_and_sparse_card(self) -> None:
        profile = normalize_agent_profile("scribe", {"name": "Scribe"})
        self.assertEqual(profile["public_id"], "scribe")
        self.assertEqual(profile["rarity"], "common")
        self.assertEqual(profile["availability"], "available")
        self.assertEqual(profile["runtime_lineage"]["ancestor_id"], "runeforge")
        self.assertTrue(profile["runtime_lineage"]["sealed"])
        self.assertEqual(profile["capsule"]["agent_id"], "scribe")
        self.assertEqual(
            set(profile["agent_card"]),
            {"name", "public_id", "agent_class", "agent_type", "rank", "rarity", "availability"},
        )
        validate_agent_profile(profile)

    def test_runeforge_is_origin_not_its_own_descendant(self) -> None:
        profile = normalize_agent_profile("runeforge", {"name": "RuneForge"})
        self.assertEqual(profile["runtime_lineage"]["ancestor_id"], "")
        validate_agent_profile(profile)

    def test_canonical_profile_includes_descendant_runner_manifest(self) -> None:
        profile = normalize_agent_profile("scribe", {"name": "Scribe", "llm": {"enabled": True, "model": {"model_name": "qwen"}}})
        runner = profile["runtime"]["bossforge_ai_runner"]
        self.assertEqual(runner["agent_id"], "scribe")
        self.assertEqual(runner["runner_role"], "descendant")
        self.assertEqual(runner["source_template"]["ancestor_id"], "runeforge")
        self.assertFalse(runner["depends_on_runeforge_online"])
        validate_agent_profile(profile)

    def test_validate_profile_rejects_runner_manifest_for_different_agent(self) -> None:
        profile = normalize_agent_profile("scribe", {"name": "Scribe"})
        profile["runtime"]["bossforge_ai_runner"] = build_agent_runner_manifest("other_agent")

        with self.assertRaisesRegex(ValueError, "runner manifest agent_id must match profile id"):
            validate_agent_profile(profile)

    def test_normalize_profile_rejects_invalid_existing_runner_manifest(self) -> None:
        runner_manifest = build_agent_runner_manifest("scribe")
        runner_manifest["source_template"]["signature"] = "forged"

        with self.assertRaises(ValueError):
            normalize_agent_profile(
                "scribe",
                {"name": "Scribe", "runtime": {"bossforge_ai_runner": runner_manifest}},
            )

    def test_normalize_profile_rejects_non_object_existing_runner_manifest(self) -> None:
        with self.assertRaisesRegex(ValueError, "runner manifest must be an object"):
            normalize_agent_profile(
                "scribe",
                {"name": "Scribe", "runtime": {"bossforge_ai_runner": "stale"}},
            )

    def test_canonical_runeforge_profile_is_personalized_origin_runner(self) -> None:
        profile = normalize_agent_profile(
            "runeforge",
            {
                "name": "RuneForge",
                "agent_class": "prime",
                "agent_type": "controller",
                "rank": "commander",
                "skills": ["command"],
                "sigils": ["sigil_transporter"],
                "llm": {"enabled": True, "model": {"model_name": "Runeforge_Alpha-7b"}},
            },
        )
        runner = profile["runtime"]["bossforge_ai_runner"]
        self.assertEqual(runner["runner_role"], "personalized_origin")
        self.assertEqual(runner["source_template"]["ancestor_id"], "")
        self.assertFalse(runner["depends_on_runeforge_online"])
        validate_agent_profile(profile)


if __name__ == "__main__":
    unittest.main()
