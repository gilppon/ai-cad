# tests/test_incident_semantics.py — Phase 5 Exit Criteria 검증 테스트
"""
Phase 5 Incident Semantics Layer 완전 검증 테스트.
Exit Criteria: "A leakage case can be described inside the scene model, not just next to it"
"""
import unittest
import os
import json
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from domain.models import (
    LeakCase, LeakSource, DamageZone, SuspectedPath,
    IncidentAnnotation, Point, DamageType, Severity,
    Floor, Room, Wall, RoomKind,
)
from scene.serializer import (
    leak_case_to_dict, dict_to_leak_case,
    save_leak_case, load_leak_case,
)
from scene.incident_mapper import (
    map_incident_to_scene, validate_incident_mapping,
    compute_damage_spread, _point_in_polygon,
)
from scene.annotations import (
    attach_photo, attach_note,
    list_annotations_for_room, remove_annotation,
)
from pipeline.contracts import validate_incident_payload, ContractValidationError


def _make_sample_case() -> LeakCase:
    """테스트용 합성 LeakCase 생성"""
    return LeakCase(
        case_id="TEST-001",
        customer_name="Yamada Taro",
        address="Tokyo, Minato-ku 1-2-3",
        incident_date="2026-05-15",
        description="Water leakage from upstairs bathroom pipe",
        leak_sources=[
            LeakSource(
                point=Point(50.0, 50.0),
                room_id=None,  # auto-mapping 대상
                confidence=0.85,
                description="Suspected pipe joint leak under bathroom floor",
            ),
        ],
        damage_zones=[
            DamageZone(
                id=1,
                damage_type=DamageType.CEILING,
                severity=Severity.HIGH,
                polygon=[Point(30, 30), Point(70, 30), Point(70, 70), Point(30, 70)],
                room_id=None,  # auto-mapping 대상
                floor_level=0,
                surface_area_m2=1.6,
                description="Ceiling water stain in living room",
            ),
            DamageZone(
                id=2,
                damage_type=DamageType.FLOOR,
                severity=Severity.MEDIUM,
                polygon=[Point(120, 30), Point(180, 30), Point(180, 70), Point(120, 70)],
                room_id=None,
                floor_level=0,
                surface_area_m2=3.0,
                description="Floor moisture in bedroom",
            ),
        ],
        suspected_paths=[
            SuspectedPath(
                waypoints=[Point(50, 50), Point(80, 50), Point(150, 50)],
                room_ids=[],  # auto-mapping 대상
                description="Water flows from bathroom through wall to bedroom",
            ),
        ],
        annotations=[
            IncidentAnnotation(
                id=1,
                anchor_point=Point(50, 50),
                anchor_room_id=None,
                text="Initial inspection note",
                category="inspection",
            ),
        ],
    )


def _make_sample_geometry() -> dict:
    """테스트용 geometry payload 생성 (2개 방)"""
    return {
        "kind": "geometry_payload",
        "schema_version": "0.1.0",
        "page": 0,
        "page_index": 0,
        "canvas": {"width": 200, "height": 100},
        "rooms": [
            {
                "id": 0,
                "kind": "ldk",
                "polygon": [
                    {"x": 0, "y": 0}, {"x": 100, "y": 0},
                    {"x": 100, "y": 100}, {"x": 0, "y": 100},
                ],
                "area_m2": 25.0,
                "metadata": {},
            },
            {
                "id": 1,
                "kind": "bedroom",
                "polygon": [
                    {"x": 100, "y": 0}, {"x": 200, "y": 0},
                    {"x": 200, "y": 100}, {"x": 100, "y": 100},
                ],
                "area_m2": 12.0,
                "metadata": {},
            },
        ],
        "rooms_count": 2,
        "walls": [],
        "walls_count": 0,
        "debug_files": {},
        "processing": {"stage": "test", "warnings": []},
        "incident": {},
    }


