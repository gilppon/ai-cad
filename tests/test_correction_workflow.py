# tests/test_correction_workflow.py — Phase 6 Manual Correction Workflow 테스트
"""
Phase 6 Exit Criteria: "The product is usable even when automation is imperfect"
검증 항목: 연산 10종, 세션 관리, 이력 추적, 재빌드 파이프라인
"""
import unittest
import os
import json
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from domain.models import RoomKind
from correction.patch import CorrectionPatch, CorrectionSession
from correction.operations import (
    change_room_type, move_wall, add_wall, delete_wall,
    merge_rooms, split_room, move_opening,
    place_leak_source, paint_damage_zone, delete_room,
)
from correction.rebuild import rebuild_after_correction
from correction.history import save_session, load_session, list_sessions, get_correction_stats


def _make_payload() -> dict:
    """테스트용 geometry payload"""
    return {
        "kind": "geometry_payload",
        "schema_version": "0.1.0",
        "page": 0,
        "page_index": 0,
        "canvas": {"width": 200, "height": 100},
        "rooms": [
            {
                "id": 0, "kind": "unknown", "area_m2": 25.0,
                "polygon": [
                    {"x": 0, "y": 0}, {"x": 100, "y": 0},
                    {"x": 100, "y": 100}, {"x": 0, "y": 100},
                ],
                "openings": [
                    {"id": 0, "p1": {"x": 40, "y": 0}, "p2": {"x": 60, "y": 0}, "kind": "door"},
                ],
                "metadata": {},
            },
            {
                "id": 1, "kind": "bedroom", "area_m2": 12.0,
                "polygon": [
                    {"x": 100, "y": 0}, {"x": 200, "y": 0},
                    {"x": 200, "y": 100}, {"x": 100, "y": 100},
                ],
                "openings": [],
                "metadata": {},
            },
        ],
        "rooms_count": 2,
        "walls": [
            {"id": 0, "p1": {"x": 0, "y": 0}, "p2": {"x": 100, "y": 0}},
            {"id": 1, "p1": {"x": 100, "y": 0}, "p2": {"x": 100, "y": 100}},
            {"id": 2, "p1": {"x": 100, "y": 100}, "p2": {"x": 0, "y": 100}},
        ],
        "walls_count": 3,
        "debug_files": {},
        "processing": {"stage": "test", "warnings": []},
        "incident": {},
    }


