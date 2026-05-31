"""
SoundForge Engine v1.0
BossForgeOS deterministic sound engine.

Features:
- Real-time program open/close detection
- Per-executable sound mappings
- Default open/close sounds
- REST API for control + status
- Event log
- WebSocket event stream (BossForgeOS-compatible)
- Protocol v1 envelopes
"""

import os
import time
import threading
import json
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_sock import Sock
import psutil
import win32gui
import win32process
import win32con
import winsound

# =========================
# CONFIG
# =========================
DEFAULT_OPEN_SOUND = r"C:\Windows\Media\Windows Logon.wav"
DEFAULT_CLOSE_SOUND = r"C:\Windows\Media\Windows Logoff.wav"
POLL_RATE = 0.5
IGNORED_PROCESSES = {
    "explorer.exe",
    "SearchApp.exe",
    "ShellExperienceHost.exe"
}

SOUND_MAPPINGS = {
    "default_open": DEFAULT_OPEN_SOUND,
    "default_close": DEFAULT_CLOSE_SOUND,
}

# =========================
# STATE
# =========================
known_pids = {}
event_log = []
ws_clients = set()

# =========================
# HELPERS
# =========================
def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _wrap_event(event_type, data):
    return {
        "protocol_version": "1.0",
        "type": "event",
        "source": "soundforge",
        "event": event_type,
        "data": data,
        "timestamp": _now_iso(),
    }

# =========================
# WINDOW ENUMERATION
# =========================
def is_real_window(hwnd):
    if not win32gui.IsWindowVisible(hwnd):
        return False
    if win32gui.GetWindowText(hwnd) == "":
        return False
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    return bool(style & win32con.WS_OVERLAPPEDWINDOW)

def get_pid_exe(pid):
    try:
        return psutil.Process(pid).name()
    except Exception:
        return None

def enumerate_real_windows():
    hwnd_pid = {}
    def callback(hwnd, extra):
        if is_real_window(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            exe = get_pid_exe(pid)
            if exe and exe.lower() not in IGNORED_PROCESSES:
                hwnd_pid[pid] = exe
    win32gui.EnumWindows(callback, None)
    return hwnd_pid

# =========================
# SOUND PLAYBACK
# =========================
def play_sound(event, exe=None):
    path = None
    if exe and exe.lower() in SOUND_MAPPINGS:
        path = SOUND_MAPPINGS[exe.lower()].get(event)
    if not path:
        path = SOUND_MAPPINGS.get(f"default_{event}")
    if path and os.path.exists(path):
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)

# =========================
# MONITOR LOOP
# =========================
def monitor_loop():
    global known_pids
    while True:
        current = enumerate_real_windows()

        # Open events
        for pid, exe in current.items():
            if pid not in known_pids:
                payload = {"exe": exe, "pid": pid}
                event = _wrap_event("program_open", payload)
                event_log.append(event)
                play_sound("open", exe)
                _broadcast_ws(event)

        # Close events
        for pid, exe in list(known_pids.items()):
            if pid not in current:
                payload = {"exe": exe, "pid": pid}
                event = _wrap_event("program_close", payload)
                event_log.append(event)
                play_sound("close", exe)
                _broadcast_ws(event)

        known_pids = current
        time.sleep(POLL_RATE)

# =========================
# WEBSOCKET BROADCAST
# =========================
def _broadcast_ws(event):
    dead = []
    for ws in ws_clients:
        try:
            ws.send(json.dumps(event))
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)

# =========================
# HTTP + WS API
# =========================
app = Flask(__name__)
sock = Sock(app)

@app.route("/api/status")
def status():
    return jsonify({
        "known_pids": known_pids,
        "sound_mappings": SOUND_MAPPINGS,
        "log_length": len(event_log)
    })

@app.route("/api/play", methods=["POST"])
def play():
    data = request.json or {}
    event = data.get("event", "open")
    exe = data.get("exe")
    play_sound(event, exe)
    return jsonify({"ok": True})

@app.route("/api/mapping", methods=["POST"])
def set_mapping():
    data = request.json or {}
    exe = data.get("exe")
    open_path = data.get("open")
    close_path = data.get("close")
    if exe:
        SOUND_MAPPINGS[exe.lower()] = {}
        if open_path:
            SOUND_MAPPINGS[exe.lower()]["open"] = open_path
        if close_path:
            SOUND_MAPPINGS[exe.lower()]["close"] = close_path
    return jsonify({"ok": True, "sound_mappings": SOUND_MAPPINGS})

@app.route("/api/logs")
def logs():
    return jsonify(event_log)

@sock.route("/events")
def events(ws):
    ws_clients.add(ws)
    while True:
        try:
            ws.receive()
        except Exception:
            break
    ws_clients.remove(ws)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    app.run(port=5005)
