from pathlib import Path
import tempfile
import unittest

from core.model_vault.private_model_vault import build_private_payload_package, verify_private_model_package


class CapsulePayloadVaultTests(unittest.TestCase):
    def test_runtime_and_memory_payloads_are_encrypted_and_verified_without_fake_model_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'runtime'
            source.mkdir()
            (source / 'runner.exe').write_bytes(b'example runner payload')
            descriptor = build_private_payload_package(agent_id='grand-archivist', source_root=source,
                vault_root=root / 'vaults', secret_key='test-owner-key', key_ref='owner-test',
                runtime_requirements={'vault_kind': 'runner'})
            manifest = verify_private_model_package(descriptor['package_path'], 'test-owner-key')
            self.assertEqual(manifest['files'][0]['relative_path'], 'runner.exe')
            self.assertEqual(manifest['files'][0]['size'], 22)
            self.assertEqual(manifest['required_categories'], [])
            self.assertFalse(any(p.name == 'runner.exe' for p in Path(descriptor['package_path']).rglob('*')))
