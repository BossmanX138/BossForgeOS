import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote_plus


HERE = Path(__file__).resolve().parent
ACTIVATION_MONIKERS = ("runeforge", "runforge")


def _emit(payload: dict) -> None:
    print(json.dumps(payload))


def capture_text(timeout_seconds: int = 8, phrase_time_limit: int = 12) -> tuple[bool, str]:
    try:
        import speech_recognition as sr  # type: ignore
    except Exception as ex:
        return False, f"speech_recognition unavailable: {ex}"

    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=timeout_seconds, phrase_time_limit=phrase_time_limit)
        text = recognizer.recognize_google(audio)
        return True, text.strip()
    except Exception as ex:
        return False, str(ex)


def _extract_path(text: str) -> str:
    # Accept quoted paths first.
    quoted = re.findall(r'"([^"]+)"', text)
    if quoted:
        return quoted[0].strip()

    lower = text.lower().strip()
    triggers = [
        "lock file",
        "unlock file",
        "unblock file",
        "open file",
        "status file lock",
        "lock status",
    ]
    for trig in triggers:
        idx = lower.find(trig)
        if idx >= 0:
            return text[idx + len(trig):].strip(" :")
    return ""


def _extract_url(text: str) -> str:
    quoted = re.findall(r'"([^"]+)"', text)
    for value in quoted:
        val = value.strip()
        if val.lower().startswith(("http://", "https://", "www.")):
            return val if val.lower().startswith(("http://", "https://")) else f"https://{val}"

    match = re.search(r"(https?://\S+|www\.\S+)", text, flags=re.IGNORECASE)
    if not match:
        return ""
    url = match.group(1).strip().rstrip(".,;)")
    if url.lower().startswith("www."):
        return f"https://{url}"
    return url


