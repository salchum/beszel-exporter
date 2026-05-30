from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from beszel_exporter.record_type import select_record_type


class RecordTypeTests(unittest.TestCase):
    def test_select_record_type_boundaries(self) -> None:
        start = datetime(2026, 5, 30, 16, 0, tzinfo=ZoneInfo("Asia/Jakarta"))

        self.assertEqual(select_record_type(start, start + timedelta(hours=1)), "1m")
        self.assertEqual(select_record_type(start, start + timedelta(hours=12)), "10m")
        self.assertEqual(select_record_type(start, start + timedelta(hours=24)), "20m")
        self.assertEqual(select_record_type(start, start + timedelta(days=7)), "120m")
        self.assertEqual(select_record_type(start, start + timedelta(days=30)), "480m")

    def test_select_record_type_moves_to_next_rule_after_boundary(self) -> None:
        start = datetime(2026, 5, 30, 16, 0, tzinfo=ZoneInfo("Asia/Jakarta"))

        self.assertEqual(select_record_type(start, start + timedelta(hours=1, seconds=1)), "10m")
        self.assertEqual(select_record_type(start, start + timedelta(hours=12, seconds=1)), "20m")
        self.assertEqual(select_record_type(start, start + timedelta(hours=24, seconds=1)), "120m")
        self.assertEqual(select_record_type(start, start + timedelta(days=7, seconds=1)), "480m")
        self.assertEqual(select_record_type(start, start + timedelta(days=31)), "480m")


if __name__ == "__main__":
    unittest.main()
