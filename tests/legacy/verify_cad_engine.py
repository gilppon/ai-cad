"""
Verification Script for AI-CAD Core Engineering Suite.
Tests:
1. PSLG Topology & Fuzzy Snapping Room Extraction
2. Deterministic Japan Building Standard Law Rules (Track 1)
3. e-Gov Hierarchical XML RAG & 1:1 Citation Binding (Track 2)
4. SLM Adapter Fallback Circuit Breaker
"""
import sys
import os

# Add workspace to path
sys.path.insert(0, os.path.dirname(__file__))

from engine.geometry.pslg_topology import PSLGTopologyEngine
from engine.compliance.rules import JapanBuildingCodeRules, RuleStatus
from engine.compliance.compliance import DualTrackComplianceEngine
from engine.inference.slm_adapter import SLMInferenceAdapter

def test_pslg_topology():
    print("[TEST 1] Testing PSLG Topology & Fuzzy Snapping...")
    engine = PSLGTopologyEngine(snap_tolerance=3.0, min_room_area=1.0)
    
    # 4 walls forming a 10m x 10m room with slight snap gaps (1.5px misalignment)
    segments = [
        ((0.0, 0.0), (10.0, 1.2)),     # Bottom wall (misaligned end)
        ((10.0, 0.0), (10.0, 10.0)),   # Right wall
        ((10.0, 10.0), (0.0, 9.5)),    # Top wall (misaligned end)
        ((0.0, 10.0), (0.0, 0.0)),     # Left wall
    ]
    
    rooms = engine.extract_room_polygons(segments)
    assert len(rooms) >= 1, f"Expected at least 1 room polygon, got {len(rooms)}"
    room = rooms[0]
    print(f"  -> Extracted Room: {room['room_id']}, Area: {room['area_m2']} m², Perimeter: {room['perimeter_m']} m")
    print("  [PASS] PSLG Topology & Snapping OK!")

def test_deterministic_rules():
    print("[TEST 2] Testing Deterministic Japan Building Law Rules (Track 1)...")
    
    # Room 1: 14m², window 1.0m² (Required: 14 / 7 = 2.0m² -> FAIL)
    res_daylight_fail = JapanBuildingCodeRules.check_daylight_ratio("living", 14.0, 1.0)
    assert res_daylight_fail.status == RuleStatus.FAIL, "Daylight should fail for 1.0m² / 14m²"
    print(f"  -> Daylight Check (Deficit): {res_daylight_fail.status.value} - {res_daylight_fail.description}")
    
    # Room 2: 14m², window 2.5m² (Required: 2.0m² -> PASS)
    res_daylight_pass = JapanBuildingCodeRules.check_daylight_ratio("living", 14.0, 2.5)
    assert res_daylight_pass.status == RuleStatus.PASS, "Daylight should pass for 2.5m² / 14m²"
    print(f"  -> Daylight Check (Compliant): {res_daylight_pass.status.value}")

    # Stair width check (70cm in residential -> FAIL, threshold 75cm)
    res_stair_fail = JapanBuildingCodeRules.check_stair_width(70.0, "residential")
    assert res_stair_fail.status == RuleStatus.FAIL
    print(f"  -> Stair Width Check: {res_stair_fail.status.value} - {res_stair_fail.description}")
    print("  [PASS] Deterministic Rules OK!")

def test_dual_track_compliance_report():
    print("[TEST 3] Testing Dual-Track Compliance Report (Track 1 + Track 2 1:1 Citation Binding)...")
    compliance_engine = DualTrackComplianceEngine()
    
    test_room_data = {
        "room_id": "ROOM_01",
        "room_type": "living_room",
        "floor_area_m2": 21.0,
        "window_effective_area_m2": 1.5,  # 1.5m² < 3.0m² (21/7) -> FAILS Daylight
        "vent_opening_area_m2": 1.2,      # 1.2m² > 1.05m² (21/20) -> PASSES Vent
        "stair_width_cm": 80.0            # 80cm > 75cm -> PASSES Stair
    }
    
    report = compliance_engine.evaluate_room(test_room_data)
    print(f"  -> Overall Verdict: {report.overall_verdict} ({report.passed_count} Passed, {report.failed_count} Failed)")
    for item in report.items:
        print(f"     [{item.status}] {item.law_article_id}: {item.description}")
        if item.remedy_suggestion:
            print(f"        💡 Remedy: {item.remedy_suggestion}")
        assert item.law_snippet, "Law snippet must be bound 1:1"
        
    assert report.failed_count == 1, "Expected exactly 1 failed check (daylight)"
    print("  [PASS] Dual-Track Compliance Engine OK!")

def test_slm_adapter_circuit_breaker():
    print("[TEST 4] Testing SLM Adapter & Circuit Breaker...")
    adapter = SLMInferenceAdapter(base_url="http://127.0.0.1:9999/v1", timeout_seconds=0.5)
    
    schema = {"type": "object", "properties": {"status": {"type": "string"}}}
    # Call offline port -> should gracefully catch and trigger cloud fallback without crashing
    res = adapter.generate_structured("Extract 3D box", schema)
    assert res.get("fallback_used") is True, "Expected fallback on unreachable local SLM"
    print(f"  -> Fallback Result: {res['reason']}")
    print("  [PASS] SLM Adapter & Circuit Breaker OK!")

if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    print("=" * 60)
    print("[KODARI DEV LEGION] AI-CAD VERIFICATION SUITE")
    print("=" * 60)
    test_pslg_topology()
    test_deterministic_rules()
    test_dual_track_compliance_report()
    test_slm_adapter_circuit_breaker()
    print("=" * 60)
    print("[ALL 4 VERIFICATION GATES PASSED 100%!]")
    print("=" * 60)
