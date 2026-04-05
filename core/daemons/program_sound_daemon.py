"""
Program Sound Daemon for BossForgeOS
Restores deterministic Open/Close Program sounds (Windows 7 style)

- Monitors real, user-facing programs (top-level windows + PIDs)
- Ignores hidden/system windows
- Plays user-configurable WAVs on true open/close events
- Ready for event bus integration

Requires: pywin32 (pip install pywin32)
"""

import time
import os
import sys
import threading

import json
import win32gui
import win32process
import win32con
import win32api
import winsound
import wmi
import pythoncom
import ctypes
import threading
from pynput import mouse, keyboard

# === Managed Sound Directory Logic ===
import shutil

import random
import wave
import contextlib
import tempfile
import subprocess

SOUNDSTAGE_SCHEMES_DIR = os.path.join(os.path.dirname(__file__), "soundstage_schemes")
SOUNDSTAGE_SOUNDS_DIR = os.path.join(SOUNDSTAGE_SCHEMES_DIR, "sounds")
os.makedirs(SOUNDSTAGE_SOUNDS_DIR, exist_ok=True)


def resolve_sound_path(path):
    if not path:
        return None
    if os.path.isabs(path) and os.path.exists(path):
        return path
    # Try managed dir
    managed = os.path.join(SOUNDSTAGE_SOUNDS_DIR, os.path.basename(path))
    if os.path.exists(managed):
        return managed
    # Fallback: original path
    return path if os.path.exists(path) else None

def select_sound_entry(event, exe=None):
    """
    Selects the sound entry for a given event, considering per-app overrides.
    Returns dict with keys: files (list), volume, rate
    """
    # Per-app override
    if exe and config.get("per_app", {}).get(exe, {}).get(event):
        entry = config["per_app"][exe][event]
    else:
        entry = config.get("global", {}).get(event, {})
    # Defaults
    files = entry.get("files", []) if entry else []
    volume = entry.get("volume", 1.0) if entry else 1.0
    rate = entry.get("rate", 1.0) if entry else 1.0
    return {"files": files, "volume": volume, "rate": rate}

def pick_random_sound(files):
    if not files:
        return None
    return random.choice(files)

