import argparse
import json
import tkinter as tk
from tkinter import scrolledtext
from urllib import parse, request


VIEW_LABELS = {
    "view_status": "Agent Status",
    "view_snapshot": "OS Snapshot",
    "view_commands": "Quick Commands",
    "view_manual": "Manual Command",
    "view_seal": "Archivist Seal Queue",
    "view_events": "Recent Events",
    "view_chat": "Model Chat",
    "view_maker": "Agent Maker",
    "view_security": "Security Sentinel",
}


def _fetch_json(url: str) -> dict:
    req = request.Request(url, headers={"Accept": "application/json"})
    with request.urlopen(req, timeout=4) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    return data if isinstance(data, dict) else {"ok": False, "message": "invalid response"}


def _content_for_view(base_url: str, view: str) -> dict:
    if view == "view_status":
        return _fetch_json(f"{base_url}/api/status")
    if view == "view_snapshot":
        return _fetch_json(f"{base_url}/api/snapshot")
    if view == "view_seal":
        return _fetch_json(f"{base_url}/api/archivist/seal")
    if view == "view_events":
        return _fetch_json(f"{base_url}/api/events?limit=40")
    if view == "view_security":
        return _fetch_json(f"{base_url}/api/security/state")
    if view == "view_commands":
        return {
            "ok": True,
            "message": "Quick Commands panel is interactive in Control Hall. Keep this pin window open for status while using commands in the main UI.",
        }
    if view == "view_manual":
        return {
            "ok": True,
            "message": "Manual Command panel is interactive in Control Hall. This floating pin stays always on top and draggable.",
        }
    if view == "view_chat":
        return {
            "ok": True,
            "message": "Model Chat remains interactive in Control Hall. This pin window can monitor status and events while you chat.",
        }
    if view == "view_maker":
        return _fetch_json(f"{base_url}/api/model/agents")
    return {"ok": False, "message": f"Unsupported view: {view}"}


class PinOverlay:
    def __init__(self, base_url: str, view: str, interval_ms: int = 2500, alpha: float = 0.95) -> None:
        self.base_url = base_url.rstrip("/")
        self.view = view
        self.interval_ms = max(1000, interval_ms)
        self.alpha = max(0.35, min(1.0, float(alpha)))

        self.root = tk.Tk()
        self.root.title(f"BossForge Pin - {VIEW_LABELS.get(self.view, self.view)}")
        self.root.geometry("760x480+120+120")
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", self.alpha)
        except Exception:
            pass

        frame = tk.Frame(self.root, bg="#0f1723")
        frame.pack(fill=tk.BOTH, expand=True)

        top = tk.Frame(frame, bg="#132236")
        top.pack(fill=tk.X, padx=8, pady=(8, 4))

        self.title_var = tk.StringVar(value=f"Pinned: {VIEW_LABELS.get(self.view, self.view)}")
        title = tk.Label(top, textvariable=self.title_var, fg="#f6c667", bg="#132236", anchor="w", font=("Bahnschrift", 11, "bold"))
        title.pack(side=tk.LEFT, padx=(8, 6), pady=6)

        refresh_btn = tk.Button(top, text="Refresh", command=self.refresh_now)
        refresh_btn.pack(side=tk.RIGHT, padx=6, pady=6)

        close_btn = tk.Button(top, text="Close", command=self.root.destroy)
        close_btn.pack(side=tk.RIGHT, padx=6, pady=6)

        self.text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, bg="#0d1622", fg="#eaf2ff", insertbackground="#eaf2ff")
        self.text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))

    def refresh_now(self) -> None:
        try:
            data = _content_for_view(self.base_url, self.view)
        except Exception as ex:
            data = {"ok": False, "message": str(ex)}

        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, json.dumps(data, indent=2))
        self.text.configure(state=tk.DISABLED)

    def _tick(self) -> None:
        self.refresh_now()
        self.root.after(self.interval_ms, self._tick)

    def run(self) -> None:
        self.refresh_now()
        self.root.after(self.interval_ms, self._tick)
        self.root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS floating pin overlay")
    parser.add_argument("--view", default="view_status")
    parser.add_argument("--base-url", default="http://127.0.0.1:5005")
    parser.add_argument("--interval-ms", type=int, default=2500)
    parser.add_argument("--alpha", type=float, default=0.95)
    args = parser.parse_args()

    view = parse.unquote_plus(str(args.view).strip())
    overlay = PinOverlay(base_url=str(args.base_url), view=view, interval_ms=args.interval_ms, alpha=args.alpha)
    overlay.run()


if __name__ == "__main__":
    main()
