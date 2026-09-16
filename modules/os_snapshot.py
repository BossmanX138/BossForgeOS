import os
import shutil
import subprocess
import json
from pathlib import Path
from typing import Any, Dict, Optional

import psutil

from core.rune.rune_bus import resolve_root_from_env


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


def _normalize_io_counter_key(value: str) -> str:
    return str(value or "").strip().replace("\\", "").replace("/", "").replace(":", "").lower()


def _resolve_partition_io(
    device: str,
    mountpoint: str,
    io_map: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not io_map:
        return None

    lookup: Dict[str, Any] = {}
    for key, counter in io_map.items():
        lookup[_normalize_io_counter_key(str(key))] = counter

    candidates = [device, mountpoint]
    if mountpoint:
        candidates.append(str(Path(mountpoint).anchor))
    if mountpoint and len(mountpoint) >= 1:
        candidates.append(mountpoint[0] + ":")

    for candidate in candidates:
        norm = _normalize_io_counter_key(candidate)
        if norm and norm in lookup:
            counter = lookup[norm]
            read_bytes = getattr(counter, "read_bytes", None)
            write_bytes = getattr(counter, "write_bytes", None)
            if read_bytes is None or write_bytes is None:
                return None
            try:
                return {
                    "read_bytes": int(read_bytes),
                    "write_bytes": int(write_bytes),
                }
            except (TypeError, ValueError):
                return None
    return None


def snapshot_disks() -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    partitions = []
    try:
        partitions = psutil.disk_partitions(all=False)
    except Exception:
        partitions = []

    try:
        io_map = psutil.disk_io_counters(perdisk=True) or {}
    except Exception:
        io_map = {}

    seen: set[str] = set()
    for part in partitions:
        mountpoint = str(getattr(part, "mountpoint", "") or "").strip()
        device = str(getattr(part, "device", "") or "").strip()
        fstype = str(getattr(part, "fstype", "") or "").strip()
        if not mountpoint:
            continue
        norm_mount = mountpoint.lower()
        if norm_mount in seen:
            continue

        try:
            usage = psutil.disk_usage(mountpoint)
        except Exception:
            continue

        seen.add(norm_mount)
        io_values = _resolve_partition_io(device=device, mountpoint=mountpoint, io_map=io_map)

        row = {
            "key": norm_mount,
            "mount": mountpoint,
            "device": device,
            "fstype": fstype,
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "percent": round(float(usage.percent), 1),
            "read_bytes": int(io_values.get("read_bytes", 0)) if isinstance(io_values, dict) else None,
            "write_bytes": int(io_values.get("write_bytes", 0)) if isinstance(io_values, dict) else None,
        }
        rows.append(row)

    rows.sort(key=lambda item: str(item.get("mount", "")).lower())
    return rows


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


def snapshot_thermal() -> Optional[Dict[str, Any]]:
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None
    if not temps:
        return None

    readings: list[Dict[str, Any]] = []
    for source, entries in temps.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            current = getattr(entry, "current", None)
            if current is None:
                continue
            try:
                current_value = float(current)
            except (TypeError, ValueError):
                continue
            readings.append(
                {
                    "source": str(source),
                    "label": str(getattr(entry, "label", "") or "").strip(),
                    "current_c": round(current_value, 1),
                    "high_c": round(float(getattr(entry, "high", 0.0) or 0.0), 1),
                    "critical_c": round(float(getattr(entry, "critical", 0.0) or 0.0), 1),
                }
            )

    if not readings:
        return None

    max_temp = max(float(item.get("current_c", 0.0)) for item in readings)
    cpu_candidates = [
        float(item.get("current_c", 0.0))
        for item in readings
        if "cpu" in str(item.get("source", "")).lower()
        or "package" in str(item.get("label", "")).lower()
    ]

    return {
        "readings": readings,
        "max_temp_c": round(max_temp, 1),
        "cpu_temp_c": round(cpu_candidates[0], 1) if cpu_candidates else None,
    }


def snapshot_fans() -> Optional[Dict[str, Any]]:
    try:
        fans = psutil.sensors_fans()
    except Exception:
        return None
    if not fans:
        return None

    readings: list[Dict[str, Any]] = []
    for source, entries in fans.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            current = getattr(entry, "current", None)
            if current is None:
                continue
            try:
                rpm = float(current)
            except (TypeError, ValueError):
                continue
            readings.append(
                {
                    "source": str(source),
                    "label": str(getattr(entry, "label", "") or "").strip(),
                    "rpm": round(rpm, 1),
                }
            )

    if not readings:
        return None

    rpms = [float(item.get("rpm", 0.0)) for item in readings]
    avg_rpm = (sum(rpms) / len(rpms)) if rpms else 0.0
    max_rpm = max(rpms) if rpms else 0.0
    return {
        "readings": readings,
        "avg_rpm": round(avg_rpm, 1),
        "max_rpm": round(max_rpm, 1),
    }


def snapshot_gpu_vram() -> Optional[Dict[str, Any]]:
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu,fan.speed",
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
        temp_c = None
        fan_percent = None
        if len(parts) >= 6:
            try:
                temp_c = round(float(parts[5]), 1)
            except (TypeError, ValueError):
                temp_c = None
        if len(parts) >= 7:
            try:
                fan_percent = round(float(parts[6]), 1)
            except (TypeError, ValueError):
                fan_percent = None
        percent = round((used_mb / total_mb) * 100, 1) if total_mb else 0.0
        gpus.append(
            {
                "name": name,
                "total_gb": round(total_mb / 1024.0, 2),
                "used_gb": round(used_mb / 1024.0, 2),
                "free_gb": round(free_mb / 1024.0, 2),
                "percent": percent,
                "utilization_percent": round(util_percent, 1),
                "temperature_c": temp_c,
                "fan_percent": fan_percent,
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
        "disks": snapshot_disks(),
        "docker": snapshot_docker(),
        "wsl_vhd": snapshot_wsl_vhd(),
        "system": snapshot_system_resources(),
        "thermal": snapshot_thermal(),
        "fans": snapshot_fans(),
        "gpu_vram": snapshot_gpu_vram(),
        "agent_load": snapshot_agent_load(),
    }
    payload["warnings"] = build_pressure_warnings(payload)
    return payload