def play_sound_advanced(event, exe=None):
    entry = select_sound_entry(event, exe)
    files = entry["files"]
    volume = entry["volume"]
    rate = entry["rate"]
    sound_path = pick_random_sound(files)
    resolved = resolve_sound_path(sound_path)
    if resolved:
        # If volume/rate are default, use winsound
        if volume == 1.0 and rate == 1.0:
            winsound.PlaySound(resolved, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            # Use ffplay (if available) for volume/rate adjustment
            # This is a best-effort; fallback to normal if ffplay not found
            try:
                cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-volume", str(int(volume*100)), "-af", f"atempo={rate}", resolved]
                subprocess.Popen(cmd)
            except Exception:
                winsound.PlaySound(resolved, winsound.SND_FILENAME | winsound.SND_ASYNC)
        log_diagnostics(event, exe, resolved, volume, rate)

def log_diagnostics(event, exe, path, volume, rate):
    try:
        diag_path = os.path.join(os.path.dirname(__file__), "soundstage_diagnostics.log")
        with open(diag_path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | event={event} | exe={exe} | path={path} | volume={volume} | rate={rate}\n")
    except Exception:
        pass

def import_sound_file(src_path):
    """Copy a sound file into the managed directory, return new path."""
    if not src_path or not os.path.exists(src_path):
        return None
    dst = os.path.join(SOUNDSTAGE_SOUNDS_DIR, os.path.basename(src_path))
    shutil.copy2(src_path, dst)
    return dst


# =========================
# CONFIG
# =========================
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "soundstage_config.json")
DEFAULT_POLL_RATE = 0.5  # seconds

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[SoundStage] Failed to load config: {e}")
        return {}

config = load_config()
IGNORED_EXES = {
    "explorer.exe",
    "SearchApp.exe",
    "ShellExperienceHost.exe",
}
POLL_RATE = config.get("poll_rate", DEFAULT_POLL_RATE)

def is_real_window(hwnd):
    '''Return True if hwnd is a real, visible, user-facing window.'''
    if not win32gui.IsWindowVisible(hwnd):
        return False
    if win32gui.IsIconic(hwnd):  # Minimized
        return False
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    if not (style & win32con.WS_OVERLAPPEDWINDOW):
        return False
    title = win32gui.GetWindowText(hwnd)
    if not title.strip():
        return False
    # Tool windows, etc.
    exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    if exstyle & win32con.WS_EX_TOOLWINDOW:
        return False
    return True

def get_window_pid(hwnd):
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return pid
    except Exception:
        return None

def get_process_exe(pid):
    try:
        hproc = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
        exe = win32process.GetModuleFileNameEx(hproc, 0)
        win32api.CloseHandle(hproc)
        return os.path.basename(exe).lower()
    except Exception:
        return None




# Legacy compatibility
def play_sound(path):
    play_sound_advanced(event="manual", exe=None)


# === Event Handlers ===
def handle_program_events(stop_event=None):
    """Detects real program open/close and plays mapped sounds (per-app, random, volume/rate)."""
    known = dict()  # pid -> exe
    while not (stop_event and stop_event.is_set()):
        current = dict()
        def enum_handler(hwnd, _):
            if not is_real_window(hwnd):
                return
            pid = get_window_pid(hwnd)
            if not pid:
                return
            exe = get_process_exe(pid)
            if not exe or exe in IGNORED_EXES:
                return
            if pid not in current:
                current[pid] = exe
        win32gui.EnumWindows(enum_handler, None)
        # Detect new programs
        for pid, exe in current.items():
            if pid not in known:
                play_sound_advanced("open_program", exe)
        # Detect closed programs
        for pid, exe in known.items():
            if pid not in current:
                play_sound_advanced("close_program", exe)
        known = current
        time.sleep(POLL_RATE)


# === Additional Event Handlers ===
def handle_device_events(stop_event=None):
    """Detect device connect/disconnect using WMI."""
    pythoncom.CoInitialize()
    c = wmi.WMI()
    watcher_connect = c.Win32_DeviceChangeEvent.watch_for(notification_type="Creation")
    watcher_disconnect = c.Win32_DeviceChangeEvent.watch_for(notification_type="Deletion")
    while not (stop_event and stop_event.is_set()):
        try:
            event = watcher_connect(timeout_ms=500)
            if event:
                play_sound_advanced("device_connect")
        except wmi.x_wmi_timed_out:
            pass
        try:
            event = watcher_disconnect(timeout_ms=500)
            if event:
                play_sound_advanced("device_disconnect")
        except wmi.x_wmi_timed_out:
            pass

def handle_system_notification(stop_event=None):
    """Best-effort: Listen for system notification beeps using MessageBeep polling (not perfect)."""
    last_title = None
    while not (stop_event and stop_event.is_set()):
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        # Heuristic: if a window with 'Notification' or 'Toast' in title appears, play sound
        if title != last_title and ("notification" in title.lower() or "toast" in title.lower()):
            play_sound_advanced("system_notification")
        last_title = title
        time.sleep(0.2)

def handle_minimize_maximize(stop_event=None):
    """Poll all top-level windows for minimize/maximize/restore events."""
    window_states = {}
    while not (stop_event and stop_event.is_set()):
        def enum_handler(hwnd, states):
            if not is_real_window(hwnd):
                return
            pid = get_window_pid(hwnd)
            if not pid:
                return
            state = win32gui.IsZoomed(hwnd), win32gui.IsIconic(hwnd)
            states[hwnd] = state
        current_states = {}
        win32gui.EnumWindows(enum_handler, current_states)
        # Compare with previous
        for hwnd, state in current_states.items():
            prev = window_states.get(hwnd)
            if prev:
                # Minimized
                if not prev[1] and state[1]:
                    play_sound_advanced("minimize")
                # Maximized
                if not prev[0] and state[0]:
                    play_sound_advanced("maximize")
                # Restored
                if (prev[1] or prev[0]) and not (state[1] or state[0]):
                    play_sound_advanced("restore")
        window_states = current_states
        time.sleep(0.2)

def handle_menu_popup(stop_event=None):
    """Best-effort: Poll for menu popup/command by checking for new menu windows (heuristic)."""
    seen_menus = set()
    while not (stop_event and stop_event.is_set()):
        def enum_handler(hwnd, menus):
            class_name = win32gui.GetClassName(hwnd)
            if class_name in ("#32768", "DV2ControlHost"):  # #32768 is standard menu class
                menus.add(hwnd)
        menus = set()
        win32gui.EnumWindows(enum_handler, menus)
        # New menu popup
        for hwnd in menus:
            if hwnd not in seen_menus:
                play_sound_advanced("menu_popup")
        # Menu command (menu closes)
        for hwnd in seen_menus:
            if hwnd not in menus:
                play_sound_advanced("menu_command")
        seen_menus = menus
        time.sleep(0.1)

def handle_empty_recycle_bin(stop_event=None):
    """Poll for empty recycle bin event (best-effort)."""
    SHQueryRecycleBinW = ctypes.windll.shell32.SHQueryRecycleBinW
    class SHQUERYRBINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong),
                    ("i64Size", ctypes.c_longlong),
                    ("i64NumItems", ctypes.c_longlong)]
    last_items = None
    while not (stop_event and stop_event.is_set()):
        rbinfo = SHQUERYRBINFO()
        rbinfo.cbSize = ctypes.sizeof(SHQUERYRBINFO)
        res = SHQueryRecycleBinW(None, ctypes.byref(rbinfo))
        items = rbinfo.i64NumItems
        if last_items is not None and last_items > 0 and items == 0:
            play_sound_advanced("empty_recycle_bin")
        last_items = items
        time.sleep(0.5)

