import winreg
import sys
import json


def _emit(payload):
    print(json.dumps(payload))

def read_value(key_path, value_name):
    from sandbox import is_registry_key_safe
    if not is_registry_key_safe(key_path):
        return {"ok": False, "action": "read_registry", "error": "sandbox_refused", "key_path": key_path}
    try:
        hive, subkey = key_path.split('\\', 1)
        hive_obj = getattr(winreg, hive)
        with winreg.OpenKey(hive_obj, subkey) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            return {
                "ok": True,
                "action": "read_registry",
                "key_path": key_path,
                "value_name": value_name,
                "value": value,
            }
    except Exception as e:
        return {
            "ok": False,
            "action": "read_registry",
            "key_path": key_path,
            "value_name": value_name,
            "error": str(e),
        }

def set_value(key_path, value_name, value, value_type='REG_SZ'):
    from sandbox import is_registry_key_safe
    if not is_registry_key_safe(key_path):
        return {"ok": False, "action": "set_registry", "error": "sandbox_refused", "key_path": key_path}
    try:
        hive, subkey = key_path.split('\\', 1)
        hive_obj = getattr(winreg, hive)
        with winreg.OpenKey(hive_obj, subkey, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, value_name, 0, getattr(winreg, value_type), value)
            return {
                "ok": True,
                "action": "set_registry",
                "key_path": key_path,
                "value_name": value_name,
                "value": value,
                "value_type": value_type,
            }
    except Exception as e:
        return {
            "ok": False,
            "action": "set_registry",
            "key_path": key_path,
            "value_name": value_name,
            "value": value,
            "value_type": value_type,
            "error": str(e),
        }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--read', nargs=2, metavar=('KEY_PATH', 'VALUE_NAME'))
    parser.add_argument('--set', nargs=3, metavar=('KEY_PATH', 'VALUE_NAME', 'VALUE'))
    parser.add_argument('--type', dest='value_type', default='REG_SZ', help='Registry value type for --set (default: REG_SZ)')
    args = parser.parse_args()
    if args.read:
        result = read_value(args.read[0], args.read[1])
        _emit(result)
        if not result.get("ok"):
            raise SystemExit(1)
    elif args.set:
        result = set_value(args.set[0], args.set[1], args.set[2], args.value_type)
        _emit(result)
        if not result.get("ok"):
            raise SystemExit(1)
    else:
        _emit({
            "ok": False,
            "error": "No action provided",
            "allowed": ["--read KEY_PATH VALUE_NAME", "--set KEY_PATH VALUE_NAME VALUE [--type REG_*]"],
        })
        raise SystemExit(2)