class TestOperations(unittest.TestCase):
    """연산 10종 테스트"""

    def test_change_room_type(self):
        payload = _make_payload()
        patch = change_room_type(payload, room_id=0, new_kind=RoomKind.LDK)

        self.assertIsNotNone(patch)
        self.assertEqual(patch.operation, "change_room_type")
        self.assertEqual(payload["rooms"][0]["kind"], "ldk")

    def test_change_room_type_no_change(self):
        """동일 kind로 변경 시 None 반환"""
        payload = _make_payload()
        payload["rooms"][0]["kind"] = "ldk"
        patch = change_room_type(payload, room_id=0, new_kind=RoomKind.LDK)
        self.assertIsNone(patch)

    def test_change_room_type_invalid_id(self):
        payload = _make_payload()
        patch = change_room_type(payload, room_id=999, new_kind=RoomKind.LDK)
        self.assertIsNone(patch)

    def test_move_wall(self):
        payload = _make_payload()
        patch = move_wall(payload, wall_id=0, new_p1={"x": 0, "y": 5}, new_p2={"x": 100, "y": 5})

        self.assertIsNotNone(patch)
        self.assertEqual(patch.operation, "move_wall")
        self.assertEqual(payload["walls"][0]["p1"]["y"], 5)

    def test_add_wall(self):
        payload = _make_payload()
        initial_count = len(payload["walls"])
        patch = add_wall(payload, p1={"x": 50, "y": 0}, p2={"x": 50, "y": 100})

        self.assertIsNotNone(patch)
        self.assertEqual(patch.operation, "add_wall")
        self.assertEqual(len(payload["walls"]), initial_count + 1)
        self.assertEqual(payload["walls_count"], initial_count + 1)

    def test_delete_wall(self):
        payload = _make_payload()
        initial_count = len(payload["walls"])
        patch = delete_wall(payload, wall_id=0)

        self.assertIsNotNone(patch)
        self.assertEqual(patch.operation, "delete_wall")
        self.assertEqual(len(payload["walls"]), initial_count - 1)

    def test_delete_wall_invalid_id(self):
        payload = _make_payload()
        patch = delete_wall(payload, wall_id=999)
        self.assertIsNone(patch)

    def test_merge_rooms(self):
        payload = _make_payload()
        patch = merge_rooms(payload, room_id_a=0, room_id_b=1, merged_kind="ldk")

        self.assertIsNotNone(patch)
        self.assertEqual(patch.operation, "merge_rooms")
        self.assertEqual(len(payload["rooms"]), 1)
        self.assertEqual(payload["rooms"][0]["kind"], "ldk")
        self.assertAlmostEqual(payload["rooms"][0]["area_m2"], 37.0)
        self.assertEqual(payload["rooms"][0]["metadata"]["merged_from"], [0, 1])

    def test_merge_rooms_same_id(self):
        payload = _make_payload()
        patch = merge_rooms(payload, room_id_a=0, room_id_b=0)
        self.assertIsNone(patch)

    def test_split_room_vertical(self):
        payload = _make_payload()
        patch = split_room(payload, room_id=0, split_axis="vertical", split_ratio=0.5)

        self.assertIsNotNone(patch)
        self.assertEqual(patch.operation, "split_room")
        self.assertEqual(len(payload["rooms"]), 3)  # 원본 2 + 분할 1

    def test_split_room_horizontal(self):
        payload = _make_payload()
        patch = split_room(payload, room_id=0, split_axis="horizontal", split_ratio=0.3)

        self.assertIsNotNone(patch)
        self.assertEqual(len(payload["rooms"]), 3)

    def test_move_opening(self):
        payload = _make_payload()
        patch = move_opening(payload, room_id=0, opening_idx=0,
                             new_p1={"x": 30, "y": 0}, new_p2={"x": 50, "y": 0})

        self.assertIsNotNone(patch)
        self.assertEqual(patch.operation, "move_opening")
        self.assertEqual(payload["rooms"][0]["openings"][0]["p1"]["x"], 30)

    def test_place_leak_source(self):
        payload = _make_payload()
        patch = place_leak_source(payload, point={"x": 50, "y": 50}, room_id=0,
                                  description="Pipe leak")

        self.assertIsNotNone(patch)
        self.assertEqual(patch.operation, "place_leak_source")
        self.assertEqual(len(payload["incident"]["leak_sources"]), 1)
        self.assertEqual(payload["incident"]["leak_sources"][0]["confidence"], 1.0)

    def test_paint_damage_zone(self):
        payload = _make_payload()
        polygon = [{"x": 10, "y": 10}, {"x": 30, "y": 10}, {"x": 30, "y": 30}, {"x": 10, "y": 30}]
        patch = paint_damage_zone(payload, damage_type="ceiling", severity="high",
                                  polygon=polygon, room_id=0)

        self.assertIsNotNone(patch)
        self.assertEqual(patch.operation, "paint_damage_zone")
        self.assertEqual(len(payload["incident"]["damage_zones"]), 1)

    def test_delete_room(self):
        payload = _make_payload()
        patch = delete_room(payload, room_id=1)

        self.assertIsNotNone(patch)
        self.assertEqual(patch.operation, "delete_room")
        self.assertEqual(len(payload["rooms"]), 1)
        self.assertEqual(payload["rooms_count"], 1)


