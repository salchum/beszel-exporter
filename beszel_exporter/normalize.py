from __future__ import annotations

from typing import Any


FIELD_NAMES = [
    "timestamp",
    "system_id",
    "record_type",
    "cpu_usage",
    "memory_usage",
    "memory_used",
    "disk_usage",
    "disk_used",
    "bandwidth_upload",
    "bandwidth_download",
    "cumulative_upload",
    "cumulative_download",
]


def normalize_record(record: dict[str, Any], fallback_system_id: str | None = None) -> dict[str, Any]:
    stats = record.get("stats") or {}
    if not isinstance(stats, dict):
        stats = {}

    bandwidth = stats.get("b")
    cumulative_upload = None
    cumulative_download = None
    if isinstance(bandwidth, list | tuple) and len(bandwidth) >= 2:
        cumulative_upload = as_number(bandwidth[0])
        cumulative_download = as_number(bandwidth[1])

    memory_usage = first_number(stats, "m", "mp")

    return {
        "timestamp": record.get("created"),
        "system_id": record.get("system") or fallback_system_id,
        "record_type": record.get("type"),
        "cpu_usage": as_number(stats.get("cpu")),
        "memory_usage": memory_usage,
        "memory_used": as_number(stats.get("mu")),
        "disk_usage": as_number(stats.get("dp")),
        "disk_used": as_number(stats.get("du")),
        "bandwidth_upload": as_number(stats.get("ns")),
        "bandwidth_download": as_number(stats.get("nr")),
        "cumulative_upload": cumulative_upload,
        "cumulative_download": cumulative_download,
    }


def first_number(values: dict[str, Any], *keys: str) -> int | float | None:
    for key in keys:
        value = as_number(values.get(key))
        if value is not None:
            return value
    return None


def as_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return value
    return None
