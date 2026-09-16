"""
Prime BossGate Authentication Stubs
"""
import os
import json
import base64
import getpass
from typing import Optional
from cryptography.fernet import Fernet
import pyotp

# === USB BossGate Key ===
def create_usb_key(user_info: dict, usb_path: str, password: str):
    """Encrypt and write user credentials and address to USB drive."""
    key = base64.urlsafe_b64encode(password.encode('utf-8').ljust(32, b'0'))
    f = Fernet(key)
    data = json.dumps(user_info).encode('utf-8')
    encrypted = f.encrypt(data)
    with open(os.path.join(usb_path, 'bossgate.key'), 'wb') as fp:
        fp.write(encrypted)
    print(f"[USB] Key written to {usb_path}/bossgate.key")

# === Read USB Key ===
def read_usb_key(usb_path: str, password: str) -> Optional[dict]:
    key = base64.urlsafe_b64encode(password.encode('utf-8').ljust(32, b'0'))
    f = Fernet(key)
    try:
        with open(os.path.join(usb_path, 'bossgate.key'), 'rb') as fp:
            encrypted = fp.read()
        data = f.decrypt(encrypted)
        return json.loads(data.decode('utf-8'))
    except Exception as e:
        print(f"[USB] Failed to read key: {e}")
        return None

# === NFC/RF Credential (QR code as example) ===
def generate_nfc_payload(user_info: dict) -> str:
    """Encode credentials as a base64 string for NFC/QR transfer."""
    payload = json.dumps(user_info).encode('utf-8')
    return base64.urlsafe_b64encode(payload).decode('utf-8')

# === Authenticator App (TOTP) ===
def create_totp_secret() -> str:
    return pyotp.random_base32()

def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code)

# === Admin Issuance ===
def admin_issue_key(user_info: dict, method: str, **kwargs):
    if method == 'usb':
        usb_path = kwargs.get('usb_path')
        password = kwargs.get('password')
        create_usb_key(user_info, usb_path, password)
    elif method == 'nfc':
        payload = generate_nfc_payload(user_info)
        print(f"[NFC] Payload: {payload}")
    elif method == 'totp':
        secret = create_totp_secret()
        print(f"[TOTP] Secret: {secret}")
    else:
        print("[Admin] Unknown method")

# === Request Terminal (Stub) ===
def request_terminal_verify(user_id: str) -> bool:
    # TODO: Implement biometric/password/other verification
    print(f"[Terminal] Verifying user {user_id}...")
    return True  # Stub: always succeeds

# === Access Check ===
def check_access(method: str, **kwargs) -> bool:
    if method == 'usb':
        usb_path = kwargs.get('usb_path')
        password = kwargs.get('password')
        return read_usb_key(usb_path, password) is not None
    elif method == 'nfc':
        payload = kwargs.get('payload')
        try:
            data = base64.urlsafe_b64decode(payload.encode('utf-8'))
            user_info = json.loads(data.decode('utf-8'))
            print(f"[NFC] User info: {user_info}")
            return True
        except Exception as e:
            print(f"[NFC] Failed: {e}")
            return False
    elif method == 'totp':
        secret = kwargs.get('secret')
        code = kwargs.get('code')
        return verify_totp(secret, code)
    else:
        return False
