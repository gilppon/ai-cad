from __future__ import annotations

import unittest

from parser.export_ifc import _mm_to_m, _px_to_m
from parser.export_step import _derive_doors_from_wall_gaps


class ExportHelperTests(unittest.TestCase):
    def test_mm_to_m_and_px_to_m_are_stable(self):
        self.assertEqual(_mm_to_m(2400), 2.4)
        self.assertEqual(_px_to_m(100, 5.0), 0.5)

    def test_derive_doors_from_wall_gaps_detects_horizontal_and_vertical_gaps(self):
        walls_px = [
            (0, 10, 40, 10),
            (60, 10, 100, 10),
            (20, 0, 20, 40),
            (20, 60, 20, 100),
        ]

        doors = _derive_doors_from_wall_gaps(walls_px)

        self.assertEqual(len(doors), 2)

        horizontal = next(door for door in doors if door["axis"] == "H")
        vertical = next(door for door in doors if door["axis"] == "V")

        self.assertEqual(horizontal["angle_deg"], 0.0)
        self.assertAlmostEqual(horizontal["cx_px"], 50.0)
        self.assertAlmostEqual(horizontal["cy_px"], 10.0)

        self.assertEqual(vertical["angle_deg"], 90.0)
        self.assertAlmostEqual(vertical["cx_px"], 20.0)
        self.assertAlmostEqual(vertical["cy_px"], 50.0)

    def test_derive_doors_from_wall_gaps_filters_small_and_large_gaps(self):
        walls_px = [
            (0, 10, 10, 10),
            (15, 10, 30, 10),
            (130, 10, 160, 10),
            (250, 10, 300, 10),
        ]

        doors = _derive_doors_from_wall_gaps(walls_px, min_gap_px=8.0, max_gap_px=80.0)

        self.assertEqual(len(doors), 0)


if __name__ == "__main__":
    unittest.main()
