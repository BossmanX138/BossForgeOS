import os
import shutil
import subprocess
import json
from pathlib import Path
from typing import Any, Dict, Optional

import psutil

from core.rune_bus import resolve_root_from_env


def snapshot_disk() -> Dict[str, Any]:
    root = Path.home().anchor or "C:\\"
    usage = shutil.disk_usage(root)
    total_gb = round(usage.total / (1024**3), 1)
    used_gb = round(usage.used / (1024**3), 1)
    free_gb = round(usage.free / (1024**3), 1)
    percent = round((usage.used / usage.total) * 100, 1) if usage.total else 0.0
    return {
        "root": root,
        "total_gb": total_gb,
        "used_gb": used_gb,
        "free_gb": free_gb,
        "percent": percent,
    }


def snapshot_docker() -> Optional[Dict[str, Any]]:
    if shutil.which("docker") is None:
        return None
    try:
        out = subprocess.check_output(
            ["docker", "system", "df", "--format", "{{json .}}"],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
        if not out:
            return None
        first = out.splitlines()[0]
        import json

        data = json.loads(first)
        return {
            "disk_used": data.get("Size") or data.get("DiskUsed"),
            "reclaimable": data.get("Reclaimable"),
            "type": data.get("Type"),
        }
    except Exception:
        return None


def snapshot_wsl_vhd() -> Optional[Dict[str, Any]]:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    vhd = Path(local_app_data) / "Docker" / "wsl" / "data" / "ext4.vhdx"
    if not vhd.exists():
        return None
    size_gb = round(vhd.stat().st_size / (1024**3), 2)
    return {"path": str(vhd), "size_gb": size_gb}


def snapshot_system_resources() -> Dict[str, Any]:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "cpu_percent": round(psutil.cpu_percent(interval=0.0), 1),
        "memory": {
            "total_gb": round(vm.total / (1024**3), 2),
            "used_gb": round(vm.used / (1024**3), 2),
            "available_gb": round(vm.available / (1024**3), 2),
            "percent": round(vm.percent, 1),
        },
        "swap": {
            "total_gb": round(swap.total / (1024**3), 2),
            "used_gb": round(swap.used / (1024**3), 2),
            "percent": round(swap.percent, 1),
        },
    }


def snapshot_gpu_vram() -> Optional[Dict[str, Any]]:
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        return None

    gpus: list[Dict[str, Any]] = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        name = parts[0]
        try:
            total_mb = float(parts[1])
            used_mb = float(parts[2])
            free_mb = float(parts[3])
            util_percent = float(parts[4])
        except ValueError:
            continue
        percent = round((used_mb / total_mb) * 100, 1) if total_mb else 0.0
        gpus.append(
            {
                "name": name,
                "total_gb": round(total_mb / 1024.0, 2),
                "used_gb": round(used_mb / 1024.0, 2),
                "free_gb": round(free_mb / 1024.0, 2),
                "percent": percent,
                "utilization_percent": round(util_percent, 1),
            }
        )

    if not gpus:
        return None
    return {"gpus": gpus}


def snapshot_agent_load() -> Dict[str, Any]:
    root = resolve_root_from_env()
    state_dir = root / "bus" / "state"
    pids: dict[str, int] = {}

    for known in ["hearth_tender", "archivist", "model_gateway", "security_sentinel"]:
        path = state_dir / f"{known}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pid = payload.get("pid")
        if isinstance(pid, int):
            pids[known] = pid

    model_gateway_state = state_dir / "model_gateway.json"
    if model_gateway_state.exists():
        try:
            payload = json.loads(model_gateway_state.read_text(encoding="utf-8"))
            servers = payload.get("servers", [])
            if isinstance(servers, list):
                for item in servers:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name", "")).strip()
                    pid = item.get("pid")
                    if name and isinstance(pid, int):
                        pids[f"model_server:{name}"] = pid
        except (OSError, json.JSONDecodeError):
            pass

    processes: list[Dict[str, Any]] = []
    total_rss_mb = 0.0
    total_cpu = 0.0
    for label, pid in pids.items():
        try:
            proc = psutil.Process(pid)
            rss_mb = round(proc.memory_info().rss / (1024**2), 1)
            cpu = round(proc.cpu_percent(interval=0.0), 1)
            total_rss_mb += rss_mb
            total_cpu += cpu
            processes.append(
                {
                    "agent": label,
                    "pid": pid,
                    "name": proc.name(),
                    "cpu_percent": cpu,
                    "rss_mb": rss_mb,
                    "status": proc.status(),
                }
            )
        except Exception:
            processes.append(
                {
                    "agent": label,
                    "pid": pid,
                    "status": "missing",
                }
            )

    return {
        "tracked_processes": processes,
        "totals": {
            "cpu_percent": round(total_cpu, 1),
            "rss_gb": round(total_rss_mb / 1024.0, 3),
        },
    }


def build_pressure_warnings(snapshot: Dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    disk_pct = float(snapshot.get("disk", {}).get("percent", 0.0))
    mem_pct = float(snapshot.get("system", {}).get("memory", {}).get("percent", 0.0))
    swap_pct = float(snapshot.get("system", {}).get("swap", {}).get("percent", 0.0))

    if disk_pct >= 90.0:
        warnings.append(f"disk critical: {disk_pct}% used")
    elif disk_pct >= 80.0:
        warnings.append(f"disk high: {disk_pct}% used")

    if mem_pct >= 90.0:
        warnings.append(f"ram critical: {mem_pct}% used")
    elif mem_pct >= 80.0:
        warnings.append(f"ram high: {mem_pct}% used")

    if swap_pct >= 75.0:
        warnings.append(f"swap high: {swap_pct}% used")

    gpu = snapshot.get("gpu_vram") or {}
    gpus = gpu.get("gpus") if isinstance(gpu, dict) else None
    if isinstance(gpus, list):
        for idx, info in enumerate(gpus):
            try:
                pct = float((info or {}).get("percent", 0.0))
            except (TypeError, ValueError):
                pct = 0.0
            if pct >= 90.0:
                warnings.append(f"vram critical on gpu{idx}: {pct}% used")
            elif pct >= 80.0:
                warnings.append(f"vram high on gpu{idx}: {pct}% used")

    return warnings


def snapshot_all() -> Dict[str, Any]:
    payload = {
        "disk": snapshot_disk(),
        "docker": snapshot_docker(),
        "wsl_vhd": snapshot_wsl_vhd(),
        "system": snapshot_system_resources(),
        "gpu_vram": snapshot_gpu_vram(),
        "agent_load": snapshot_agent_load(),
    }
    payload["warnings"] = build_pressure_warnings(payload)
    return payload
