import base64
import ctypes
import ctypes.wintypes
from pathlib import Path


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


crypt32 = ctypes.windll.crypt32
kernel32 = ctypes.windll.kernel32


def _to_blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array[ctypes.c_byte]]:
    buffer = (ctypes.c_byte * len(data))(*data)
    blob = DATA_BLOB(len(data), buffer)
    return blob, buffer


def _from_blob(blob: DATA_BLOB) -> bytes:
    return ctypes.string_at(blob.pbData, blob.cbData)


def protect_bytes(data: bytes, entropy: bytes = b"BossForgeOS.Security") -> bytes:
    in_blob, _in_buffer = _to_blob(data)
    ent_blob, _ent_buffer = _to_blob(entropy)
    out_blob = DATA_BLOB()

    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(ent_blob),
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError("CryptProtectData failed")

    try:
        return _from_blob(out_blob)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def unprotect_bytes(data: bytes, entropy: bytes = b"BossForgeOS.Security") -> bytes:
    in_blob, _in_buffer = _to_blob(data)
    ent_blob, _ent_buffer = _to_blob(entropy)
    out_blob = DATA_BLOB()

    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(ent_blob),
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError("CryptUnprotectData failed")

    try:
        return _from_blob(out_blob)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def protect_text(plain_text: str) -> str:
    encrypted = protect_bytes(plain_text.encode("utf-8"))
    return base64.b64encode(encrypted).decode("ascii")


def unprotect_text(cipher_text_b64: str) -> str:
    raw = base64.b64decode(cipher_text_b64.encode("ascii"))
    return unprotect_bytes(raw).decode("utf-8")


def ensure_vault_file(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
