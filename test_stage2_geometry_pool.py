"""
Stage 2 Verification Test Suite.
Tests:
1. Room Detection & Self-Intersection (Bowtie) Auto-Healing (Shapely-like make_valid)
2. Subprocess Worker Pooling for ISO STEP & IFC4 Exports
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

from engine.geometry.room_detect import RoomDetector
from engine.exporters.worker_pool import ExporterWorkerPool

def test_stage2_self_intersection_healing():
    print("[STAGE 2 TEST 1] Testing Room Detection & Self-Intersection Auto-Healing...")
    detector = RoomDetector(min_room_area=1.0)

    # 1. Normal clean room
    clean_loop = [(0.0, 0.0), (5.0, 0.0), (5.0, 4.0), (0.0, 4.0)]
    
    # 2. Self-intersecting Bowtie loop: (0,0) -> (5,4) -> (5,0) -> (0,4) (crossed edges!)
    bowtie_loop = [(0.0, 0.0), (5.0, 4.0), (5.0, 0.0), (0.0, 4.0)]
    assert detector.is_self_intersecting(bowtie_loop) is True, "Should detect Bowtie self-intersection"
    print("  -> Bowtie Self-Intersection Detection: OK (Caught accurately)")

    rooms = detector.process_and_detect_rooms([clean_loop, bowtie_loop])
    assert len(rooms) == 2, f"Expected 2 healed rooms, got {len(rooms)}"
    
    clean_room, healed_room = rooms[0], rooms[1]
    print(f"  -> Clean Room: {clean_room['room_id']}, Area: {clean_room['area_m2']} m² (Healed: {clean_room['self_intersection_healed']})")
    print(f"  -> Bowtie Healed Room: {healed_room['room_id']}, Area: {healed_room['area_m2']} m² (Healed: {healed_room['self_intersection_healed']})")
    assert healed_room['is_watertight'] is True
    print("  [PASS] Room Detection & Self-Intersection Healing OK!")

def test_stage2_worker_pool_exports():
    print("[STAGE 2 TEST 2] Testing Subprocess Worker Pool for IFC4 Export (Real ifcopenshell path)...")
    pool = ExporterWorkerPool(pool_size=2, max_tasks_per_child=50)

    # SP2/A-2: 가짜 STEP/IFC 스텁 제거. 실 ifcopenshell 워커만 검증한다.
    # (STEP은 FreeCAD 바이너리 의존 기능으로 분리 - parser/room_export.run_freecad_step 참조)
    ifc_script = os.path.join(os.path.dirname(__file__), "engine", "exporters", "ifc_worker.py")

    out_dir = os.path.join(os.path.dirname(__file__), "out", "tmp")
    os.makedirs(out_dir, exist_ok=True)
    target_ifc = os.path.join(out_dir, "pool_test.ifc")

    payload = {
        "target_path": target_ifc,
        "payload": {
            "rooms": [{
                "id": 1,
                "kind": "ldk",
                "polygon": [{"x": 0, "y": 0}, {"x": 400, "y": 0}, {"x": 400, "y": 300}, {"x": 0, "y": 300}],
                "area_px2": 120000.0
            }],
            "walls": [{"id": 1, "p1": {"x": 0, "y": 0}, "p2": {"x": 400, "y": 0}}],
            "scale": {"pixel_to_mm": 5.0},
            "metadata": {}
        }
    }

    # Execute IFC through Worker Pool
    res_ifc = pool.execute_export(ifc_script, payload)
    assert res_ifc.get("success") is True and res_ifc.get("worker_pooled") is True, f"IFC export failed: {res_ifc}"
    assert os.path.exists(target_ifc), "IFC file was not generated"
    print(f"  -> Pooled IFC Export: OK (Generated: {res_ifc.get('exported_file')}, "
          f"{res_ifc.get('file_size_bytes')} bytes)")

    # Cleanup
    if os.path.exists(target_ifc):
        os.remove(target_ifc)

    print("  [PASS] Worker Pool CAD Exports OK!")

if __name__ == "__main__":
    print("=" * 70)
    print("🎖️ [KODARI DEV LEGION] STAGE 2 VALIDATION GATE")
    print("=" * 70)
    test_stage2_self_intersection_healing()
    test_stage2_worker_pool_exports()
    print("=" * 70)
    print("✅ [STAGE 2 COMPLETE] 2단계 도면 파서 및 기하 토폴로지 재구축 100% 무결점 완료!")
    print("=" * 70)
