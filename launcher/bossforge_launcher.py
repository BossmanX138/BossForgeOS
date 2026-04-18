import argparse
import atexit
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
import threading
from typing import Callable
import time
import webbrowser
from pathlib import Path

from werkzeug.serving import make_server

from core.agents.archivist_agent import ArchivistAgent
from core.agents.codemage_agent import CodeMageAgent
from core.agents.devlot_agent import DevlotAgent
from core.daemons.hearth_tender_daemon import HearthTender
from core.model.internal_vllm_service import InternalVLLMService
from core.agents.model_gateway_agent import ModelGateway as ModelGatewayAgent
from core.rune.rune_bus import RuneBus, resolve_root_from_env
from core.agents.runeforge_agent import RuneforgeAgent
from core.security.security_sentinel_agent import SecuritySentinelAgent
from core.daemons.speaker_daemon import SpeakerDaemon
from core.agents.test_sentinel_agent import TestSentinelAgent
from core.daemons.voice_daemon import VoiceDaemon
from ui.control_hall import app


class SystemTrayIcon:
    def __init__(
        self,
        icon_path: Path,
        tooltip: str,
        open_url: str,
        stop_event: threading.Event,
        on_exit: Callable | None = None,
    ) -> None:
        self.icon_path = icon_path
        self.tooltip = tooltip
        self.open_url = open_url
        self.stop_event = stop_event
        self.on_exit = on_exit
        self._thread: threading.Thread | None = None
        self._hwnd = None
        self._hicon = None

    def start(self) -> bool:
        if os.name != "nt":
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _run(self) -> None:
        try:
            import win32api  # type: ignore
            import win32con  # type: ignore
            import win32gui  # type: ignore
        except Exception as ex:
            print(f"System tray disabled (pywin32 unavailable): {ex}")
            return

        msg_tray = win32con.WM_USER + 20
        menu_open = 1001
        menu_exit = 1002

        def _wndproc(hwnd, msg, wparam, lparam):
            if msg == msg_tray:
                if lparam in (win32con.WM_LBUTTONUP, win32con.WM_LBUTTONDBLCLK):
                    print("[Tray] Left click detected")
                    if self.open_url:
                        try:
                            webbrowser.open(self.open_url)
                        except Exception:
                            pass
                elif lparam == win32con.WM_RBUTTONUP:
                    print("[Tray] Right click detected - showing menu")
                    try:
                        menu = win32gui.CreatePopupMenu()
                        if self.open_url:
                            win32gui.AppendMenu(menu, win32con.MF_STRING, menu_open, "Open Control Hall")
                            win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, None)
                        win32gui.AppendMenu(menu, win32con.MF_STRING, menu_exit, "Exit BossForgeOS")
                        pos = win32gui.GetCursorPos()
                        win32gui.SetForegroundWindow(hwnd)
                        time.sleep(0.05)  # Small delay to ensure menu focus
                        win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN | win32con.TPM_BOTTOMALIGN, pos[0], pos[1], 0, hwnd, None)
                        win32gui.PostMessage(hwnd, win32con.WM_NULL, 0, 0)
                    except Exception as ex:
                        print(f"[Tray] Exception in right-click menu: {ex}")
                return 0
            if msg == win32con.WM_COMMAND:
                cmd = int(wparam) & 0xFFFF
                if cmd == menu_open:
                    if self.open_url:
                        try:
                            webbrowser.open(self.open_url)
                        except Exception:
                            pass
                    return 0
                if cmd == menu_exit:
                    try:
                        if self.on_exit:
                            self.on_exit()
                        else:
                            self.stop_event.set()
                    except Exception:
                        self.stop_event.set()
                    return 0
            if msg == win32con.WM_DESTROY:
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        hinst = win32api.GetModuleHandle(None)
        class_name = "BossForgeOSTrayWindow"
        wc = win32gui.WNDCLASS()
        wc.hInstance = hinst
        wc.lpszClassName = class_name
        wc.lpfnWndProc = _wndproc

        try:
            win32gui.RegisterClass(wc)
        except Exception:
            pass

        hwnd = win32gui.CreateWindow(class_name, class_name, 0, 0, 0, 0, 0, 0, 0, hinst, None)
        self._hwnd = hwnd

        icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
        try:
            self._hicon = win32gui.LoadImage(0, str(self.icon_path), win32con.IMAGE_ICON, 0, 0, icon_flags)
        except Exception:
            self._hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

        nid = (hwnd, 0, win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP, msg_tray, self._hicon, self.tooltip)
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
        except Exception as ex:
            print(f"System tray icon failed to initialize: {ex}")
            try:
                win32gui.DestroyWindow(hwnd)
            except Exception:
                pass
            return

        try:
            while not self.stop_event.is_set():
                win32gui.PumpMessages()
                time.sleep(0.2)
        finally:
            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
            except Exception:
                pass
            try:
                if self._hicon:
                    win32gui.DestroyIcon(self._hicon)
            except Exception:
                pass
            try:
                if hwnd:
                    win32gui.DestroyWindow(hwnd)
            except Exception:
                pass


