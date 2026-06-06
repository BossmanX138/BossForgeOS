import json
import tempfile
import unittest
from pathlib import Path

from core.model_vault.private_model_vault import (
    build_private_model_package,
    inspect_model_source,
    verify_private_model_package,
)


def write_complete_model(root: Path, marker: bytes = b"weights") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.json").write_text('{"model_type":"qwen2"}', encoding="utf-8")
    (root / "tokenizer.json").write_text('{"version":"1.0"}', encoding="utf-8")
    (root / "generation_config.json").write_text('{"max_new_tokens":128}', encoding="utf-8")
    (root / "model.safetensors").write_bytes(marker)
    (root / "requirements.txt").write_text("transformers\n", encoding="utf-8")


class PrivateModelVaultTests(unittest.TestCase):
    def test_inspector_returns_deterministic_complete_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write_complete_model(source)

            inspected = inspect_model_source(source)

            paths = [item["relative_path"] for item in inspected["files"]]
            self.assertEqual(paths, sorted(paths))
            self.assertEqual(
                set(inspected["required_categories"]),
                {"weights", "tokenizer", "model_config"},
            )
            self.assertIn("generation_config", inspected["present_categories"])

    def test_inspector_rejects_missing_weights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write_complete_model(source)
            (source / "model.safetensors").unlink()

            with self.assertRaisesRegex(ValueError, "model weights"):
                inspect_model_source(source)

    def test_inspector_rejects_missing_declared_shard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write_complete_model(source)
            (source / "model.safetensors").unlink()
            index = {"weight_map": {"layer": "model-00001-of-00002.safetensors"}}
            (source / "model.safetensors.index.json").write_text(
                json.dumps(index),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "declared shard"):
                inspect_model_source(source)

    def test_adapter_inventory_includes_complete_base_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base"
            adapter = Path(tmp) / "adapter"
            write_complete_model(base, b"base-weights")
            adapter.mkdir()
            (adapter / "adapter_config.json").write_text(
                json.dumps({"base_model_name_or_path": str(base)}),
                encoding="utf-8",
            )
            (adapter / "adapter_model.safetensors").write_bytes(b"adapter")

            inspected = inspect_model_source(adapter)

            roots = {item["source_group"] for item in inspected["files"]}
            self.assertEqual(roots, {"adapter", "base"})
            self.assertIn(
                "base/model.safetensors",
                {item["relative_path"] for item in inspected["files"]},
            )

    def test_adapter_inventory_rejects_unresolved_base_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = Path(tmp) / "adapter"
            adapter.mkdir()
            (adapter / "adapter_config.json").write_text(
                '{"base_model_name_or_path":"missing"}',
                encoding="utf-8",
            )
            (adapter / "adapter_model.safetensors").write_bytes(b"adapter")

            with self.assertRaisesRegex(ValueError, "base model"):
                inspect_model_source(adapter)

    def test_encrypted_package_round_trip_contains_no_plaintext_weights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            vaults = Path(tmp) / "vaults"
            write_complete_model(source, b"private-weight-material")

            descriptor = build_private_model_package(
                agent_id="wayfinder",
                source_root=source,
                vault_root=vaults,
                secret_key="wayfinder-secret",
                key_ref="agent-model-key:wayfinder",
                chunk_size=4,
            )

            package_root = Path(descriptor["package_path"])
            encrypted_bytes = b"".join(
                path.read_bytes() for path in package_root.rglob("*.chunk")
            )
            self.assertNotIn(b"private-weight-material", encrypted_bytes)
            self.assertTrue(descriptor["verified"])
            verified = verify_private_model_package(
                package_root,
                "wayfinder-secret",
            )
            self.assertEqual(verified["owner_agent_id"], "wayfinder")
            self.assertEqual(verified["package_id"], descriptor["package_id"])

    def test_package_verification_rejects_tampered_chunk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write_complete_model(source)
            descriptor = build_private_model_package(
                agent_id="wayfinder",
                source_root=source,
                vault_root=Path(tmp) / "vaults",
                secret_key="wayfinder-secret",
                key_ref="agent-model-key:wayfinder",
                chunk_size=4,
            )
            package_root = Path(descriptor["package_path"])
            chunk = next(package_root.rglob("*.chunk"))
            payload = json.loads(chunk.read_text(encoding="utf-8"))
            payload["ciphertext_b64"] = "AAAA"
            chunk.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "ciphertext|decrypt|authentication"):
                verify_private_model_package(package_root, "wayfinder-secret")


if __name__ == "__main__":
    unittest.main()