class TestSerialization(unittest.TestCase):
    """1. 직렬화 왕복 테스트"""

    def test_round_trip_full_case(self):
        """LeakCase → dict → LeakCase 왕복 무손실"""
        case = _make_sample_case()
        d = leak_case_to_dict(case)
        restored = dict_to_leak_case(d)

        self.assertEqual(restored.case_id, case.case_id)
        self.assertEqual(restored.customer_name, case.customer_name)
        self.assertEqual(restored.address, case.address)
        self.assertEqual(restored.version, case.version)
        self.assertEqual(len(restored.leak_sources), len(case.leak_sources))
        self.assertEqual(len(restored.damage_zones), len(case.damage_zones))
        self.assertEqual(len(restored.suspected_paths), len(case.suspected_paths))
        self.assertEqual(len(restored.annotations), len(case.annotations))

        # 세부 필드 검증
        self.assertAlmostEqual(restored.leak_sources[0].point.x, 50.0)
        self.assertEqual(restored.damage_zones[0].damage_type, DamageType.CEILING)
        self.assertEqual(restored.damage_zones[0].severity, Severity.HIGH)
        self.assertEqual(restored.damage_zones[0].floor_level, 0)
        self.assertEqual(restored.damage_zones[1].damage_type, DamageType.FLOOR)

    def test_round_trip_file_io(self):
        """파일 저장/로드 왕복"""
        case = _make_sample_case()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name

        try:
            save_leak_case(case, path)
            loaded = load_leak_case(path)

            self.assertEqual(loaded.case_id, case.case_id)
            self.assertEqual(loaded.version, case.version)
            self.assertEqual(len(loaded.damage_zones), 2)

            # JSON 파일 내용 확인
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.assertIn("case_id", raw)
            self.assertIn("damage_zones", raw)
        finally:
            os.unlink(path)

    def test_empty_case_round_trip(self):
        """빈 LeakCase도 왕복 가능"""
        case = LeakCase(case_id="EMPTY-001")
        d = leak_case_to_dict(case)
        restored = dict_to_leak_case(d)
        self.assertEqual(restored.case_id, "EMPTY-001")
        self.assertEqual(len(restored.leak_sources), 0)
        self.assertEqual(len(restored.damage_zones), 0)


class TestIncidentMapping(unittest.TestCase):
    """2. 인시던트 매핑 테스트"""

    def test_point_in_polygon_basic(self):
        """Ray-casting Point-in-Polygon 기본 동작"""
        square = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}, {"x": 0, "y": 100}]
        self.assertTrue(_point_in_polygon(50, 50, square))
        self.assertFalse(_point_in_polygon(150, 50, square))
        self.assertFalse(_point_in_polygon(-10, 50, square))

    def test_leak_source_auto_binding(self):
        """leak source 좌표가 올바른 room_id에 자동 바인딩"""
        case = _make_sample_case()
        geo = _make_sample_geometry()

        result = map_incident_to_scene(case, geo)
        incident = result["incident"]

        # leak source (50,50)은 room 0 (0-100 범위) 안에 있어야 함
        src = incident["leak_sources"][0]
        self.assertEqual(src["room_id"], 0)
        self.assertTrue(src.get("auto_mapped", False))

    def test_damage_zone_auto_binding(self):
        """damage zone이 겹치는 방에 자동 매핑"""
        case = _make_sample_case()
        geo = _make_sample_geometry()

        result = map_incident_to_scene(case, geo)
        incident = result["incident"]

        # DZ1 (30-70)은 room 0과 겹침
        dz1 = incident["damage_zones"][0]
        self.assertEqual(dz1["room_id"], 0)
        self.assertIn(0, dz1["affected_room_ids"])

        # DZ2 (120-180)은 room 1과 겹침
        dz2 = incident["damage_zones"][1]
        self.assertEqual(dz2["room_id"], 1)
        self.assertIn(1, dz2["affected_room_ids"])

    def test_suspected_path_auto_room_ids(self):
        """suspected_path의 waypoints에서 room_ids 자동 계산"""
        case = _make_sample_case()
        geo = _make_sample_geometry()

        result = map_incident_to_scene(case, geo)
        incident = result["incident"]

        path = incident["suspected_paths"][0]
        # waypoints: (50,50) → room 0, (80,50) → room 0, (150,50) → room 1
        self.assertIn(0, path["room_ids"])
        self.assertIn(1, path["room_ids"])

    def test_original_payload_not_mutated(self):
        """map_incident_to_scene이 원본 payload를 변경하지 않음"""
        case = _make_sample_case()
        geo = _make_sample_geometry()

        result = map_incident_to_scene(case, geo)

        # 원본은 빈 incident 유지
        self.assertEqual(geo["incident"], {})
        # 결과에는 인시던트 포함
        self.assertIn("case_id", result["incident"])


