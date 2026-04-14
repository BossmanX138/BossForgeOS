import sys
import os
import argparse
import json
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_command_code_from_vault() -> str:
    root = _project_root()
    vault_path = root / "bus" / "state" / "security_secrets_vault.json"
    if not vault_path.exists():
        return ""

    try:
        payload = json.loads(vault_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""

    core_root = root / "core"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    if str(core_root) not in sys.path:
        sys.path.insert(0, str(core_root))

    try:
        from core.security.security_vault import unprotect_text  # type: ignore
    except Exception:
        return ""

    for key in ("runeforge_command_code", "command_code"):
        cipher = payload.get(key)
        if not isinstance(cipher, str) or not cipher.strip():
            continue
        try:
            value = unprotect_text(cipher).strip()
        except Exception:
            continue
        if value:
            return value

    return ""


def _load_command_code_from_file() -> str:
    try:
        with open("command_code.txt", "r", encoding="utf-8") as f:
            for line in f:
                candidate = line.strip()
                if candidate and not candidate.startswith("#"):
                    return candidate
    except Exception:
        return ""
    return ""


def check_command_code(provided_code: str | None = None):
    try:
        code = _load_command_code_from_vault() or _load_command_code_from_file()
        if not code:
            print('No command code configured in vault or file. Action aborted.')
            sys.exit(1)
        user_code = (provided_code or input('Enter command code: ').strip()).strip()
        if user_code != code:
            print('Invalid command code. Action aborted.')
            sys.exit(1)
    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)

def perform_high_risk_action(action_func, *args, code: str | None = None, **kwargs):
    check_command_code(code)
    action_func(*args, **kwargs)

# Example usage:
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", type=str, default=None)
    args = parser.parse_args()

    def dangerous():
        print("High-risk action performed!")
    perform_high_risk_action(dangerous, code=args.code)
