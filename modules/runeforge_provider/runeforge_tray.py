import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import requests
from PIL import Image
import pystray
from pystray import MenuItem as Item

ROOT = Path(__file__).resolve().parent
SERVER_SCRIPT = ROOT / "runeforge_inference_server.py"
MODELS_DIR = ROOT / "models"
DEFAULT_BASE_MODEL = Path("E:/BossCrafts_Models/runeforge_core-7b")
ASSETS_DIR = ROOT / "web" / "assets"
ICON_PNG = ASSETS_DIR / "skunkworks-logo.png"
ICON_ICO = ASSETS_DIR / "skunkworks-tray.ico"
RUNTIME_CFG = ROOT / "runtime_config.json"
SERVER_URL = "http://127.0.0.1:8008"
GUI_URL = f"{SERVER_URL}/app/"

proc = None
state = {"running": False, "current_model": "default", "pec_mode": "auto"}


def load_cfg():
    if RUNTIME_CFG.exists():
        return json.loads(RUNTIME_CFG.read_text(encoding="utf-8"))
    return {
        "host": "0.0.0.0",
        "port": 8008,
        "fast_mode": True,
        "fast_max_new_tokens": 192,
        "pec_enabled": True,
        "pec_runtime_mode": "auto",
        "tts_enabled": True,
        "tts_default_voice_hint": "zira",
        "tts_default_rate": 185,
        "model_registry": {},
    }


def save_cfg(cfg):
    RUNTIME_CFG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def autodetect_models():
    reg = {}
    if not MODELS_DIR.exists():
        return reg
    for p in sorted(MODELS_DIR.iterdir()):
        if p.is_dir() and (p / "config.json").exists():
            mid = p.name
            reg[mid] = {"model_path": str(p).replace("\\", "/"), "pec_mode": "auto"}
    if "Runeforge_Alpha-7b" in reg:
        reg = {"default": {"model_path": reg["Runeforge_Alpha-7b"]["model_path"], "pec_mode": "on"}, **{k:v for k,v in reg.items() if k != "Runeforge_Alpha-7b"}}
    elif reg:
        first = next(iter(reg.values()))
        reg = {"default": {"model_path": first["model_path"], "pec_mode": "auto"}, **reg}
    return reg