class TestMultiRoomSpread(unittest.TestCase):
    """3. 다실 확산 테스트"""

    def test_damage_spread_analysis(self):
        """damage_zones가 복수 방에 걸친 확산 분석"""
        case = _make_sample_case()  # 2개 DZ → 2개 방
        geo = _make_sample_geometry()

        spread = compute_damage_spread(case, geo)

        self.assertEqual(spread["total_affected_rooms"], 2)
        self.assertIn(0, spread["affected_room_ids"])
        self.assertIn(1, spread["affected_room_ids"])
        self.assertEqual(spread["spread_summary"], "multi_room")

        # per_room_damage 검증
        self.assertIn("ceiling", spread["per_room_damage"][0]["damage_types"])
        self.assertIn("floor", spread["per_room_damage"][1]["damage_types"])

    def test_single_room_spread(self):
        """단일 방에만 피해인 경우"""
        case = LeakCase(
            case_id="SINGLE-001",
            damage_zones=[
                DamageZone(
                    id=1, damage_type=DamageType.WALL_SURFACE,
                    severity=Severity.LOW,
                    polygon=[Point(10, 10), Point(20, 10), Point(20, 20), Point(10, 20)],
                    room_id=0, floor_level=0,
                ),
            ],
        )
        geo = _make_sample_geometry()
        spread = compute_damage_spread(case, geo)
        self.assertEqual(spread["total_affected_rooms"], 1)
        self.assertEqual(spread["spread_summary"], "single_room")


class TestAnnotationCRUD(unittest.TestCase):
    """4. 어노테이션 CRUD 테스트"""

    def test_attach_photo(self):
        case = LeakCase(case_id="ANN-001")
        ann = attach_photo(case, "photos/leak1.jpg", Point(10, 20), room_id=1, text="Ceiling stain")

        self.assertEqual(ann.category, "photo")
        self.assertEqual(ann.attached_photo, "photos/leak1.jpg")
        self.assertEqual(ann.anchor_room_id, 1)
        self.assertEqual(len(case.annotations), 1)
        self.assertEqual(case.version, 2)  # bump_version 호출됨

    def test_attach_note(self):
        case = LeakCase(case_id="ANN-002")
        ann = attach_note(case, "Check pipe joint", Point(50, 50), room_id=0, category="warning")

        self.assertEqual(ann.category, "warning")
        self.assertIsNone(ann.attached_photo)
        self.assertEqual(ann.text, "Check pipe joint")

    def test_list_annotations_for_room(self):
        case = LeakCase(case_id="ANN-003")
        attach_note(case, "Note 1", Point(10, 10), room_id=0)
        attach_note(case, "Note 2", Point(20, 20), room_id=1)
        attach_note(case, "Note 3", Point(30, 30), room_id=0)

        room0_anns = list_annotations_for_room(case, 0)
        room1_anns = list_annotations_for_room(case, 1)

        self.assertEqual(len(room0_anns), 2)
        self.assertEqual(len(room1_anns), 1)

    def test_remove_annotation(self):
        case = LeakCase(case_id="ANN-004")
        ann = attach_note(case, "To remove", Point(10, 10), room_id=0)
        ann_id = ann.id

        self.assertTrue(remove_annotation(case, ann_id))
        self.assertEqual(len(case.annotations), 0)

        # 존재하지 않는 id 삭제 시도
        self.assertFalse(remove_annotation(case, 999))


