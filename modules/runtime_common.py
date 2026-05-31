from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone


def run_module_runtime(module_id: str, display_name: str) -> int:
    parser = argparse.ArgumentParser(description=f"{display_name} module runtime")
    parser.add_argument("--once", action="store_true", help="Emit one heartbeat payload and exit")
    parser.add_argument("--interval", type=int, default=15, help="Heartbeat interval seconds")
    args = parser.parse_args()

    interval = max(5, int(args.interval or 15))
    if args.once:
        print(
            json.dumps(
                {
                    "ok": True,
                    "module_id": module_id,
                    "display_name": display_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mode": "once",
                }
            )
        )
        return 0

    while True:
        print(
            json.dumps(
                {
                    "ok": True,
                    "module_id": module_id,
                    "display_name": display_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mode": "service",
                }
            ),
            flush=True,
        )
        time.sleep(interval)

