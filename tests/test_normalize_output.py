from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from beszel_exporter.normalize import FIELD_NAMES, normalize_record
from beszel_exporter.output import write_csv, write_json


class NormalizeAndOutputTests(unittest.TestCase):
    def test_normalize_system_stats_record(self) -> None:
        row = normalize_record(
            {
                "created": "2026-01-01 01:00:00.000Z",
                "system": "sys1",
                "type": "1m",
                "stats": {
                    "cpu": 12.5,
                    "m": 64.2,
                    "mp": 63.9,
                    "mu": 2048,
                    "dp": 70.1,
                    "du": 120.5,
                    "ns": 2.4,
                    "nr": 5.1,
                    "b": [123456, 654321],
                    "bm": [200000, 700000],
                },
            }
        )

        self.assertEqual(row["timestamp"], "2026-01-01 01:00:00.000Z")
        self.assertEqual(row["system_id"], "sys1")
        self.assertEqual(row["record_type"], "1m")
        self.assertEqual(row["cpu_usage"], 12.5)
        self.assertEqual(row["memory_usage"], 64.2)
        self.assertEqual(row["disk_usage"], 70.1)
        self.assertEqual(row["bandwidth_upload"], 123456)
        self.assertEqual(row["bandwidth_download"], 654321)
        self.assertEqual(row["bandwidth_upload_max"], 200000)
        self.assertEqual(row["bandwidth_download_max"], 700000)
        self.assertEqual(row["cumulative_upload"], 123456)
        self.assertEqual(row["cumulative_download"], 654321)

    def test_normalize_bandwidth_from_current_beszel_payload(self) -> None:
        row = normalize_record(
            {
                "created": "2026-05-30 09:00:00.000Z",
                "system": "sys1",
                "type": "1m",
                "stats": {
                    "b": [109, 71],
                    "bm": [268, 145],
                    "ni": {
                        "ens18": [109, 71, 117596082, 156853239],
                    },
                },
            }
        )

        self.assertEqual(row["bandwidth_upload"], 109)
        self.assertEqual(row["bandwidth_download"], 71)
        self.assertEqual(row["bandwidth_upload_max"], 268)
        self.assertEqual(row["bandwidth_download_max"], 145)
        self.assertEqual(row["cumulative_upload"], 117596082)
        self.assertEqual(row["cumulative_download"], 156853239)

    def test_cumulative_bandwidth_sums_multiple_interfaces(self) -> None:
        row = normalize_record(
            {
                "stats": {
                    "b": [10, 20],
                    "ni": {
                        "eth0": [10, 20, 1000, 2000],
                        "eth1": [30, 40, 3000, 4000],
                    },
                },
            },
            fallback_system_id="sys1",
        )

        self.assertEqual(row["cumulative_upload"], 4000)
        self.assertEqual(row["cumulative_download"], 6000)

    def test_legacy_bandwidth_keys_are_fallbacks(self) -> None:
        row = normalize_record(
            {
                "stats": {
                    "ns": 2.4,
                    "nr": 5.1,
                },
            }
        )

        self.assertEqual(row["bandwidth_upload"], 2.4)
        self.assertEqual(row["bandwidth_download"], 5.1)

    def test_memory_usage_falls_back_to_mp(self) -> None:
        row = normalize_record({"stats": {"mp": 51.5}}, fallback_system_id="sys1")

        self.assertEqual(row["memory_usage"], 51.5)
        self.assertEqual(row["system_id"], "sys1")

    def test_writers_have_stable_fields(self) -> None:
        row = {field: None for field in FIELD_NAMES}
        row["timestamp"] = "2026-01-01 01:00:00.000Z"
        row["cpu_usage"] = 12.5

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "out.csv"
            json_path = Path(temp_dir) / "out.json"

            write_csv(csv_path, [row])
            write_json(json_path, [row])

            with csv_path.open(newline="", encoding="utf-8") as file:
                csv_rows = list(csv.DictReader(file))
            with json_path.open(encoding="utf-8") as file:
                json_rows = json.load(file)

        self.assertEqual(csv_rows[0].keys(), set(FIELD_NAMES))
        self.assertEqual(csv_rows[0]["cpu_usage"], "12.5")
        self.assertEqual(json_rows[0]["cpu_usage"], 12.5)

    def test_csv_writer_accepts_aggregation_fields(self) -> None:
        row = {
            "timestamp": "2026-01-01 11:00:00+07:00",
            "aggregation": "max",
            "sample_count": 2,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "out.csv"
            write_csv(csv_path, [row], fieldnames=["timestamp", "aggregation", "sample_count"])

            with csv_path.open(newline="", encoding="utf-8") as file:
                csv_rows = list(csv.DictReader(file))

        self.assertEqual(list(csv_rows[0].keys()), ["timestamp", "aggregation", "sample_count"])
        self.assertEqual(csv_rows[0]["aggregation"], "max")


if __name__ == "__main__":
    unittest.main()
