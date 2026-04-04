"""
Runeforge Webhook Listener Service

- HTTP POST endpoint at /webhook (default port 8081)
- Payload size limit: 16KB
- Replay protection: nonce+timestamp
- Optional HMAC signature validation (set RUNEFORGE_WEBHOOK_SECRET env var)
- Emits normalized ingress events to Rune Bus
"""

import os
import time
import hmac
import hashlib
from flask import Flask, request, abort, jsonify
from core.rune_bus import RuneBus, resolve_root_from_env

MAX_PAYLOAD_SIZE = 16 * 1024  # 16KB
REPLAY_WINDOW = 120  # seconds
NONCE_CACHE = set()
SECRET = os.environ.get("RUNEFORGE_WEBHOOK_SECRET", "")

app = Flask(__name__)
bus = RuneBus(resolve_root_from_env())

@app.route("/webhook", methods=["POST"])
def webhook():
    # Enforce payload size
    if request.content_length is None or request.content_length > MAX_PAYLOAD_SIZE:
        abort(413, description="Payload too large")
    data = request.get_data()
    try:
        payload = request.get_json(force=True)
    except Exception:
        abort(400, description="Invalid JSON")

    # Replay protection
    nonce = str(payload.get("nonce", ""))
    timestamp = int(payload.get("timestamp", 0))
    now = int(time.time())
    if not nonce or not timestamp or abs(now - timestamp) > REPLAY_WINDOW:
        abort(400, description="Missing or stale nonce/timestamp")
    key = f"{nonce}:{timestamp}"
    if key in NONCE_CACHE:
        abort(409, description="Replay detected")
    NONCE_CACHE.add(key)
    # Prune old nonces
    if len(NONCE_CACHE) > 10000:
        NONCE_CACHE.clear()

    # Optional signature validation
    if SECRET:
        sig = request.headers.get("X-Hub-Signature-256", "")
        mac = hmac.new(SECRET.encode(), data, hashlib.sha256).hexdigest()
        expected = f"sha256={mac}"
        if not hmac.compare_digest(sig, expected):
            abort(401, description="Invalid signature")

    # Normalize and emit event
    event = {
        "source": "runeforge_webhook",
        "received_at": now,
        "payload": payload,
        "remote_addr": request.remote_addr,
    }
    bus.emit_event("runeforge", "webhook:ingress", event)
    return jsonify({"ok": True, "message": "Webhook received"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
