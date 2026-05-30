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
    "bandwidth_upload_max",
    "bandwidth_download_max",
    "cumulative_upload",
    "cumulative_download",
]


def normalize_record(record: dict[str, Any], fallback_system_id: str | None = None) -> dict[str, Any]:
    stats = record.get("stats") or {}
    if not isinstance(stats, dict):
        stats = {}

    memory_usage = first_number(stats, "m", "mp")
    bandwidth_upload, bandwidth_download = bandwidth_pair(stats, "b")
    bandwidth_upload_max, bandwidth_download_max = bandwidth_pair(stats, "bm")
    cumulative_upload, cumulative_download = cumulative_totals(stats)

    return {
        "timestamp": record.get("created"),
        "system_id": record.get("system") or fallback_system_id,
        "record_type": record.get("type"),
        "cpu_usage": as_number(stats.get("cpu")),
        "memory_usage": memory_usage,
        "memory_used": as_number(stats.get("mu")),
        "disk_usage": as_number(stats.get("dp")),
        "disk_used": as_number(stats.get("du")),
        "bandwidth_upload": first_value(bandwidth_upload, as_number(stats.get("ns"))),
        "bandwidth_download": first_value(bandwidth_download, as_number(stats.get("nr"))),
        "bandwidth_upload_max": bandwidth_upload_max,
        "bandwidth_download_max": bandwidth_download_max,
        "cumulative_upload": cumulative_upload,
        "cumulative_download": cumulative_download,
    }


def first_number(values: dict[str, Any], *keys: str) -> int | float | None:
    for key in keys:
        value = as_number(values.get(key))
        if value is not None:
            return value
    return None


def bandwidth_pair(values: dict[str, Any], key: str) -> tuple[int | float | None, int | float | None]:
    pair = values.get(key)
    if isinstance(pair, list | tuple) and len(pair) >= 2:
        return as_number(pair[0]), as_number(pair[1])
    return None, None


def cumulative_totals(values: dict[str, Any]) -> tuple[int | float | None, int | float | None]:
    interfaces = values.get("ni")
    upload_total: int | float = 0
    download_total: int | float = 0
    found = False
    if isinstance(interfaces, dict):
        for interface_values in interfaces.values():
            if not isinstance(interface_values, list | tuple) or len(interface_values) < 4:
                continue
            upload = as_number(interface_values[2])
            download = as_number(interface_values[3])
            if upload is None or download is None:
                continue
            upload_total += upload
            download_total += download
            found = True
    if found:
        return upload_total, download_total
    return bandwidth_pair(values, "b")


def first_value(*values: int | float | None) -> int | float | None:
    for value in values:
        if value is not None:
            return value
    return None


def as_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return value
    return None
