"""
Stage 1 Verification Test Suite.
Tests:
1. Pydantic v2 SSOT Models & Pipeline Contracts Synchronization
2. Japan Building Code Article 28 (Daylight/Vent) and Article 35 (Evacuation/Travel Distance/Dual Stair) Rules
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

from engine.domain.models import CADPrimitive3D, RoomGeometry, FloorplanDocument
from engine.pipeline.contracts import Generate3DRequestContract, Generate3DResponseContract
from engine.compliance.rules import JapanBuildingCodeRules, RuleStatus

def test_stage1_contracts_sync():
    print("[STAGE 1 TEST 1] Testing Pydantic v2 SSOT & Pipeline Contracts Synchronization...")
    
    # 1. Test Request Contract Validation
    req = Generate3DRequestContract(
        image_base64="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        project_name="Tokyo Residence 2026",
        scale_hint="1:100",
        check_compliance=True
    )
    assert req.project_name == "Tokyo Residence 2026"
    print("  -> Generate3DRequestContract: OK")

    # 2. Test SSOT Floorplan & Response Contract
    room1 = RoomGeometry(
        room_id="ROOM_01",
        room_type="living_room",
        vertices=[(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)],
        area_m2=24.0,
        perimeter_m=20.0,
        window_effective_area_m2=3.8,
        vent_opening_area_m2=1.5
    )
    primitive1 = CADPrimitive3D(
        type="box",
        position=(0.0, 1.5, 0.0),
        size=(6.0, 3.0, 4.0),
        color="#4f46e5",
        name="LivingRoom_Mesh"
    )
    floorplan = FloorplanDocument(
        doc_id="DOC_STAGE1_001",
        building_name="Tokyo Residence",
        rooms=[room1],
        primitives=[primitive1]
    )

    resp = Generate3DResponseContract(
        status="SUCCESS",
        floorplan=floorplan,
        processing_time_ms=12.5,
        compliance_summary={"overall": "PASS"}
    )
    assert resp.floorplan.rooms[0].area_m2 == 24.0
    print("  -> Generate3DResponseContract & SSOT Serialization: OK")
    print("  [PASS] Models & Contracts Sync OK!")

def test_stage1_article_28_and_35_rules():
    print("[STAGE 1 TEST 2] Testing Japan Building Code Article 28 & Article 35 Rules Engine...")
    
    # Article 28 (Daylight 1/7, Vent 1/20)
    res_daylight = JapanBuildingCodeRules.check_daylight_ratio("living", 21.0, 3.5) # 3.5 > 3.0 -> PASS
    assert res_daylight.status == RuleStatus.PASS
    print(f"  -> Art 28 (Daylight): {res_daylight.status.value} - {res_daylight.description}")

    # Article 35 & Order 120 (Evacuation Travel Distance: Fireproof max 50m, Non-fireproof max 30m)
    res_dist_pass = JapanBuildingCodeRules.check_evacuation_travel_distance(42.0, is_fireproof=True) # 42m <= 50m -> PASS
    assert res_dist_pass.status == RuleStatus.PASS
    print(f"  -> Art 35 (Evac Distance Compliant): {res_dist_pass.status.value} - {res_dist_pass.description}")

    res_dist_fail = JapanBuildingCodeRules.check_evacuation_travel_distance(35.0, is_fireproof=False) # 35m > 30m -> FAIL
    assert res_dist_fail.status == RuleStatus.FAIL
    print(f"  -> Art 35 (Evac Distance Non-Fireproof Exceeded): {res_dist_fail.status.value} - {res_dist_fail.description}")

    # Order 121 (Dual Staircase: 6th floor area > 100m² -> WARNING)
    res_dual_stair = JapanBuildingCodeRules.check_dual_staircase_requirement(150.0, floor_level=7)
    assert res_dual_stair.status == RuleStatus.WARNING
    print(f"  -> Art 35 / Ord 121 (Dual Staircase Warning): {res_dual_stair.status.value} - {res_dual_stair.description}")
    print("  [PASS] Article 28 & 35 Rules Engine OK!")

if __name__ == "__main__":
    print("=" * 70)
    print("🎖️ [KODARI DEV LEGION] STAGE 1 VALIDATION GATE")
    print("=" * 70)
    test_stage1_contracts_sync()
    test_stage1_article_28_and_35_rules()
    print("=" * 70)
    print("✅ [STAGE 1 COMPLETE] 1단계 코어 데이터 모델 및 룰 엔진 분리 100% 무결점 완료!")
    print("=" * 70)
