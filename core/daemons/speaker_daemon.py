import argparse
import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import winsound
except Exception:  # pragma: no cover - winsound only exists on Windows
    winsound = None

from core.rune.rune_bus import RuneBus, resolve_root_from_env


class SpeakerDaemon:
    def __init__(
        self,
        interval_seconds: int = 3,
        profile_path: str = "voices/codemage/profile.json",
        source_filter: str = "codemage",
    ) -> None:
        self.interval_seconds = interval_seconds
        self.root = resolve_root_from_env()
        self.bus = RuneBus(self.root)
        self.profile_path = Path(profile_path)
        self.source_filter = source_filter
        # Start from "now" so the daemon speaks only fresh events.
        self.seen_events: set[str] = {p.name for p in self.bus.events.glob("*.json")}

    def _play_output(self, output_rel: str) -> dict[str, Any]:
        if not output_rel:
            return {"played": False, "play_message": "no output file provided"}

        output_abs = (self.root / output_rel).resolve()
        if not output_abs.exists():
            return {"played": False, "play_message": f"output missing: {output_abs}"}

        if os.name != "nt" or winsound is None:
            return {"played": False, "play_message": "audio playback currently supports Windows only"}

        try:
            winsound.PlaySound(str(output_abs), winsound.SND_FILENAME | winsound.SND_ASYNC)
            return {"played": True, "play_message": "audio playback started"}
        except Exception as ex:
            return {"played": False, "play_message": str(ex)}

    def _poll_events(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in sorted(self.bus.events.glob("*.json")):
            if path.name in self.seen_events:
                continue
            self.seen_events.add(path.name)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            payload["_event_file"] = path.name
            out.append(payload)
        return out

    def _extract_text(self, event: dict[str, Any]) -> str:
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        event_name = str(event.get("event", "")).strip()

        # Voice command completion events are high-volume and can create echo loops.
        if event_name == "command:voice_command":
            return ""

        if isinstance(data.get("message"), str) and data["message"].strip():
            return data["message"].strip()
        if isinstance(data.get("model_reply"), str) and data["model_reply"].strip():
            return data["model_reply"].strip()
        if isinstance(data.get("status"), str) and data["status"].strip():
            agent_name = self.source_filter.replace("_", " ").title()
            return f"{agent_name} status: {data['status'].strip()}"
        if event_name.startswith("command:"):
            command = event_name.split(":", 1)[1]
            if command:
                agent_name = str(event.get("source", self.source_filter)).replace("_", " ").title()
                return f"{agent_name} completed {command}."
        return ""

    def _profile_for_source(self, source: str) -> Path:
        candidate = self.root / "voices" / source / "profile.json"
        if candidate.exists():
            return candidate
        return (self.root / self.profile_path).resolve()

    def _synthesize(self, text: str, stem: str, source: str) -> dict[str, Any]:
        profile_abs = self._profile_for_source(source)
        if not profile_abs.exists():
            return {"ok": False, "message": f"profile missing: {profile_abs}"}

        profile = json.loads(profile_abs.read_text(encoding="utf-8"))
        auto_play = bool(profile.get("auto_play", True))
        xtts_python = str(profile.get("xtts_env_python", ".venv-xtts\\Scripts\\python.exe"))
        output_rel = f"voices/{source}/out/{stem}.wav"
        script_abs = (Path(__file__).resolve().parent / "xtts_speak.py").resolve()

        cmd = [
            xtts_python,
            str(script_abs),
            "--profile",
            str(profile_abs.relative_to(self.root).as_posix()),
            "--text",
            text,
            "--output",
            output_rel,
        ]
        try:
            subprocess.check_output(cmd, cwd=str(self.root), stderr=subprocess.STDOUT, text=True, timeout=90)
            return {"ok": True, "output": output_rel, "auto_play": auto_play}
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "message": "xtts_speak timed out after 90s",
                "output": output_rel,
                "auto_play": auto_play,
            }
        except Exception as ex:
            return {"ok": False, "message": str(ex), "output": output_rel, "auto_play": auto_play}

    def handle_event(self, event: dict[str, Any]) -> None:
        if event.get("type") != "event":
            return
        source = str(event.get("source", "")).strip()
        if not source:
            return
        if self.source_filter != "*" and source != self.source_filter:
            return
        text = self._extract_text(event)
        if not text:
            return

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        stem = f"{source}_{stamp}"
        result = self._synthesize(text=text, stem=stem, source=source)
        should_play = bool(result.get("auto_play", True))
        if result.get("ok") and should_play:
            playback = self._play_output(str(result.get("output", "")))
        elif result.get("ok") and not should_play:
            playback = {"played": False, "play_message": "auto_play disabled in voice profile"}
        else:
            playback = {"played": False, "play_message": "skipped"}

        self.bus.emit_event(
            "speaker",
            "tts_generated" if result.get("ok") else "tts_failed",
            {
                "source_event": event.get("_event_file", ""),
                "source_agent": source,
                "text": text,
                **playback,
                **result,
            },
            level="info" if result.get("ok") else "warning",
        )

    def run(self, stop_event: threading.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            self.bus.write_state(
                "speaker",
                {
                    "service": "speaker",
                    "pid": os.getpid(),
                    "status": "running",
                    "source_filter": self.source_filter,
                    "profile": str(self.profile_path),
                },
            )
            for event in self._poll_events():
                self.handle_event(event)
            time.sleep(self.interval_seconds)



def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS Speaker daemon")
    parser.add_argument("--interval", type=int, default=3)
    parser.add_argument("--profile", default="voices/codemage/profile.json")
    parser.add_argument("--source", default="codemage")
    args = parser.parse_args()

    daemon = SpeakerDaemon(
        interval_seconds=args.interval,
        profile_path=args.profile,
        source_filter=args.source,
    )
    daemon.run(stop_event=None)


if __name__ == "__main__":
    main()
