"""Bounded GGUF v2/v3 metadata inspection; no tensor data is loaded or executed."""
from pathlib import Path
import struct


def inspect_gguf(path):
    path = Path(path)
    size = path.stat().st_size
    limit = min(size, 128 * 1024 * 1024)
    with path.open('rb') as stream:
        def read(count):
            if count < 0 or stream.tell() + count > limit:
                raise ValueError('Invalid or oversized GGUF metadata.')
            data = stream.read(count)
            if len(data) != count:
                raise ValueError('Truncated GGUF metadata.')
            return data

        def number(fmt):
            return struct.unpack('<' + fmt, read(struct.calcsize('<' + fmt)))[0]

        def skip(count):
            if count < 0 or stream.tell() + count > limit:
                raise ValueError('Truncated or oversized GGUF metadata.')
            stream.seek(count, 1)

        def string(capture=False):
            count = number('Q')
            if capture:
                if count > 1024 * 1024:
                    raise ValueError('Oversized GGUF metadata string.')
                return read(count).decode('utf-8', errors='strict')
            skip(count)

        sizes = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
        def value(kind, capture=False):
            if kind == 8:
                return string(capture)
            if kind == 9:
                element, count = number('I'), number('Q')
                if count > 10_000_000 or element == 9:
                    raise ValueError('Unsupported GGUF metadata array.')
                if element == 8:
                    for _ in range(count):
                        string()
                elif element in sizes:
                    skip(sizes[element] * count)
                else:
                    raise ValueError('Invalid GGUF array element type.')
                return (element, count)
            if kind not in sizes:
                raise ValueError('Invalid GGUF metadata value type.')
            skip(sizes[kind])

        if read(4) != b'GGUF' or number('I') not in (2, 3):
            raise ValueError('Unsupported GGUF header/version.')
        tensors, entries = number('Q'), number('Q')
        if not 0 < tensors <= 1_000_000 or entries > 100_000:
            raise ValueError('Invalid GGUF tensor/metadata counts.')
        metadata = {}
        wanted = {'general.architecture', 'tokenizer.ggml.model', 'tokenizer.ggml.tokens'}
        for _ in range(entries):
            key = string(True)
            result = value(number('I'), key in wanted)
            if key in wanted:
                metadata[key] = result
        if stream.tell() >= size:
            raise ValueError('GGUF tensor descriptors/data are missing.')
        tokens = metadata.get('tokenizer.ggml.tokens')
        return {'architecture': metadata.get('general.architecture'),
                'embedded_tokenizer': bool(metadata.get('tokenizer.ggml.model') and
                    isinstance(tokens, tuple) and tokens[0] == 8 and tokens[1] > 0),
                'tensor_count': tensors}
