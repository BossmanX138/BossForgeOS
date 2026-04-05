import os
import time
import threading
import json
from flask import Flask, request, jsonify
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
POLL_RATE = 0.5  # seconds
IGNORED_PROCESSES = {
    "explorer.exe",
    "SearchApp.exe",
    "ShellExperienceHost.exe"
}
SOUND_MAPPINGS = {
    "default_open": DEFAULT_OPEN_SOUND,
    "default_close": DEFAULT_CLOSE_SOUND,
    # "notepad.exe": {"open": "...", "close": "..."}
}

# =========================
# STATE
# =========================
known_pids = {}
event_log = []

# =========================
# SOUND ENGINE CORE
# =========================
def is_real_window(hwnd):
    if not win32gui.IsWindowVisible(hwnd):
        return False
    if win32gui.GetWindowText(hwnd) == "":
        return False
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    if not (style & win32con.WS_OVERLAPPEDWINDOW):
        return False
    return True

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

def play_sound(event, exe=None):
    path = None
    if exe and exe.lower() in SOUND_MAPPINGS:
        path = SOUND_MAPPINGS[exe.lower()].get(event)
    if not path:
        path = SOUND_MAPPINGS.get(f"default_{event}")
    if path and os.path.exists(path):
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)

def monitor_loop():
    global known_pids
    while True:
        current = enumerate_real_windows()
        # Open events
        for pid, exe in current.items():
            if pid not in known_pids:
                play_sound("open", exe)
                event_log.append({"event": "open", "exe": exe, "pid": pid, "ts": time.time()})
        # Close events
        for pid, exe in list(known_pids.items()):
            if pid not in current:
                play_sound("close", exe)
                event_log.append({"event": "close", "exe": exe, "pid": pid, "ts": time.time()})
        known_pids = current
        time.sleep(POLL_RATE)

# =========================
# HTTP API
# =========================
app = Flask(__name__)

@app.route("/status")
def status():
    return jsonify({
        "known_pids": known_pids,
        "sound_mappings": SOUND_MAPPINGS,
        "log_length": len(event_log)
    })

@app.route("/play", methods=["POST"])
def play():
    data = request.json or {}
    event = data.get("event", "open")
    exe = data.get("exe")
    play_sound(event, exe)
    return jsonify({"ok": True})

@app.route("/set-mapping", methods=["POST"])
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

@app.route("/log")
def log():
    return jsonify(event_log)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    app.run(port=5005)
