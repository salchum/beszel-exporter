from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from beszel_exporter.aggregate import aggregate_rows, parse_interval


class AggregateTests(unittest.TestCase):
    def test_parse_interval_accepts_supported_values(self) -> None:
        self.assertEqual(parse_interval("1m"), timedelta(minutes=1))
        self.assertEqual(parse_interval("5m"), timedelta(minutes=5))
        self.assertEqual(parse_interval("1h"), timedelta(hours=1))
        self.assertEqual(parse_interval("24h"), timedelta(hours=24))
        self.assertEqual(parse_interval("1d"), timedelta(days=1))

    def test_parse_interval_rejects_unsupported_values(self) -> None:
        with self.assertRaises(ValueError):
            parse_interval("30m")

    def test_max_aggregation_uses_start_aligned_one_minute_buckets(self) -> None:
        rows = [
            self.row("2026-01-01T04:00:10+00:00", cpu_usage=10, memory_usage=50, cumulative_upload=100),
            self.row("2026-01-01T04:00:50+00:00", cpu_usage=25, memory_usage=40, cumulative_upload=160),
            self.row("2026-01-01T04:01:10+00:00", cpu_usage=15, memory_usage=60, cumulative_upload=200),
        ]

        result = aggregate_rows(
            rows,
            self.local("2026-01-01 11:00"),
            self.local("2026-01-01 11:02"),
            parse_interval("1m"),
            "max",
            "1m",
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["timestamp"], "2026-01-01 11:00:00+07:00")
        self.assertEqual(result[0]["interval_start"], "2026-01-01 11:00:00+07:00")
        self.assertEqual(result[0]["interval_end"], "2026-01-01 11:01:00+07:00")
        self.assertEqual(result[0]["aggregation"], "max")
        self.assertEqual(result[0]["source_record_type"], "1m")
        self.assertEqual(result[0]["sample_count"], 2)
        self.assertEqual(result[0]["cpu_usage"], 25)
        self.assertEqual(result[0]["memory_usage"], 50)
        self.assertEqual(result[0]["cumulative_upload"], 60)

    def test_aggregation_includes_max_bandwidth_fields(self) -> None:
        rows = [
            self.row(
                "2026-01-01T04:00:10+00:00",
                bandwidth_upload_max=200,
                bandwidth_download_max=50,
            ),
            self.row(
                "2026-01-01T04:00:50+00:00",
                bandwidth_upload_max=300,
                bandwidth_download_max=100,
            ),
        ]

        result = aggregate_rows(
            rows,
            self.local("2026-01-01 11:00"),
            self.local("2026-01-01 11:01"),
            parse_interval("1m"),
            "max",
            "1m",
        )

        self.assertEqual(result[0]["bandwidth_upload_max"], 300)
        self.assertEqual(result[0]["bandwidth_download_max"], 100)

    def test_avg_aggregation_uses_start_aligned_24_hour_buckets(self) -> None:
        rows = [
            self.row("2026-01-01T04:00:00+00:00", cpu_usage=10, bandwidth_download=100, cumulative_download=500),
            self.row("2026-01-01T16:00:00+00:00", cpu_usage=30, bandwidth_download=300, cumulative_download=800),
            self.row("2026-01-02T04:00:00+00:00", cpu_usage=70, bandwidth_download=700, cumulative_download=1000),
        ]

        result = aggregate_rows(
            rows,
            self.local("2026-01-01 11:00"),
            self.local("2026-01-30 11:00"),
            parse_interval("24h"),
            "avg",
            "480m",
        )

        self.assertEqual(len(result), 29)
        self.assertEqual(result[0]["timestamp"], "2026-01-01 11:00:00+07:00")
        self.assertEqual(result[0]["interval_end"], "2026-01-02 11:00:00+07:00")
        self.assertEqual(result[0]["source_record_type"], "480m")
        self.assertEqual(result[0]["sample_count"], 2)
        self.assertEqual(result[0]["cpu_usage"], 20)
        self.assertEqual(result[0]["bandwidth_download"], 200)
        self.assertEqual(result[0]["cumulative_download"], 300)
        self.assertEqual(result[1]["timestamp"], "2026-01-02 11:00:00+07:00")
        self.assertEqual(result[1]["sample_count"], 1)
        self.assertEqual(result[1]["cumulative_download"], 0)
        self.assertEqual(result[2]["timestamp"], "2026-01-03 11:00:00+07:00")
        self.assertEqual(result[2]["sample_count"], 0)
        self.assertIsNone(result[2]["cpu_usage"])
        self.assertIsNone(result[2]["cumulative_download"])

    def test_empty_buckets_are_emitted(self) -> None:
        result = aggregate_rows(
            [self.row("2026-01-01T04:00:00+00:00", cpu_usage=10)],
            self.local("2026-01-01 11:00"),
            self.local("2026-01-01 11:03"),
            parse_interval("1m"),
            "avg",
            "1m",
        )

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["sample_count"], 1)
        self.assertEqual(result[1]["sample_count"], 0)
        self.assertIsNone(result[1]["cpu_usage"])
        self.assertEqual(result[1]["source_record_type"], "1m")

    def row(self, timestamp: str, **values: int | float) -> dict[str, object]:
        return {
            "timestamp": timestamp,
            "system_id": "sys1",
            "record_type": "1m",
            "cpu_usage": None,
            "memory_usage": None,
            "memory_used": None,
            "disk_usage": None,
            "disk_used": None,
            "bandwidth_upload": None,
            "bandwidth_download": None,
            "bandwidth_upload_max": None,
            "bandwidth_download_max": None,
            "cumulative_upload": None,
            "cumulative_download": None,
            **values,
        }

    def local(self, value: str) -> datetime:
        return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Asia/Jakarta"))


if __name__ == "__main__":
    unittest.main()