def handle_mouse_left_click(stop_event=None):
    """Listen for mouse left click events and play mapped sound."""
    def on_click(x, y, button, pressed):
        if stop_event and stop_event.is_set():
            return False
        if button == mouse.Button.left and pressed:
            play_sound_advanced("mouse_left_click")
    listener = mouse.Listener(on_click=on_click)
    listener.start()
    while not (stop_event and stop_event.is_set()):
        time.sleep(0.1)
    listener.stop()

def handle_keyboard_key_press(stop_event=None):
    """Listen for keyboard key press events and play mapped sound."""
    def on_press(key):
        if stop_event and stop_event.is_set():
            return False
        play_sound_advanced("keyboard_key_press")
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    while not (stop_event and stop_event.is_set()):
        time.sleep(0.1)
    listener.stop()



def main():
    print("[SoundStage] Starting. Press Ctrl+C to exit.")
    stop_event = threading.Event()
    threads = []
    # Start all event handlers in background threads
    threads.append(threading.Thread(target=handle_program_events, kwargs={"stop_event": stop_event}, daemon=True))
    threads.append(threading.Thread(target=handle_device_events, kwargs={"stop_event": stop_event}, daemon=True))
    threads.append(threading.Thread(target=handle_system_notification, kwargs={"stop_event": stop_event}, daemon=True))
    threads.append(threading.Thread(target=handle_minimize_maximize, kwargs={"stop_event": stop_event}, daemon=True))
    threads.append(threading.Thread(target=handle_menu_popup, kwargs={"stop_event": stop_event}, daemon=True))
    threads.append(threading.Thread(target=handle_empty_recycle_bin, kwargs={"stop_event": stop_event}, daemon=True))
    threads.append(threading.Thread(target=handle_mouse_left_click, kwargs={"stop_event": stop_event}, daemon=True))
    threads.append(threading.Thread(target=handle_keyboard_key_press, kwargs={"stop_event": stop_event}, daemon=True))
    for t in threads:
        t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[SoundStage] Exiting.")
        stop_event.set()
        for t in threads:
            t.join(timeout=2)

if __name__ == "__main__":
    main()