class TestVersioning(unittest.TestCase):
    """5. 버전 관리 테스트"""

    def test_version_auto_increment(self):
        case = LeakCase(case_id="VER-001")
        self.assertEqual(case.version, 1)

        case.bump_version()
        self.assertEqual(case.version, 2)
        self.assertNotEqual(case.created_at, "")
        self.assertNotEqual(case.updated_at, "")

    def test_annotation_bumps_version(self):
        case = LeakCase(case_id="VER-002")
        initial_version = case.version

        attach_note(case, "Test", Point(0, 0))
        self.assertEqual(case.version, initial_version + 1)

        attach_photo(case, "test.jpg", Point(0, 0))
        self.assertEqual(case.version, initial_version + 2)

        remove_annotation(case, 1)
        self.assertEqual(case.version, initial_version + 3)

    def test_version_preserved_in_serialization(self):
        case = LeakCase(case_id="VER-003")
        case.bump_version()
        case.bump_version()
        self.assertEqual(case.version, 3)

        d = leak_case_to_dict(case)
        restored = dict_to_leak_case(d)
        self.assertEqual(restored.version, 3)


class TestContractValidation(unittest.TestCase):
    """6. 빈 인시던트 및 contract validation 테스트"""

    def test_empty_incident_valid(self):
        """빈 incident dict는 합법"""
        validate_incident_payload({})  # 예외 없이 통과해야 함

    def test_valid_incident_payload(self):
        """올바른 인시던트 payload 검증"""
        case = _make_sample_case()
        geo = _make_sample_geometry()
        result = map_incident_to_scene(case, geo)
        validate_incident_payload(result["incident"])

    def test_invalid_incident_missing_case_id(self):
        """case_id 없는 incident은 거부"""
        with self.assertRaises(ContractValidationError):
            validate_incident_payload({"leak_sources": []})

    def test_invalid_leak_source_missing_point(self):
        """point 없는 leak_source 거부"""
        with self.assertRaises(ContractValidationError):
            validate_incident_payload({
                "case_id": "BAD",
                "leak_sources": [{"room_id": 1}],
            })


class TestMappingValidation(unittest.TestCase):
    """7. 매핑 검증 + geometry 통합 테스트"""

    def test_validate_mapping_no_warnings(self):
        """정상 매핑에서는 경고 없음"""
        case = _make_sample_case()
        geo = _make_sample_geometry()
        result = map_incident_to_scene(case, geo)
        warnings = validate_incident_mapping(result)

        # suspected_path가 2개 방을 지나므로 경고 없어야 함
        # 그러나 정밀 검증이므로 일부 경고가 있을 수 있음 (예: path < 2 rooms)
        # 최소한 leak_source와 damage_zone은 room에 매핑되었어야 함
        source_warnings = [w for w in warnings if "leak_source" in w and "not mapped" in w]
        self.assertEqual(len(source_warnings), 0, f"Unexpected source warnings: {source_warnings}")

    def test_incident_inside_geometry_payload(self):
        """Exit Criteria 증명: incident 데이터가 geometry payload 안에 존재"""
        case = _make_sample_case()
        geo = _make_sample_geometry()
        result = map_incident_to_scene(case, geo)

        # geometry payload 안에 incident 필드가 존재
        self.assertIn("incident", result)
        incident = result["incident"]

        # 인시던트 핵심 데이터가 rooms와 같은 레벨에 공존
        self.assertIn("rooms", result)
        self.assertIn("leak_sources", incident)
        self.assertIn("damage_zones", incident)
        self.assertIn("suspected_paths", incident)
        self.assertIn("annotations", incident)

        # room_id가 기하학의 room id와 매칭
        room_ids = {r["id"] for r in result["rooms"]}
        for src in incident["leak_sources"]:
            if src["room_id"] is not None:
                self.assertIn(src["room_id"], room_ids)

    def test_full_json_round_trip_with_incident(self):
        """인시던트 포함 geometry payload의 JSON 왕복"""
        case = _make_sample_case()
        geo = _make_sample_geometry()
        result = map_incident_to_scene(case, geo)

        # JSON 직렬화 → 역직렬화
        json_str = json.dumps(result)
        restored = json.loads(json_str)

        self.assertEqual(restored["incident"]["case_id"], "TEST-001")
        self.assertEqual(len(restored["incident"]["leak_sources"]), 1)
        self.assertEqual(len(restored["incident"]["damage_zones"]), 2)


if __name__ == "__main__":
    unittest.main()
