from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

AGGREGATION_FIELD_NAMES = [
    "timestamp",
    "interval_start",
    "interval_end",
    "system_id",
    "record_type",
    "source_record_type",
    "aggregation",
    "sample_count",
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
AGGREGATABLE_FIELDS = [
    "cpu_usage",
    "memory_usage",
    "memory_used",
    "disk_usage",
    "disk_used",
    "bandwidth_upload",
    "bandwidth_download",
    "bandwidth_upload_max",
    "bandwidth_download_max",
]
COUNTER_FIELDS = ["cumulative_upload", "cumulative_download"]
INTERVALS = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "1d": timedelta(days=1),
}


def parse_interval(value: str) -> timedelta:
    try:
        return INTERVALS[value]
    except KeyError as exc:
        supported = ", ".join(INTERVALS)
        raise ValueError(f"unsupported interval {value!r}; supported values: {supported}") from exc


def aggregate_rows(
    rows: list[dict[str, Any]],
    start: datetime,
    end: datetime,
    interval: timedelta,
    aggregation: str,
    source_record_type: str | None = None,
) -> list[dict[str, Any]]:
    if aggregation not in {"avg", "max"}:
        raise ValueError("aggregation must be 'avg' or 'max'")
    if interval.total_seconds() <= 0:
        raise ValueError("interval must be greater than zero")
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must include timezone information")

    buckets: dict[int, list[tuple[datetime, dict[str, Any]]]] = defaultdict(list)
    for row in rows:
        timestamp = parse_row_timestamp(row.get("timestamp"), start)
        if timestamp is None or timestamp < start or timestamp > end:
            continue
        bucket_index = int((timestamp - start).total_seconds() // interval.total_seconds())
        buckets[bucket_index].append((timestamp, row))

    aggregated: list[dict[str, Any]] = []
    for bucket_index in range(bucket_count(start, end, interval)):
        bucket_start = start + (interval * bucket_index)
        bucket_end = min(bucket_start + interval, end)
        samples = sorted(buckets[bucket_index], key=lambda item: item[0])
        sample_rows = [sample[1] for sample in samples]
        output = {field: None for field in AGGREGATION_FIELD_NAMES}
        output.update(
            {
                "timestamp": format_timestamp(bucket_start),
                "interval_start": format_timestamp(bucket_start),
                "interval_end": format_timestamp(bucket_end),
                "system_id": first_present(sample_rows, "system_id"),
                "record_type": first_present(sample_rows, "record_type"),
                "source_record_type": source_record_type,
                "aggregation": aggregation,
                "sample_count": len(sample_rows),
            }
        )
        for field in AGGREGATABLE_FIELDS:
            values = numeric_values(sample_rows, field)
            output[field] = aggregate_values(values, aggregation)
        for field in COUNTER_FIELDS:
            output[field] = counter_delta(sample_rows, field)
        aggregated.append(output)

    return aggregated


def bucket_count(start: datetime, end: datetime, interval: timedelta) -> int:
    duration_seconds = (end - start).total_seconds()
    interval_seconds = interval.total_seconds()
    whole_buckets = int(duration_seconds // interval_seconds)
    if duration_seconds % interval_seconds:
        whole_buckets += 1
    return max(whole_buckets, 1)


def parse_row_timestamp(value: Any, reference: datetime) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=reference.tzinfo)
    return parsed.astimezone(reference.tzinfo)


def format_timestamp(value: datetime) -> str:
    return value.isoformat(sep=" ")


def numeric_values(rows: list[dict[str, Any]], field: str) -> list[int | float]:
    return [value for row in rows if isinstance(value := row.get(field), int | float) and not isinstance(value, bool)]


def aggregate_values(values: list[int | float], aggregation: str) -> int | float | None:
    if not values:
        return None
    if aggregation == "max":
        return max(values)
    return sum(values) / len(values)


def counter_delta(rows: list[dict[str, Any]], field: str) -> int | float | None:
    values = numeric_values(rows, field)
    if len(values) < 2:
        return 0 if len(values) == 1 else None
    delta = values[-1] - values[0]
    return delta if delta >= 0 else values[-1]


def first_present(rows: list[dict[str, Any]], field: str) -> Any:
    for row in rows:
        value = row.get(field)
        if value is not None:
            return value
    return None
