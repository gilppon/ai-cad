from __future__ import annotations

import unittest
from unittest.mock import patch

from parser.room_export import rooms_to_json_dict
from pipeline.contracts import (
    ContractValidationError,
    build_export_metadata,
    build_geometry_payload,
    validate_export_metadata,
    validate_geometry_payload,
)


class _FakeRoom:
    def __init__(self, room_id, contour, bbox, area_px, kind="ROOM"):
        self.id = room_id
        self.contour = contour
        self.bbox = bbox
        self.area_px = area_px
        self.kind = kind


class _FakeRoomResult:
    def __init__(self):
        self.width = 120
        self.height = 80
        self.rooms = [
            _FakeRoom(
                room_id=7,
                contour=[(0, 0), (10, 0), (10, 8), (0, 8)],
                bbox=(0, 0, 10, 8),
                area_px=80.0,
                kind="ROOM",
            )
        ]
        self.debug = {"overlay": "out/overlay_page0.png"}


class ContractTests(unittest.TestCase):
    def test_build_geometry_payload_is_valid(self):
        payload = build_geometry_payload(
            page=0,
            canvas={"width": 100, "height": 200},
            rooms=[],
            debug_files={"overlay": "out/overlay_page0.png"},
        )

        validate_geometry_payload(payload)

        self.assertEqual(payload["kind"], "geometry_payload")
        self.assertEqual(payload["schema_version"], "0.1.0")
        self.assertEqual(payload["page"], payload["page_index"])
        self.assertEqual(payload["rooms_count"], 0)

    def test_rooms_to_json_dict_uses_geometry_contract(self):
        payload = rooms_to_json_dict(
            _FakeRoomResult(),
            page=0,
            pixel_to_mm=5.0,
            source={"file_path": "samples/sample.pdf", "source_type": "image_pdf"},
        )

        validate_geometry_payload(payload)

        self.assertEqual(payload["canvas"]["width"], 120)
        self.assertEqual(payload["rooms_count"], 1)
        self.assertEqual(payload["rooms"][0]["id"], 7)
        self.assertEqual(payload["scale"]["pixel_to_mm"], 5.0)
        self.assertEqual(payload["source"]["source_type"], "image_pdf")

    def test_save_rooms_json_passes_refinement_context(self):
        fake_context = {
            "page_index": 3,
            "output_dir": "out",
            "inputs": {"lines_path": "out/snapped_page3.json"},
        }
        fake_refined = {
            "kind": "geometry_payload",
            "schema_version": "0.1.0",
            "page": 3,
            "page_index": 3,
            "canvas": {"width": 120, "height": 80},
            "rooms": [],
            "rooms_count": 0,
            "debug_files": {},
            "processing": {"stage": "room_export", "warnings": []},
            "incident": {},
            "refined": True,
        }

        with patch("parser.rooms_pipeline.detect_and_refine_rooms", return_value=fake_refined) as refine_mock:
            with patch("builtins.open"):
                from parser.room_export import save_rooms_json

                save_rooms_json(
                    _FakeRoomResult(),
                    "out/page3_rooms.json",
                    page=3,
                    refinement_context=fake_context,
                )

        _, kwargs = refine_mock.call_args
        self.assertEqual(kwargs["refinement_context"], fake_context)

    def test_build_export_metadata_is_valid(self):
        metadata = build_export_metadata(
            page_index=0,
            rooms=[{"id": 1, "polygon": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}]}],
            walls=[{"id": 1, "x1_px": 0, "y1_px": 0, "x2_px": 10, "y2_px": 0}],
            doors=[{"id": 1, "center_px": {"x": 4, "y": 0}, "angle_deg": 0.0}],
            edges=[],
            params={"px_to_mm": 5.0},
        )

        validate_export_metadata(metadata)

        self.assertEqual(metadata["kind"], "scene_export_metadata")
        self.assertEqual(metadata["params"]["px_to_mm"], 5.0)

    def test_validate_geometry_payload_rejects_wrong_kind(self):
        with self.assertRaises(ContractValidationError):
            validate_geometry_payload({"kind": "wrong"})


if __name__ == "__main__":
    unittest.main()
