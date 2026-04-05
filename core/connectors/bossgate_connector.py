import socket
import json
import threading
import time
from typing import Any, Callable
from urllib.parse import urlparse
from urllib import request

BOSSGATE_PORT = 50505
BOSSGATE_BEACON = b'BOSSGATE-ASS-PAIRING'
BOSSGATE_BEACON_PREFIX = b'BOSSGATE-PRESENCE:'

ALLOWED_TRAVEL_TARGET_TYPES = {
    "bossgate_connector",
    "ass",
    "bossforgeos",
    "bridgebase_alpha",
}

TARGET_SIGNATURES = {
    "bossgate_connector": (
        "bossgate",
        "bossgate connector",
        "bossgate",
    ),
    "ass": (
        "a.s.s",
        "ass",
        "autonomous security system",
    ),
    "bossforgeos": (
        "bossforgeos",
        "bossforge os",
    ),
    "bridgebase_alpha": (
        "bridgebase_alpha",
        "bridgebase alpha",
    ),
}


def _normalize_url_for_scan(raw_url: str) -> str:
    url = (raw_url or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    if not parsed.scheme:
        return f"http://{url}"
    return url


def _collect_identity_text(metadata: dict) -> str:
    parts = []
    for key in (
        "server",
        "x-powered-by",
        "x-bossgate-role",
        "x-bossgate-target-type",
        "title",
        "description",
        "name",
    ):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip().lower())
    return "\n".join(parts)


def classify_target_type(metadata: dict) -> str:
    corpus = _collect_identity_text(metadata)
    if not corpus:
        return "unknown"
    for target_type, signatures in TARGET_SIGNATURES.items():
        for signature in signatures:
            if signature in corpus:
                return target_type
    return "unknown"


def is_valid_transfer_target(metadata: dict) -> tuple[bool, str]:
    target_type = classify_target_type(metadata)
    return target_type in ALLOWED_TRAVEL_TARGET_TYPES, target_type


def _normalize_agent_presence(raw_agents: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    for item in raw_agents or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip().lower()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "agent_class": str(item.get("agent_class", "prime")).strip().lower() or "prime",
                "bossgate_enabled": bool(item.get("bossgate_enabled", True)),
                "created_by_node": str(item.get("created_by_node", "")).strip(),
                "current_node": str(item.get("current_node", "")).strip(),
                "assistance_requested": bool(item.get("assistance_requested", False)),
                "assistance_reason": str(item.get("assistance_reason", "")).strip(),
            }
        )
    return out


