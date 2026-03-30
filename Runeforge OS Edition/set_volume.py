import argparse
import ctypes
import json
from pathlib import Path


def _emit(payload: dict) -> None:
    print(json.dumps(payload))


def get_command_code() -> str | None:
    path = Path(__file__).resolve().parent / "command_code.txt"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            code = line.strip()
            if code and not code.startswith("#"):
                return code
    return None


def validate_code(provided_code: str | None) -> bool:
    expected = get_command_code()
    if not expected:
        return True
    if not provided_code:
        return False
    return provided_code.strip() == expected


def set_system_volume(volume_percent: int) -> dict:
    try:
        clamped = max(0, min(100, int(volume_percent)))
    except Exception:
        return {"ok": False, "action": "set_volume", "error": "invalid_level"}

    new_volume = int(clamped * 65535 / 100)
    try:
        for _ in range(50):
            ctypes.windll.winmm.waveOutSetVolume(0, new_volume | (new_volume << 16))
        return {"ok": True, "action": "set_volume", "level": clamped}
    except Exception as ex:
        return {"ok": False, "action": "set_volume", "level": clamped, "error": str(ex)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Runeforge system volume utility")
    parser.add_argument("--level", type=int, required=True, help="Volume percent from 0 to 100")
    parser.add_argument("--code", type=str, help="Optional command code for standalone validation")
    parser.add_argument("--trusted-caller", action="store_true", help="Skip local code check (already validated upstream)")
    args = parser.parse_args()

    if not args.trusted_caller and not validate_code(args.code):
        _emit({"ok": False, "action": "set_volume", "error": "invalid_or_missing_command_code"})
        raise SystemExit(1)

    result = set_system_volume(args.level)
    _emit(result)
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
