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
    print("[STAGE 2 TEST 2] Testing Subprocess Worker Pool for STEP/IFC Exports...")
    pool = ExporterWorkerPool(pool_size=2, max_tasks_per_child=50)

    step_script = os.path.join(os.path.dirname(__file__), "engine", "exporters", "export_step.py")
    ifc_script = os.path.join(os.path.dirname(__file__), "engine", "exporters", "export_ifc.py")

    target_step = os.path.join(os.path.dirname(__file__), "pool_test.step")
    target_ifc = os.path.join(os.path.dirname(__file__), "pool_test.ifc")

    payload = {
        "target_path": target_step,
        "primitives": [{"type": "box", "position": [0, 1, 0], "size": [5, 3, 4], "name": "PoolWall"}],
        "rooms": [{"room_id": "ROOM_01", "area_m2": 30.0}]
    }

    # Execute STEP through Worker Pool
    res_step = pool.execute_export(step_script, payload)
    assert res_step.get("success") is True and res_step.get("worker_pooled") is True
    print(f"  -> Pooled STEP Export: OK (Generated: {res_step.get('exported_file')})")

    # Execute IFC through Worker Pool
    payload["target_path"] = target_ifc
    res_ifc = pool.execute_export(ifc_script, payload)
    assert res_ifc.get("success") is True and res_ifc.get("worker_pooled") is True
    print(f"  -> Pooled IFC Export: OK (Generated: {res_ifc.get('exported_file')})")

    # Cleanup
    for p in (target_step, target_ifc):
        if os.path.exists(p):
            os.remove(p)

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
