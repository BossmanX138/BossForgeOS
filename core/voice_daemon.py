import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from core.rune_bus import RuneBus, resolve_root_from_env
from core.runeforge_agent import RuneforgeAgent


class VoiceDaemon:
    def __init__(self, interval_seconds: int = 1, root: Path | None = None) -> None:
        self.interval_seconds = interval_seconds
        self.root = root or resolve_root_from_env()
        self.bus = RuneBus(self.root)
        self.seen_commands: set[str] = set()
        self.muted = False
        self.runeforge = RuneforgeAgent(interval_seconds=9, root=self.root)
        self.voice_script = Path(__file__).resolve().parents[1] / "Runeforge OS Edition" / "audio_dictation.py"

    def _parse_last_json_line(self, text: str) -> dict[str, Any] | None:
        for line in reversed((text or "").splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
        return None

    def _capture_spoken_text(self) -> dict[str, Any]:
        if not self.voice_script.exists():
            return {"ok": False, "message": f"voice script not found: {self.voice_script}"}

        try:
            proc = subprocess.run(
                [sys.executable, str(self.voice_script), "--capture-only"],
                cwd=str(self.voice_script.parent),
                capture_output=True,
                text=True,
                timeout=180,
            )
        except Exception as ex:
            return {"ok": False, "message": str(ex)}

        parsed = self._parse_last_json_line(proc.stdout)
        spoken = str(parsed.get("spoken_text", "")).strip() if isinstance(parsed, dict) else ""
        return {
            "ok": proc.returncode == 0 and bool(spoken),
            "returncode": proc.returncode,
            "spoken_text": spoken,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        }

    def _normalize(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())

    def _is_activation(self, text: str) -> bool:
        normalized = self._normalize(text)
        return normalized.startswith("bossforge") or normalized.startswith("runeforge")

    def _control_intent(self, text: str) -> str | None:
        normalized = self._normalize(text)
        if normalized in {
            "bossforge mute",
            "runeforge mute",
            "bossforge mute listening",
            "runeforge mute listening",
            "bossforge be quiet",
            "runeforge be quiet",
        }:
            return "mute"
        if normalized in {
            "bossforge unmute",
            "runeforge unmute",
            "bossforge unmute listening",
            "runeforge unmute listening",
            "bossforge resume listening",
            "runeforge resume listening",
        }:
            return "unmute"
        if normalized in {
            "bossforge stop listening",
            "runeforge stop listening",
            "bossforge shutdown voice",
            "runeforge shutdown voice",
        }:
            return "stop"
        return None

    def _emit_voice_feedback(self, message: str, level: str = "info") -> None:
        self.bus.emit_event("runeforge", "voice_feedback", {"message": message}, level=level)

    def _handle_control(self, intent: str) -> bool:
        if intent == "mute":
            self.muted = True
            self._emit_voice_feedback("Voice daemon muted.")
            return False
        if intent == "unmute":
            self.muted = False
            self._emit_voice_feedback("Voice daemon unmuted.")
            return False
        if intent == "stop":
            self._emit_voice_feedback("Voice daemon stopping.")
            return True
        return False

    def _handle_bus_command(self, payload: dict[str, Any]) -> bool:
        if payload.get("target") != "voice_daemon":
            return False
        command = str(payload.get("command", "")).strip().lower()
        if command == "mute":
            self.muted = True
            self._emit_voice_feedback("Voice daemon muted by bus command.")
        elif command == "unmute":
            self.muted = False
            self._emit_voice_feedback("Voice daemon unmuted by bus command.")
        elif command == "stop":
            self._emit_voice_feedback("Voice daemon stopping by bus command.")
            return True
        elif command == "status_ping":
            self.bus.emit_event("voice_daemon", "command:status_ping", {"ok": True, "status": "alive", "muted": self.muted})
        return False

    def run(self, stop_event: threading.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            self.bus.write_state(
                "voice_daemon",
                {
                    "service": "voice_daemon",
                    "pid": os.getpid(),
                    "status": "running",
                    "muted": self.muted,
                },
            )

            should_stop = False
            for _, payload in self.bus.poll_commands(self.seen_commands):
                if self._handle_bus_command(payload):
                    should_stop = True
                    break
            if should_stop:
                break

            captured = self._capture_spoken_text()
            if not captured.get("ok"):
                # Do not spam logs on routine no-speech errors.
                time.sleep(self.interval_seconds)
                continue

            spoken_text = str(captured.get("spoken_text", "")).strip()
            if not spoken_text:
                time.sleep(self.interval_seconds)
                continue

            intent = self._control_intent(spoken_text)
            if intent and self._is_activation(spoken_text):
                if self._handle_control(intent):
                    break
                time.sleep(0.1)
                continue

            if self.muted:
                time.sleep(0.1)
                continue

            result = self.runeforge.run_voice_text({"text": spoken_text})
            if not result.get("ok"):
                self.bus.emit_event("runeforge", "voice_error", {"message": "Voice command failed", "spoken_text": spoken_text, "result": result}, level="warning")
            else:
                vr = result.get("voice_result") if isinstance(result.get("voice_result"), dict) else {}
                if vr.get("voice_action") == "agent_ping":
                    target = str(((vr.get("result") or {}) if isinstance(vr.get("result"), dict) else {}).get("agent", "agent"))
                    self._emit_voice_feedback(f"{target.replace('_', ' ').title()} is online.")

            time.sleep(self.interval_seconds)

    def run_forever(self) -> None:
        self.run(stop_event=None)


def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS continuous voice daemon")
    parser.add_argument("--interval", type=float, default=0.5, help="Loop interval in seconds")
    args = parser.parse_args()

    daemon = VoiceDaemon(interval_seconds=max(0.1, args.interval))
    daemon.run_forever()


if __name__ == "__main__":
    main()