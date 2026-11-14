from pathlib import Path
import struct
import tempfile
import unittest

from core.model_vault.private_model_vault import inspect_model_source


def string(text):
    data = text.encode()
    return struct.pack('<Q', len(data)) + data


def gguf(tokenizer=True):
    fields = [string('general.architecture') + struct.pack('<I', 8) + string('qwen2')]
    if tokenizer:
        fields += [string('tokenizer.ggml.model') + struct.pack('<I', 8) + string('gpt2'),
                   string('tokenizer.ggml.tokens') + struct.pack('<IIQ', 9, 8, 2) + string('a') + string('b')]
    return b'GGUF' + struct.pack('<IQQ', 3, 1, len(fields)) + b''.join(fields) + bytes(64)


class GgufModelCapsuleTests(unittest.TestCase):
    def test_embedded_tokenizer_and_architecture_satisfy_complete_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / 'model.gguf').write_bytes(gguf())
            result = inspect_model_source(path)
            self.assertTrue({'weights', 'model_config', 'tokenizer'} <= set(result['present_categories']))
            self.assertEqual(len(result['files']), 1)

    def test_projector_alone_is_not_a_complete_language_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / 'mmproj.gguf').write_bytes(gguf(tokenizer=False))
            with self.assertRaisesRegex(ValueError, 'tokenizer'):
                inspect_model_source(path)

    def test_truncated_metadata_is_rejected_before_packaging(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / 'model.gguf').write_bytes(gguf()[:30])
            with self.assertRaisesRegex(ValueError, 'GGUF'):
                inspect_model_source(path)