def _build_presence_packet(node_id: str, agents: list[dict] | None = None, target_type: str = "bossgate_connector") -> bytes:
    payload = {
        "version": 1,
        "node_id": str(node_id or "unknown-node").strip(),
        "target_type": str(target_type or "bossgate_connector").strip().lower(),
        "agents": _normalize_agent_presence(agents),
        "timestamp": int(time.time()),
    }
    return BOSSGATE_BEACON_PREFIX + json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _parse_presence_packet(data: bytes, sender_ip: str) -> dict[str, Any] | None:
    if data == BOSSGATE_BEACON:
        return {
            "address": sender_ip,
            "node_id": sender_ip,
            "target_type": "bossgate_connector",
            "agents": [],
            "legacy": True,
        }

    if not data.startswith(BOSSGATE_BEACON_PREFIX):
        return None

    try:
        payload = json.loads(data[len(BOSSGATE_BEACON_PREFIX):].decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    timestamp_raw = payload.get("timestamp")
    timestamp = int(timestamp_raw) if isinstance(timestamp_raw, int) else 0
    return {
        "address": sender_ip,
        "node_id": str(payload.get("node_id", sender_ip)).strip() or sender_ip,
        "target_type": str(payload.get("target_type", "bossgate_connector")).strip().lower() or "bossgate_connector",
        "agents": _normalize_agent_presence(payload.get("agents") if isinstance(payload.get("agents"), list) else []),
        "legacy": False,
        "timestamp": timestamp,
    }


# --- LAN Beacon/Discovery ---
def broadcast_presence(
    node_id: str,
    agents_provider: Callable[[], list[dict]] | None = None,
    interval_seconds: float = 2.0,
    stop_event: threading.Event | None = None,
) -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    while stop_event is None or not stop_event.is_set():
        agents = agents_provider() if callable(agents_provider) else []
        packet = _build_presence_packet(node_id=node_id, agents=agents, target_type="bossgate_connector")
        s.sendto(packet, ('<broadcast>', BOSSGATE_PORT))
        time.sleep(max(0.2, float(interval_seconds)))


def broadcast_beacon(node_id: str | None = None, agents_provider: Callable[[], list[dict]] | None = None):
    node_name = (node_id or socket.gethostname() or "unknown-node").strip()
    broadcast_presence(node_id=node_name, agents_provider=agents_provider)


def listen_for_beacons(timeout=5):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.bind(('', BOSSGATE_PORT))
    s.settimeout(timeout)
    found: dict[tuple[str, str], dict[str, Any]] = {}
    start = time.time()
    while time.time() - start < timeout:
        try:
            data, addr = s.recvfrom(4096)
            parsed = _parse_presence_packet(data=data, sender_ip=addr[0])
            if parsed is not None:
                found[(parsed["address"], parsed["node_id"])] = parsed
        except socket.timeout:
            break
    return list(found.values())


def discover_transfer_targets(timeout=5, assistance_only: bool = False):
    peers = listen_for_beacons(timeout=timeout)
    targets: list[dict[str, Any]] = []
    for peer in peers:
        address = str(peer.get("address", "")).strip()
        node_id = str(peer.get("node_id", address)).strip() or address
        target_type = str(peer.get("target_type", "bossgate_connector")).strip().lower() or "bossgate_connector"
        agents = peer.get("agents") if isinstance(peer.get("agents"), list) else []

        if not agents:
            if assistance_only:
                continue
            targets.append(
                {
                    "address": address,
                    "node_id": node_id,
                    "agent_name": "",
                    "target_type": target_type,
                    "allowed_for_transfer": target_type in ALLOWED_TRAVEL_TARGET_TYPES,
                    "assistance_requested": False,
                    "reason": "validated by BossGate beacon",
                }
            )
            continue

        for agent in agents:
            assistance_requested = bool(agent.get("assistance_requested", False))
            if assistance_only and not assistance_requested:
                continue
            targets.append(
                {
                    "address": address,
                    "node_id": node_id,
                    "agent_name": str(agent.get("name", "")).strip().lower(),
                    "agent_class": str(agent.get("agent_class", "prime")).strip().lower() or "prime",
                    "created_by_node": str(agent.get("created_by_node", "")).strip(),
                    "current_node": str(agent.get("current_node", node_id)).strip() or node_id,
                    "target_type": target_type,
                    "allowed_for_transfer": target_type in ALLOWED_TRAVEL_TARGET_TYPES and bool(agent.get("bossgate_enabled", True)),
                    "assistance_requested": assistance_requested,
                    "assistance_reason": str(agent.get("assistance_reason", "")).strip(),
                    "reason": "agent presence beacon",
                }
            )
    return targets


def _http_get_json(url: str, timeout: float = 2.0):
    req = request.Request(url=url, method="GET")
    with request.urlopen(req, timeout=timeout) as resp:
        status = int(getattr(resp, "status", 200))
        headers = {k: v for k, v in resp.headers.items()}
        body = resp.read().decode("utf-8", errors="replace")
    payload = json.loads(body)
    return status, headers, payload


def _http_get_headers(url: str, timeout: float = 2.0):
    req = request.Request(url=url, method="GET")
    with request.urlopen(req, timeout=timeout) as resp:
        status = int(getattr(resp, "status", 200))
        headers = {k: v for k, v in resp.headers.items()}
    return status, headers


def _http_options_headers(url: str, timeout: float = 2.0):
    req = request.Request(url=url, method="OPTIONS")
    with request.urlopen(req, timeout=timeout) as resp:
        status = int(getattr(resp, "status", 200))
        headers = {k: v for k, v in resp.headers.items()}
    return status, headers


# --- REST Endpoint Scanning ---
def scan_rest_endpoints(base_url):
    base_url = _normalize_url_for_scan(base_url)
    if not base_url:
        return {
            "ok": False,
            "allowed_for_transfer": False,
            "target_type": "unknown",
            "reason": "base_url is required",
            "base_url": "",
            "endpoints": [],
        }

    candidates = [
        '/openapi.json', '/swagger.json', '/swagger/v1/swagger.json', '/api/docs', '/docs/openapi.json'
    ]
    endpoints = []
    metadata = {}

    try:
        _, probe_headers = _http_get_headers(base_url.rstrip('/') + '/health', timeout=2)
        metadata = {
            "server": probe_headers.get("Server", ""),
            "x-powered-by": probe_headers.get("X-Powered-By", ""),
            "x-bossgate-role": probe_headers.get("X-BossGate-Role", ""),
            "x-bossgate-target-type": probe_headers.get("X-BossGate-Target-Type", ""),
        }
    except Exception:
        metadata = {}

    for path in candidates:
        try:
            status, headers, data = _http_get_json(base_url.rstrip('/') + path, timeout=2)
            if status == 200 and 'application/json' in headers.get('Content-Type', ''):
                info = data.get('info') if isinstance(data, dict) else {}
                if isinstance(info, dict):
                    if isinstance(info.get('title'), str):
                        metadata['title'] = info.get('title', '')
                    if isinstance(info.get('description'), str):
                        metadata['description'] = info.get('description', '')
                if 'paths' in data:
                    for ep, methods in data['paths'].items():
                        endpoints.append({'path': ep, 'methods': list(methods.keys())})
                break
        except Exception:
            continue

    if not endpoints:
        common = ['/api', '/health', '/status', '/v1', '/v2']
        for path in common:
            try:
                status, headers = _http_options_headers(base_url.rstrip('/') + path, timeout=2)
                if status < 400:
                    endpoints.append({'path': path, 'methods': headers.get('Allow', '').split(',')})
            except Exception:
                continue

    allowed, target_type = is_valid_transfer_target(metadata)
    if not allowed:
        return {
            "ok": False,
            "allowed_for_transfer": False,
            "target_type": target_type,
            "reason": "Destination rejected: transfer is only allowed to BossGate Connector, A.S.S., BossForgeOS, or bridgebase_alpha targets.",
            "base_url": base_url,
            "endpoints": [],
            "metadata": metadata,
        }

    return {
        "ok": True,
        "allowed_for_transfer": True,
        "target_type": target_type,
        "reason": "Destination validated for transfer.",
        "base_url": base_url,
        "endpoints": endpoints,
        "metadata": metadata,
    }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='BossGate Connector Prototype')
    parser.add_argument('--scan', metavar='URL', help='Scan a REST app for endpoints (e.g. http://localhost:8000/)')
    parser.add_argument('--beacon', action='store_true', help='Broadcast BossGate beacon on LAN')
    parser.add_argument('--discover', action='store_true', help='Discover BossGate/A.S.S. beacons on LAN')
    parser.add_argument('--node-id', default=socket.gethostname(), help='Node identifier to include in broadcast beacons')
    parser.add_argument('--assistance-only', action='store_true', help='Only return agents requesting assistance')
    args = parser.parse_args()

    if args.beacon:
        print('Broadcasting BossGate beacon...')
        threading.Thread(target=broadcast_beacon, kwargs={"node_id": args.node_id}, daemon=True).start()
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            print('Stopped.')
    elif args.discover:
        print('Listening for BossGate/A.S.S. beacons...')
        found = discover_transfer_targets(assistance_only=args.assistance_only)
        print('Found devices:', found)
    elif args.scan:
        print(f'Scanning {args.scan} for REST endpoints...')
        eps = scan_rest_endpoints(args.scan)
        print(json.dumps(eps, indent=2))
    else:
        parser.print_help()
