from __future__ import annotations

import json
from pathlib import Path

from modules.agentforge import service


def main() -> None:
    root = Path(__file__).resolve().parent
    payload_path = root / "agentforge_registration_payload.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    out = service.create_agent_profile(payload)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