def make_icon():
    if ICON_PNG.exists():
        img = Image.open(ICON_PNG).convert("RGBA")
        img = img.resize((256, 256), Image.Resampling.LANCZOS)
        img.save(ICON_ICO, format="ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
        return img.resize((64, 64), Image.Resampling.LANCZOS)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    return img


def wait_for_health(timeout=420):
    for _ in range(timeout):
        try:
            r = requests.get(f"{SERVER_URL}/health", timeout=2)
            if r.ok:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def build_env(cfg):
    env = os.environ.copy()
    cpu = os.cpu_count() or 8
    hf_workers = min(max(cpu // 2, 4), 24)
    torch_threads = min(max(cpu - 2, 4), 16)
    interop = min(max(cpu // 8, 1), 4)

    reg = cfg.get("model_registry") or autodetect_models()
    cfg["model_registry"] = reg
    save_cfg(cfg)

    env.update({
        "RUNEFORGE_HOST": str(cfg.get("host", "0.0.0.0")),
        "RUNEFORGE_PORT": str(cfg.get("port", 8008)),
        "RUNEFORGE_FAST_MODE": "1" if cfg.get("fast_mode", True) else "0",
        "RUNEFORGE_FAST_MAX_NEW_TOKENS": str(cfg.get("fast_max_new_tokens", 192)),
        "RUNEFORGE_WORKSPACE_ROOT": str(ROOT),
        "RUNEFORGE_UPLOAD_DIR": str(ROOT / "uploads"),
        "RUNEFORGE_AUDIT_LOG_PATH": str(ROOT / "logs" / "runeforge_audit.jsonl"),
        "RUNEFORGE_MEMORY_STORE_PATH": str(ROOT / "runeforge_memory_store.json"),
        "RUNEFORGE_TTS_DIR": str(ROOT / "audio"),
        "RUNEFORGE_PEC_ENABLED": "1" if cfg.get("pec_enabled", True) else "0",
        "RUNEFORGE_PEC_RUNTIME_MODE": cfg.get("pec_runtime_mode", "auto"),
        "RUNEFORGE_TTS_ENABLED": "1" if cfg.get("tts_enabled", True) else "0",
        "RUNEFORGE_TTS_DEFAULT_VOICE_HINT": str(cfg.get("tts_default_voice_hint", "zira")),
        "RUNEFORGE_TTS_DEFAULT_RATE": str(cfg.get("tts_default_rate", 185)),
        "RUNEFORGE_HF_PARALLEL_LOADING": "true",
        "RUNEFORGE_HF_PARALLEL_WORKERS": str(hf_workers),
        "RUNEFORGE_TORCH_THREADS": str(torch_threads),
        "RUNEFORGE_TORCH_INTEROP_THREADS": str(interop),
        "RUNEFORGE_UVICORN_WORKERS": "1",
        "RUNEFORGE_MODEL_REGISTRY": json.dumps(reg),
    })
    if DEFAULT_BASE_MODEL.exists():
        env["RUNEFORGE_BASE_MODEL_PATH"] = str(DEFAULT_BASE_MODEL)
    if reg.get("default", {}).get("model_path"):
        env["RUNEFORGE_MODEL_PATH"] = reg["default"]["model_path"]
    return env


def start_server(icon=None):
    global proc
    if proc and proc.poll() is None:
        return
    cfg = load_cfg()
    env = build_env(cfg)
    python = ROOT.parent / ".venv" / "Scripts" / "python.exe"
    py = str(python) if python.exists() else sys.executable
    proc = subprocess.Popen([py, str(SERVER_SCRIPT)], cwd=str(ROOT), env=env)

    def monitor():
        ok = wait_for_health()
        state["running"] = ok
        if ok and icon:
            try:
                icon.notify("Runeforge server online")
            except Exception:
                pass
    threading.Thread(target=monitor, daemon=True).start()


def stop_server(icon=None):
    global proc
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
    state["running"] = False
    if icon:
        try:
            icon.notify("Runeforge server stopped")
        except Exception:
            pass


def restart_server(icon=None):
    stop_server(icon)
    start_server(icon)


def open_gui(icon=None, item=None):
    webbrowser.open(GUI_URL)


def switch_model(model_id):
    try:
        r = requests.post(f"{SERVER_URL}/v1/models/switch", json={"model_id": model_id, "pec_mode": "auto"}, timeout=120)
        if r.ok:
            state["current_model"] = model_id
    except Exception:
        pass


def model_menu_items():
    reg = (load_cfg().get("model_registry") or autodetect_models())
    items = []
    for mid in reg.keys():
        def _mk(icon, item, m=mid):
            switch_model(m)
        items.append(Item(mid, _mk, checked=lambda i, m=mid: state.get("current_model") == m))
    if not items:
        items.append(Item("No models found", lambda i, x: None, enabled=False))
    return items


def open_model_config(icon=None, item=None):
    cfg = load_cfg()
    cfg["model_registry"] = autodetect_models() or cfg.get("model_registry", {})
    save_cfg(cfg)
    os.startfile(str(RUNTIME_CFG))


def open_system_wrapper(icon=None, item=None):
    os.startfile(str(ROOT / "start_runeforge_server.ps1"))


def shutdown_all(icon=None, item=None):
    stop_server(icon)
    icon.stop()


def build_menu():
    return pystray.Menu(
        Item("Open GUI", open_gui, default=True),
        Item("Start Server", lambda icon, item: start_server(icon)),
        Item("Restart Server", lambda icon, item: restart_server(icon)),
        Item("Stop Server", lambda icon, item: stop_server(icon)),
        Item("Load Model", lambda: pystray.Menu(*model_menu_items())),
        Item("Open Model Config Editor", open_model_config),
        Item("Open System Wrapper", open_system_wrapper),
        Item("Exit / Shutdown", shutdown_all),
    )


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "uploads").mkdir(exist_ok=True)
    (ROOT / "audio").mkdir(exist_ok=True)
    img = make_icon()
    icon = pystray.Icon("runeforge", img, "Runeforge Server", menu=build_menu())

    def setup(_icon):
        start_server(icon)
        threading.Thread(target=open_gui, daemon=True).start()

    icon.run(setup=setup)


if __name__ == "__main__":
    main()
