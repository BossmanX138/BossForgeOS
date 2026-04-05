import argparse
import json
import os
import signal
import sys
import pathlib

# === Path Resolver for Bundled/Source Modes ===
def get_project_root():
    if getattr(sys, 'frozen', False):
        # PyInstaller bundled mode
        return pathlib.Path(sys.executable).parent
    return pathlib.Path(__file__).resolve().parent.parent

PROJECT_ROOT = get_project_root()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'core'))
sys.path.insert(0, str(PROJECT_ROOT / 'ui'))
sys.path.insert(0, str(PROJECT_ROOT / 'modules'))
import sys
import pathlib
# Debug: print sys.path to diagnose import issues
print('LAUNCHER sys.path:', sys.path)
# Ensure project root is in sys.path for PyInstaller bundled execution
if getattr(sys, 'frozen', False):
    bundle_dir = pathlib.Path(sys.executable).parent.parent
    sys.path.insert(0, str(bundle_dir))
    sys.path.insert(0, str(bundle_dir / 'core'))
    sys.path.insert(0, str(bundle_dir / 'ui'))
    sys.path.insert(0, str(bundle_dir / 'modules'))
import sys
import pathlib
# Ensure project root is in sys.path for PyInstaller bundled execution
if getattr(sys, 'frozen', False):
    bundle_dir = pathlib.Path(sys.executable).parent.parent
    sys.path.insert(0, str(bundle_dir))
    sys.path.insert(0, str(bundle_dir / 'core'))
    sys.path.insert(0, str(bundle_dir / 'ui'))
    sys.path.insert(0, str(bundle_dir / 'modules'))
import threading
import time
import webbrowser
from pathlib import Path

from werkzeug.serving import make_server

from core.agents.archivist_agent import ArchivistAgent
from core.agents.codemage_agent import CodeMageAgent
from core.agents.devlot_agent import DevlotAgent
from core.daemons.hearth_tender_daemon import HearthTender
from core.model.internal_vllm_service import InternalVLLMService
from core.connectors.huggingface_connector import HuggingFaceConnector
from core.agents.model_gateway_agent import ModelGatewayAgent
from core.rune.rune_bus import RuneBus, resolve_root_from_env
from core.agents.runeforge_agent import RuneforgeAgent
from core.security.security_sentinel_agent import SecuritySentinelAgent
from core.daemons.speaker_daemon import SpeakerDaemon
from core.agents.test_sentinel_agent import TestSentinelAgent
from core.daemons.voice_daemon import VoiceDaemon
from ui.control_hall import app
from core.daemons.voice_daemon import VoiceDaemon


class ControlHallServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 5005) -> None:
        self.host = host
        self.port = port
        self._server = make_server(self.host, self.port, app)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BossForgeOS Unified Launcher")
    parser.add_argument("--daemon-only", action="store_true", help="Start only the Hearth-Tender daemon")
    parser.add_argument("--hall-only", action="store_true", help="Start only the Control Hall")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open Control Hall in browser")
    parser.add_argument("--interval", type=int, default=30, help="Daemon poll interval in seconds")
    parser.add_argument("--archivist-interval", type=int, default=15, help="Archivist poll interval in seconds")
    parser.add_argument("--model-interval", type=int, default=5, help="Model gateway poll interval in seconds")
    parser.add_argument("--security-interval", type=int, default=20, help="Security Sentinel poll interval in seconds")
    parser.add_argument("--codemage-interval", type=int, default=8, help="CodeMage poll interval in seconds")
    parser.add_argument("--devlot-interval", type=int, default=10, help="Devlot poll interval in seconds")
    parser.add_argument("--runeforge-interval", type=int, default=9, help="Runeforge poll interval in seconds")
    parser.add_argument("--test-sentinel-interval", type=int, default=45, help="Test Sentinel poll interval in seconds")
    parser.add_argument("--speaker-interval", type=int, default=3, help="Speaker poll interval in seconds")
    parser.add_argument("--voice-interval", type=float, default=0.5, help="Voice daemon loop interval in seconds")
    parser.add_argument("--no-voice-daemon", action="store_true", help="Disable continuous voice daemon")
    parser.add_argument("--no-internal-vllm", action="store_true", help="Disable internal vLLM startup for Runeforge router")
    parser.add_argument("--internal-vllm-host", default="127.0.0.1", help="Internal vLLM bind host")
    parser.add_argument("--internal-vllm-port", type=int, default=8011, help="Internal vLLM bind port")
    parser.add_argument("--internal-vllm-model", default=".models/runeforge_core-7b", help="Path to Runeforge internal model")
    parser.add_argument("--internal-vllm-model-name", default="runeforge_Core-7b", help="Served model name for internal vLLM")
    parser.add_argument("--internal-vllm-python", default="", help="Optional Python executable for internal vLLM runtime")
    parser.add_argument("--internal-vllm-wsl", action="store_true", help="Run internal vLLM in WSL instead of native Windows runtime")
    parser.add_argument("--internal-vllm-wsl-distro", default="", help="Optional WSL distro name for internal vLLM")
    parser.add_argument("--internal-vllm-wsl-python", default="python3", help="Python executable inside WSL for internal vLLM")
    parser.add_argument("--internal-vllm-wsl-model-path", default="", help="Optional model path inside WSL (defaults to Windows path auto-converted)")
    parser.add_argument("--warn-threshold", type=float, default=80.0, help="Disk warning threshold percentage")
    parser.add_argument("--host", default="127.0.0.1", help="Control Hall bind host")
    parser.add_argument("--port", type=int, default=5005, help="Control Hall bind port")
    return parser.parse_args()


