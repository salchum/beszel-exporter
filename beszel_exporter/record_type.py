from __future__ import annotations

from datetime import datetime, timedelta

RECORD_TYPE_RULES = [
    (timedelta(hours=1), "1m"),
    (timedelta(hours=12), "10m"),
    (timedelta(hours=24), "20m"),
    (timedelta(days=7), "120m"),
    (timedelta(days=30), "480m"),
]


def select_record_type(start: datetime, end: datetime) -> str:
    duration = end - start
    for max_duration, record_type in RECORD_TYPE_RULES:
        if duration <= max_duration:
            return record_type
    return "480m"