def _extract_first_int(text: str) -> int | None:
    match = re.search(r"\b(\d{1,3})\b", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _extract_after_prefix(command_text: str, prefixes: list[str]) -> str:
    lower = command_text.lower().strip()
    for prefix in prefixes:
        idx = lower.find(prefix)
        if idx >= 0:
            value = command_text[idx + len(prefix):].strip(" :\"")
            if value:
                return value
    return ""


def _strip_activation_prefix(text: str) -> tuple[bool, str]:
    cleaned = re.sub(r"\s+", " ", text.strip())
    lowered = cleaned.lower()

    for phrase in ACTIVATION_MONIKERS:
        for sep in (" ", ":", ",", "-", "|"):
            candidate = f"{phrase}{sep}"
            if lowered.startswith(candidate):
                stripped = cleaned[len(candidate):].strip()
                return bool(stripped), stripped
        if lowered == phrase:
            return False, ""

    return False, ""


def interpret_voice_command(text: str) -> dict:
    activated, command_text = _strip_activation_prefix(text)
    if not activated:
        return {
            "ok": False,
            "message": "Missing Runeforge activation moniker",
            "activation_phrases": ["Runeforge", "runforge"],
            "example": "Runeforge, lock file \"C:/AgentSandbox/Downloads/tool.zip\"",
        }

    lower = command_text.lower().strip()
    path = _extract_path(command_text)

    # File lock lifecycle.
    if lower.startswith("lock file"):
        return {"ok": True, "action": {"action_type": "lock_file", "params": {"path": path}}}
    if lower.startswith("unlock file"):
        return {"ok": True, "action": {"action_type": "unlock_file", "params": {"path": path}}}
    if lower.startswith("unblock file"):
        return {"ok": True, "action": {"action_type": "unblock_file", "params": {"path": path}}}
    if lower.startswith("list locks") or lower.startswith("list file locks"):
        return {"ok": True, "action": {"action_type": "list_file_locks", "params": {"active_only": True}}}
    if lower.startswith("list all locks"):
        return {"ok": True, "action": {"action_type": "list_file_locks", "params": {"active_only": False}}}

    # App/process controls.
    if lower.startswith(("open app", "launch app", "start app")):
        app_target = _extract_after_prefix(command_text, ["open app", "launch app", "start app"]) or path
        return {"ok": True, "action": {"action_type": "open_app", "params": {"path": app_target}}}

    if lower.startswith("open ") and not lower.startswith(("open file", "open document", "open folder", "open directory", "open url", "open website", "open web")):
        app_target = _extract_after_prefix(command_text, ["open"])
        return {"ok": True, "action": {"action_type": "open_app", "params": {"path": app_target}}}

    if lower.startswith(("close app", "stop app", "kill app", "close process", "kill process")):
        process_name = _extract_after_prefix(
            command_text,
            ["close app", "stop app", "kill app", "close process", "kill process"],
        )
        return {"ok": True, "action": {"action_type": "close_app", "params": {"name": process_name}}}

    # File and directory operations.
    if lower.startswith(("open file", "open document")):
        file_path = path or _extract_after_prefix(command_text, ["open file", "open document"])
        return {"ok": True, "action": {"action_type": "open_file", "params": {"path": file_path}}}

    if lower.startswith(("list directory", "list folder", "show directory", "show folder", "open folder")):
        dir_path = path or _extract_after_prefix(
            command_text,
            ["list directory", "list folder", "show directory", "show folder", "open folder"],
        )
        return {"ok": True, "action": {"action_type": "list_directory", "params": {"path": dir_path}}}

    # Browser and URL commands.
    if lower.startswith(("open url", "open website", "open web", "go to", "browse to")):
        url = _extract_url(command_text)
        if not url:
            url = _extract_after_prefix(command_text, ["open url", "open website", "open web", "go to", "browse to"])
            if url and not url.lower().startswith(("http://", "https://")):
                url = f"https://{url}"
        return {"ok": True, "action": {"action_type": "open_url", "params": {"url": url}}}

    if lower.startswith("play "):
        query = command_text[5:].strip()
        if not query:
            return {
                "ok": False,
                "message": "Play command requires a song, album, or artist",
                "example": "Runeforge play Metallica Black Album",
            }
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        return {"ok": True, "action": {"action_type": "open_url", "params": {"url": url}}}

    # Volume controls.
    if lower.startswith(("set volume", "change volume", "volume")):
        level = _extract_first_int(command_text)
        if level is None:
            return {
                "ok": False,
                "message": "Volume command requires a numeric level",
                "example": "BossForge set volume to 35",
            }
        clamped = max(0, min(100, level))
        return {"ok": True, "action": {"action_type": "set_volume", "params": {"level": clamped}}}

    if lower in ("mute", "mute volume", "volume mute"):
        return {"ok": True, "action": {"action_type": "set_volume", "params": {"level": 0}}}

    if lower in ("max volume", "maximum volume", "volume max"):
        return {"ok": True, "action": {"action_type": "set_volume", "params": {"level": 100}}}

    return {
        "ok": False,
        "message": "Unsupported voice command",
        "supported_examples": [
            'Runeforge, lock file "C:/AgentSandbox/Downloads/tool.zip"',
            'Runeforge unlock file "C:/AgentSandbox/Downloads/tool.zip"',
            'Runeforge unblock file "C:/AgentSandbox/Downloads/tool.zip"',
            "Runeforge list file locks",
            "Runeforge open app notepad.exe",
            "Runeforge close app notepad",
            'Runeforge open file "C:/AgentSandbox/notes.txt"',
            'Runeforge list folder "C:/AgentSandbox"',
            "Runeforge open website github.com",
            "Runeforge set volume to 35",
            "Runeforge mute volume",
            "Runeforge play Metallica Black Album",
        ],
    }


def run_action(action: dict, command_code: str | None, agent: str = "runeforge") -> dict:
    processor = HERE / "command_processor.py"
    cmd = [
        sys.executable,
        str(processor),
        "--action-json",
        json.dumps(action),
        "--agent",
        agent,
    ]
    if command_code:
        cmd.extend(["--command-code", command_code])

    try:
        proc = subprocess.run(cmd, cwd=str(HERE), capture_output=True, text=True, timeout=120)
        parsed = None
        for line in reversed((proc.stdout or "").splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                break
            except Exception:
                continue
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "parsed": parsed,
        }
    except Exception as ex:
        return {"ok": False, "returncode": -1, "stderr": str(ex)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Runeforge voice command dictation")
    parser.add_argument("--text", type=str, help="Provide command text directly (skip microphone)")
    parser.add_argument("--capture-only", action="store_true", help="Capture or accept text and return spoken_text only")
    parser.add_argument("--execute", action="store_true", help="Execute interpreted action via command_processor")
    parser.add_argument("--command-code", type=str, default=None, help="Command code for high-risk/locked actions")
    parser.add_argument("--agent", type=str, default="runeforge", help="Caller identity")
    args = parser.parse_args()

    if args.text:
        spoken = args.text.strip()
        ok = True
    else:
        ok, spoken = capture_text()

    if not ok:
        _emit({"ok": False, "message": "Voice capture failed", "error": spoken})
        raise SystemExit(1)

    if args.capture_only:
        _emit({"ok": True, "spoken_text": spoken})
        return

    interpreted = interpret_voice_command(spoken)
    if not interpreted.get("ok"):
        _emit({"ok": False, "spoken_text": spoken, **interpreted})
        raise SystemExit(1)

    action = interpreted["action"]
    payload = {"ok": True, "spoken_text": spoken, "action": action}
    if args.execute:
        payload["execution"] = run_action(action, command_code=args.command_code, agent=args.agent)
        payload["ok"] = bool(payload["execution"].get("ok"))

    _emit(payload)
    if not payload.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