def _configure_runeforge_llm_router(url: str, model: str) -> None:
    bus = RuneBus(resolve_root_from_env())
    profile_path = bus.state / "runeforge_profile.json"
    profile: dict[str, object] = {}
    if profile_path.exists():
        try:
            loaded = json.loads(profile_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                profile = loaded
        except (OSError, json.JSONDecodeError):
            profile = {}

    profile.setdefault("id", "runeforge")
    profile.setdefault("name", "Runeforge, First Mind of the Forge")
    profile.setdefault("version", "1.0.0")
    profile.setdefault("description", "Model/runtime infrastructure steward for BossForge workloads.")

    llm_router = profile.get("llm_router") if isinstance(profile.get("llm_router"), dict) else {}
    llm_router = dict(llm_router)
    llm_router.update(
        {
            "enabled": True,
            "provider": "openai_compatible",
            "url": url,
            "model": model,
            "api_key_env": llm_router.get("api_key_env", "") if isinstance(llm_router.get("api_key_env"), str) else "",
            "timeout_seconds": int(llm_router.get("timeout_seconds", 12) or 12),
            "temperature": float(llm_router.get("temperature", 0.0) or 0.0),
            "max_tokens": int(llm_router.get("max_tokens", 350) or 350),
        }
    )
    profile["llm_router"] = llm_router
    profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")


def _resolve_internal_vllm_python(explicit_path: str) -> str | None:
    candidate = explicit_path.strip()
    if candidate:
        resolved = Path(candidate).expanduser().resolve()
        if resolved.exists():
            return str(resolved)

    env_candidate = os.environ.get("BOSSFORGE_INTERNAL_VLLM_PYTHON", "").strip()
    if env_candidate:
        resolved = Path(env_candidate).expanduser().resolve()
        if resolved.exists():
            return str(resolved)

    conventional = [
        Path(".runtime") / "vllm_runtime" / "Scripts" / "python.exe",
        Path(".venv-vllm") / "Scripts" / "python.exe",
    ]
    for path in conventional:
        resolved = path.expanduser().resolve()
        if resolved.exists():
            return str(resolved)
    return None


def main() -> None:
    args = parse_args()
    if args.daemon_only and args.hall_only:
        raise SystemExit("Choose only one mode: --daemon-only or --hall-only")

    stop_event = threading.Event()
    daemon_thread: threading.Thread | None = None
    archivist_thread: threading.Thread | None = None
    model_thread: threading.Thread | None = None
    security_thread: threading.Thread | None = None
    codemage_thread: threading.Thread | None = None
    devlot_thread: threading.Thread | None = None
    runeforge_thread: threading.Thread | None = None
    test_sentinel_thread: threading.Thread | None = None
    voice_router_speaker_thread: threading.Thread | None = None
    voice_daemon_thread: threading.Thread | None = None
    internal_vllm: InternalVLLMService | None = None
    hall: ControlHallServer | None = None

    if not args.hall_only:
        daemon = HearthTender(interval_seconds=args.interval, warn_threshold=args.warn_threshold)
        daemon_thread = threading.Thread(target=daemon.run, kwargs={"stop_event": stop_event}, daemon=True)
        daemon_thread.start()
        print("Hearth-Tender started")

        archivist = ArchivistAgent(interval_seconds=args.archivist_interval)
        archivist_thread = threading.Thread(target=archivist.run, kwargs={"stop_event": stop_event}, daemon=True)
        archivist_thread.start()
        print("Archivist started")

        model_gateway = ModelGatewayAgent(interval_seconds=args.model_interval)
        model_thread = threading.Thread(target=model_gateway.run, kwargs={"stop_event": stop_event}, daemon=True)
        model_thread.start()
        print("Model gateway started")

        if not args.no_internal_vllm:
            model_path = Path(args.internal_vllm_model).expanduser().resolve()
            vllm_python = _resolve_internal_vllm_python(args.internal_vllm_python)
            if args.internal_vllm_wsl:
                distro_display = args.internal_vllm_wsl_distro or "<default distro>"
                print(f"Internal vLLM runtime: WSL ({distro_display}) via {args.internal_vllm_wsl_python}")
            elif vllm_python:
                print(f"Internal vLLM runtime: {vllm_python}")
            else:
                print("Internal vLLM runtime: using launcher Python (set --internal-vllm-python or .runtime/vllm_runtime)")
            internal_vllm = InternalVLLMService(
                model_path=model_path,
                served_model_name=args.internal_vllm_model_name,
                host=args.internal_vllm_host,
                port=args.internal_vllm_port,
                python_exe=vllm_python or None,
                use_wsl=bool(args.internal_vllm_wsl),
                wsl_distro=args.internal_vllm_wsl_distro,
                wsl_python=args.internal_vllm_wsl_python,
                wsl_model_path=args.internal_vllm_wsl_model_path,
            )
            vllm_start = internal_vllm.start()
            if vllm_start.get("ok"):
                _configure_runeforge_llm_router(url=str(vllm_start.get("url", "")), model=str(vllm_start.get("model", args.internal_vllm_model_name)))
                print(f"Internal vLLM started ({vllm_start.get('model')}) at {vllm_start.get('url')}")
            else:
                print(f"Internal vLLM not started: {vllm_start.get('message', 'unknown error')}")

        security = SecuritySentinelAgent(interval_seconds=args.security_interval)
        security_thread = threading.Thread(target=security.run, kwargs={"stop_event": stop_event}, daemon=True)
        security_thread.start()
        print("Security Sentinel started")

        codemage = CodeMageAgent(interval_seconds=args.codemage_interval)
        codemage_thread = threading.Thread(target=codemage.run, kwargs={"stop_event": stop_event}, daemon=True)
        codemage_thread.start()
        print("CodeMage started")

        devlot = DevlotAgent(interval_seconds=args.devlot_interval)
        devlot_thread = threading.Thread(target=devlot.run, kwargs={"stop_event": stop_event}, daemon=True)
        devlot_thread.start()
        print("Devlot started")

        runeforge = RuneforgeAgent(interval_seconds=args.runeforge_interval)
        runeforge_thread = threading.Thread(target=runeforge.run, kwargs={"stop_event": stop_event}, daemon=True)
        runeforge_thread.start()
        print("Runeforge started")

        test_sentinel = TestSentinelAgent(interval_seconds=args.test_sentinel_interval)
        test_sentinel_thread = threading.Thread(target=test_sentinel.run, kwargs={"stop_event": stop_event}, daemon=True)
        test_sentinel_thread.start()
        print("Test Sentinel started")

        global_speaker = SpeakerDaemon(
            interval_seconds=args.speaker_interval,
            profile_path="voices/runeforge/profile.json",
            source_filter="*",
        )
        voice_router_speaker_thread = threading.Thread(
            target=global_speaker.run,
            kwargs={"stop_event": stop_event},
            daemon=True,
        )
        voice_router_speaker_thread.start()
        print("Speaker started (all agents)")

        if not args.no_voice_daemon:
            voice_daemon = VoiceDaemon(interval_seconds=max(0.1, args.voice_interval))
            voice_daemon_thread = threading.Thread(
                target=voice_daemon.run,
                kwargs={"stop_event": stop_event},
                daemon=True,
            )
            voice_daemon_thread.start()
            print("Voice daemon started (continuous listening)")

    if not args.daemon_only:
        hall = ControlHallServer(host=args.host, port=args.port)
        hall.start()
        print(f"Control Hall started on http://{args.host}:{args.port}")
        if not args.no_browser:
            webbrowser.open(f"http://{args.host}:{args.port}")

    def _shutdown(*_: object) -> None:
        stop_event.set()
        if hall is not None:
            hall.stop()
        if daemon_thread is not None and daemon_thread.is_alive():
            daemon_thread.join(timeout=5)
        if archivist_thread is not None and archivist_thread.is_alive():
            archivist_thread.join(timeout=5)
        if model_thread is not None and model_thread.is_alive():
            model_thread.join(timeout=5)
        if security_thread is not None and security_thread.is_alive():
            security_thread.join(timeout=5)
        if codemage_thread is not None and codemage_thread.is_alive():
            codemage_thread.join(timeout=5)
        if devlot_thread is not None and devlot_thread.is_alive():
            devlot_thread.join(timeout=5)
        if runeforge_thread is not None and runeforge_thread.is_alive():
            runeforge_thread.join(timeout=5)
        if test_sentinel_thread is not None and test_sentinel_thread.is_alive():
            test_sentinel_thread.join(timeout=5)
        if voice_router_speaker_thread is not None and voice_router_speaker_thread.is_alive():
            voice_router_speaker_thread.join(timeout=5)
        if voice_daemon_thread is not None and voice_daemon_thread.is_alive():
            voice_daemon_thread.join(timeout=5)
        if internal_vllm is not None:
            stop_result = internal_vllm.stop()
            if not stop_result.get("ok"):
                print(f"Warning: internal vLLM stop issue: {stop_result.get('message', '')}")

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while not stop_event.is_set():
            time.sleep(0.25)
    except KeyboardInterrupt:
        _shutdown()


if __name__ == "__main__":
    main()