class TestSession(unittest.TestCase):
    """세션 관리 및 직렬화 테스트"""

    def test_session_patch_tracking(self):
        """세션에 패치가 올바르게 누적"""
        payload = _make_payload()
        session = CorrectionSession(session_id="test-001", case_id="case-001")

        p1 = change_room_type(payload, 0, RoomKind.LDK)
        p2 = move_wall(payload, 0, {"x": 0, "y": 5}, {"x": 100, "y": 5})
        p3 = add_wall(payload, {"x": 50, "y": 0}, {"x": 50, "y": 100})

        for p in [p1, p2, p3]:
            if p:
                session.patches.append(p)

        self.assertEqual(session.patch_count, 3)
        self.assertEqual(session.operation_summary["change_room_type"], 1)
        self.assertEqual(session.operation_summary["move_wall"], 1)
        self.assertEqual(session.operation_summary["add_wall"], 1)

    def test_session_serialization(self):
        """세션 → dict → 세션 왕복"""
        payload = _make_payload()
        session = CorrectionSession(session_id="test-ser", case_id="case-ser")
        p = change_room_type(payload, 0, RoomKind.BATHROOM)
        if p:
            session.patches.append(p)

        d = session.to_dict()
        restored = CorrectionSession.from_dict(d)

        self.assertEqual(restored.session_id, "test-ser")
        self.assertEqual(restored.patch_count, 1)
        self.assertEqual(restored.patches[0].operation, "change_room_type")

    def test_correction_source_human(self):
        session = CorrectionSession(session_id="s1", case_id="c1")
        session.patches.append(CorrectionPatch(
            id="p1", operation="test", target_id=0,
            before={}, after={}, author="operator",
        ))
        self.assertEqual(session.correction_source, "human")
        self.assertTrue(session.is_human_corrected)

    def test_correction_source_auto(self):
        session = CorrectionSession(session_id="s2", case_id="c2")
        session.patches.append(CorrectionPatch(
            id="p2", operation="test", target_id=0,
            before={}, after={}, author="auto",
        ))
        self.assertEqual(session.correction_source, "auto")
        self.assertFalse(session.is_human_corrected)

    def test_correction_source_mixed(self):
        session = CorrectionSession(session_id="s3", case_id="c3")
        session.patches.append(CorrectionPatch(
            id="p3", operation="t1", target_id=0, before={}, after={}, author="auto",
        ))
        session.patches.append(CorrectionPatch(
            id="p4", operation="t2", target_id=1, before={}, after={}, author="operator",
        ))
        self.assertEqual(session.correction_source, "mixed")

    def test_session_apply(self):
        session = CorrectionSession(session_id="s4", case_id="c4")
        self.assertEqual(session.status, "draft")
        session.apply()
        self.assertEqual(session.status, "applied")