def _resolve_tray_icon_path() -> Path:
    candidate = PROJECT_ROOT / ".." / "Anvil Secured Shuttle (A.S.S.)" / "assets" / "BossCrafts_Tray.png"
    if candidate.exists():
        return candidate
    fallback = PROJECT_ROOT / "assets" / "images" / "BossCrafts_Tray.ico"
    if fallback.exists():
        return fallback
    return PROJECT_ROOT / "assets" / "build" / "BossCrafts_Tray.ico"


def _hide_console_window() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        SW_HIDE = 0
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
    except Exception:
        pass


def _install_minimize_to_tray_handler(stop_event: threading.Event) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        CTRL_C_EVENT = 0
        CTRL_BREAK_EVENT = 1
        CTRL_CLOSE_EVENT = 2

        def _handler(ctrl_type: int) -> bool:
            if ctrl_type == CTRL_CLOSE_EVENT:
                # Keep process alive and hide console; user exits from tray menu.
                _hide_console_window()
                print("BossForgeOS minimized to tray. Use tray menu > Exit BossForgeOS to stop.")
                return True
            if ctrl_type in (CTRL_C_EVENT, CTRL_BREAK_EVENT):
                stop_event.set()
                return True
            return False

        handler = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)(_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, True)
        # Keep reference alive.
        setattr(_install_minimize_to_tray_handler, "_handler_ref", handler)
    except Exception:
        pass


class ControlHallServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5005,
        threaded: bool = True,
        backend: str = "werkzeug",
        thread_count: int = 12,
    ) -> None:
        self.host = host
        self.port = port
        self.backend = (backend or "werkzeug").strip().lower()

        if self.backend == "waitress":
            try:
                from waitress import create_server  # type: ignore

                self._server = create_server(app, host=self.host, port=self.port, threads=max(2, int(thread_count)))
                self._serve = self._server.run
                self._shutdown = self._server.close
            except Exception:
                # Fallback if waitress is unavailable.
                self.backend = "werkzeug"
                self._server = make_server(self.host, self.port, app, threaded=threaded)
                self._serve = self._server.serve_forever
                self._shutdown = self._server.shutdown
        else:
            # Use threaded serving so slow API handlers do not block the whole UI.
            self._server = make_server(self.host, self.port, app, threaded=threaded)
            self._serve = self._server.serve_forever
            self._shutdown = self._server.shutdown

        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._shutdown()
        self._thread.join(timeout=5)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _acquire_launcher_lock() -> pathlib.Path:
    lock_dir = PROJECT_ROOT / ".runtime"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "bossforge_launcher.lock"

    if lock_path.exists():
        print(f"[LauncherLock] Bypassing lockfile check: forcibly removing lockfile and proceeding.")
        lock_path.unlink(missing_ok=True)

    lock_path.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "started_at": time.time(),
            }
        ),
        encoding="utf-8",
    )

    def _release_lock() -> None:
        try:
            if lock_path.exists():
                payload = json.loads(lock_path.read_text(encoding="utf-8"))
                if int(payload.get("pid", -1)) == os.getpid():
                    lock_path.unlink(missing_ok=True)
        except Exception:
            pass

    atexit.register(_release_lock)
    return lock_path


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
    parser.add_argument("--no-speaker-daemon", action="store_true", help="Disable speaker daemon")
    parser.add_argument("--safe-mode", action="store_true", help="Disable heavy background services (voice, speaker, internal vLLM)")
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
    parser.add_argument("--hall-server", choices=["werkzeug", "waitress"], default="werkzeug", help="Control Hall HTTP server backend")
    parser.add_argument("--hall-threads", type=int, default=12, help="Control Hall thread count (waitress) or target concurrency")
    parser.add_argument("--hall-single-thread", action="store_true", help="Run Control Hall in single-threaded mode")
    parser.add_argument("--prune-events-days", type=int, default=0, help="Prune bus event backlog older than this many days before start (0 disables)")
    parser.add_argument("--prune-events-delete", action="store_true", help="Delete pruned events instead of archiving into bus/events_archive")
    parser.add_argument("--warm-events-cache", action="store_true", help="Warm recent event cache at startup for faster status/events endpoints")
    parser.add_argument("--warm-events-cache-days", type=int, default=3, help="How many recent days to scan when warming event cache")
    parser.add_argument("--warm-events-cache-lines", type=int, default=8000, help="Maximum lines to keep in warmed recent event cache")
    parser.add_argument("--no-tray-icon", action="store_true", help="Disable Windows system tray icon")
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
    _acquire_launcher_lock()

    if args.prune_events_days > 0:
        bus = RuneBus(resolve_root_from_env())
        stats = bus.prune_events(keep_days=args.prune_events_days, archive=not args.prune_events_delete)
        mode = "delete" if args.prune_events_delete else "archive"
        print(
            f"Event prune ({mode}) complete: inspected={stats.get('inspected', 0)} "
            f"moved={stats.get('moved', 0)} deleted={stats.get('deleted', 0)} errors={stats.get('errors', 0)}"
        )

    if args.warm_events_cache:
        bus = RuneBus(resolve_root_from_env())
        warmed = bus.warm_recent_events_cache(days=args.warm_events_cache_days, max_lines=args.warm_events_cache_lines)
        print(
            f"Recent event cache warm complete: written={warmed.get('written', 0)} "
            f"errors={warmed.get('errors', 0)}"
        )

    if args.safe_mode:
        args.no_voice_daemon = True
        args.no_speaker_daemon = True
        args.no_internal_vllm = True

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
    tray_icon: SystemTrayIcon | None = None
    shutdown_called = False

    _install_minimize_to_tray_handler(stop_event)

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

        if not args.no_speaker_daemon:
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
        hall = ControlHallServer(
            host=args.host,
            port=args.port,
            threaded=not args.hall_single_thread,
            backend=args.hall_server,
            thread_count=args.hall_threads,
        )
        hall.start()
        print(
            f"Control Hall started on http://{args.host}:{args.port} "
            f"(backend={args.hall_server}, threaded={not args.hall_single_thread}, threads={args.hall_threads})"
        )
        if not args.no_browser:
            webbrowser.open(f"http://{args.host}:{args.port}")

    if not args.no_tray_icon and os.name == "nt":
        tray_icon_path = _resolve_tray_icon_path()
        open_url = f"http://{args.host}:{args.port}" if hall is not None else ""
        tray_icon = SystemTrayIcon(
            icon_path=tray_icon_path,
            tooltip="BossForgeOS (running)",
            open_url=open_url,
            stop_event=stop_event,
            on_exit=lambda: stop_event.set(),
        )
        tray_icon.start()
        if tray_icon_path.exists():
            print(f"System tray icon active: {tray_icon_path}")
        else:
            print("System tray icon active with Windows default icon (tray asset not found).")

    def _shutdown(*_: object) -> None:
        nonlocal shutdown_called
        if shutdown_called:
            return
        shutdown_called = True
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
        if tray_icon is not None:
            tray_icon.stop()
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
    finally:
        _shutdown()


if __name__ == "__main__":
    main()
