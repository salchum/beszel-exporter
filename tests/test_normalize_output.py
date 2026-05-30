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
                },
            }
        )

        self.assertEqual(row["timestamp"], "2026-01-01 01:00:00.000Z")
        self.assertEqual(row["system_id"], "sys1")
        self.assertEqual(row["record_type"], "1m")
        self.assertEqual(row["cpu_usage"], 12.5)
        self.assertEqual(row["memory_usage"], 64.2)
        self.assertEqual(row["disk_usage"], 70.1)
        self.assertEqual(row["bandwidth_upload"], 2.4)
        self.assertEqual(row["bandwidth_download"], 5.1)
        self.assertEqual(row["cumulative_upload"], 123456)
        self.assertEqual(row["cumulative_download"], 654321)

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


if __name__ == "__main__":
    unittest.main()