class TestHistory(unittest.TestCase):
    """이력 저장/로드/통계 테스트"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_save_and_load_session(self):
        session = CorrectionSession(session_id="hist-001", case_id="case-hist")
        session.patches.append(CorrectionPatch(
            id="p1", operation="change_room_type", target_id=0,
            before={"kind": "unknown"}, after={"kind": "ldk"},
        ))

        path = save_session(session, self.tmp_dir)
        self.assertTrue(os.path.exists(path))

        loaded = load_session("hist-001", self.tmp_dir)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.session_id, "hist-001")
        self.assertEqual(loaded.patch_count, 1)

    def test_load_nonexistent_session(self):
        loaded = load_session("nonexistent", self.tmp_dir)
        self.assertIsNone(loaded)

    def test_list_sessions(self):
        for i in range(3):
            s = CorrectionSession(session_id=f"list-{i}", case_id="c")
            s.patches.append(CorrectionPatch(
                id=f"p{i}", operation="test", target_id=i, before={}, after={},
            ))
            save_session(s, self.tmp_dir)

        sessions = list_sessions(self.tmp_dir)
        self.assertEqual(len(sessions), 3)

    def test_get_correction_stats(self):
        for i in range(2):
            s = CorrectionSession(session_id=f"stat-{i}", case_id="c")
            s.patches.append(CorrectionPatch(
                id=f"sp{i}", operation="change_room_type", target_id=i, before={}, after={},
            ))
            if i == 1:
                s.patches.append(CorrectionPatch(
                    id=f"sp{i}b", operation="move_wall", target_id=i, before={}, after={},
                ))
            save_session(s, self.tmp_dir)

        stats = get_correction_stats(self.tmp_dir)
        self.assertEqual(stats["total_sessions"], 2)
        self.assertEqual(stats["total_patches"], 3)
        self.assertEqual(stats["operations_breakdown"]["change_room_type"], 2)
        self.assertEqual(stats["operations_breakdown"]["move_wall"], 1)


class TestRebuild(unittest.TestCase):
    """재빌드 파이프라인 테스트"""

    def test_rebuild_metadata(self):
        """재빌드 후 메타데이터가 올바르게 기록"""
        payload = _make_payload()
        session = CorrectionSession(session_id="rebuild-001", case_id="case-rb")
        p = change_room_type(payload, 0, RoomKind.LDK)
        if p:
            session.patches.append(p)

        result = rebuild_after_correction(payload, session)

        self.assertTrue(result["refined"])
        self.assertTrue(result["correction_applied"])
        self.assertEqual(result["last_correction_session"], "rebuild-001")
        self.assertEqual(result["correction_source"], "human")
        self.assertEqual(result["processing"]["stage"], "post_correction")
        self.assertEqual(len(result["processing"]["corrections"]), 1)

    def test_rebuild_recounts(self):
        """재빌드 후 rooms_count / walls_count 재계산"""
        payload = _make_payload()
        session = CorrectionSession(session_id="rebuild-002", case_id="case-rc")
        delete_room(payload, room_id=1)
        session.patches.append(CorrectionPatch(
            id="del", operation="delete_room", target_id=1, before={}, after={},
        ))

        result = rebuild_after_correction(payload, session)

        self.assertEqual(result["rooms_count"], 1)
        self.assertEqual(result["walls_count"], 3)

    def test_rebuild_session_applied(self):
        """재빌드 후 세션이 applied 상태"""
        payload = _make_payload()
        session = CorrectionSession(session_id="rebuild-003", case_id="case-app")

        rebuild_after_correction(payload, session)
        self.assertEqual(session.status, "applied")


class TestEndToEnd(unittest.TestCase):
    """E2E 시나리오: 자동 추출 → 수동 보정 → 재빌드"""

    def test_full_correction_workflow(self):
        """운영자가 3분 안에 할 수 있는 보정 시나리오"""
        payload = _make_payload()
        session = CorrectionSession(session_id="e2e-001", case_id="case-e2e")

        # 1. AI가 room 0을 unknown으로 잡음 → 운영자가 LDK로 보정
        p1 = change_room_type(payload, 0, RoomKind.LDK)
        self.assertIsNotNone(p1)
        session.patches.append(p1)

        # 2. 벽 하나가 살짝 어긋남 → 운영자가 위치 조정
        p2 = move_wall(payload, 0, {"x": 0, "y": 2}, {"x": 100, "y": 2})
        self.assertIsNotNone(p2)
        session.patches.append(p2)

        # 3. 불필요한 벽 세그먼트 삭제
        p3 = delete_wall(payload, 2)
        self.assertIsNotNone(p3)
        session.patches.append(p3)

        # 4. 누수 소스 배치
        p4 = place_leak_source(payload, {"x": 50, "y": 50}, room_id=0, description="Main leak")
        self.assertIsNotNone(p4)
        session.patches.append(p4)

        # 5. 데미지 영역 페인팅
        p5 = paint_damage_zone(payload, "ceiling", "high",
                               [{"x": 30, "y": 30}, {"x": 70, "y": 30}, {"x": 70, "y": 70}, {"x": 30, "y": 70}],
                               room_id=0)
        self.assertIsNotNone(p5)
        session.patches.append(p5)

        # 검증
        self.assertEqual(session.patch_count, 5)
        self.assertTrue(session.is_human_corrected)
        self.assertEqual(session.correction_source, "human")

        # 재빌드
        result = rebuild_after_correction(payload, session)
        self.assertTrue(result["correction_applied"])
        self.assertEqual(result["rooms_count"], 2)
        self.assertEqual(result["walls_count"], 2)  # 3 - 1 삭제

        # 인시던트 데이터가 payload 안에 존재
        self.assertEqual(len(result["incident"]["leak_sources"]), 1)
        self.assertEqual(len(result["incident"]["damage_zones"]), 1)

        # 세션 상태
        self.assertEqual(session.status, "applied")

        # 직렬화 왕복
        session_dict = session.to_dict()
        restored = CorrectionSession.from_dict(session_dict)
        self.assertEqual(restored.patch_count, 5)
        self.assertEqual(restored.correction_source, "human")


if __name__ == "__main__":
    unittest.main()
