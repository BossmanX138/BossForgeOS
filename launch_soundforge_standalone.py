import argparse
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch SoundForge in standalone mode")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=5705, help="Bind port")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    python_exe = root / ".venv" / "Scripts" / "python.exe"
    if not python_exe.exists():
        python_exe = Path(sys.executable)

    launcher = root / "launcher" / "bossforge_launcher.py"
    cmd = [
        str(python_exe),
        str(launcher),
        "--hall-only",
        "--no-browser",
        "--no-tray-icon",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]

    proc = subprocess.Popen(cmd, cwd=str(root))

    try:
        time.sleep(1.5)
        webbrowser.open(f"http://{args.host}:{args.port}/?mode=soundforge&view=view_sounds")
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
