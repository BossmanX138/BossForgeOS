"""Shared BossGate protocol primitives."""
from core.connectors.bossgate_connector import decrypt_json_payload, encrypt_json_payload

__all__ = ["decrypt_json_payload", "encrypt_json_payload"]
