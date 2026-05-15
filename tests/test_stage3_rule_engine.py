import json
from compliance.evaluator import evaluate_project
from compliance.slm_adapter import slm_adapter

def test_stage3_rule_engine():
    # Mock compliance data
    compliance_data = {
        "page_index": 0,
        "metrics": {"px_to_m_scale": 0.01, "total_area_m2": 20.0},
        "rooms": [
            {
                "id": 1,
                "kind": "BEDROOM",
                "area_m2": 14.0,       # Requires 2.0 m2 window
                "height_mm": 2000.0,   # Fails rule 2 (>= 2100)
                "polygon": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 140}, {"x": 0, "y": 140}]
            },
            {
                "id": 2,
                "kind": "LDK",
                "area_m2": 28.0,       # Requires 4.0 m2 window
                "height_mm": 2400.0,   # Passes rule 2
                "polygon": [{"x": 200, "y": 0}, {"x": 400, "y": 0}, {"x": 400, "y": 140}, {"x": 200, "y": 140}]
            },
            {
                "id": 3,
                "kind": "CORRIDOR",    # Should be ignored by habitable room rules
                "area_m2": 10.0,
                "height_mm": 2000.0
            }
        ],
        "openings": [
            # A small window near BEDROOM (width 100px = 1m -> area = 1m * 1.5m = 1.5m2) -> Fails rule 1 (needs 2.0)
            {
                "id": 1,
                "kind": "WINDOW",
                "width_px": 100,
                "p1": {"x": 50, "y": 0},
                "p2": {"x": 50, "y": 0}
            },
            # A large window near LDK (width 300px = 3m -> area = 3m * 1.5m = 4.5m2) -> Passes rule 1 (needs 4.0)
            {
                "id": 2,
                "kind": "WINDOW",
                "width_px": 300,
                "p1": {"x": 300, "y": 0},
                "p2": {"x": 300, "y": 0}
            }
        ]
    }
    
    # Run evaluation
    report = evaluate_project(compliance_data)
    
    # Verify results
    assert report["status"] == "success"
    
    results = report["room_results"]
    assert len(results) == 3
    
    # BEDROOM check
    bedroom_res = results[0]["evaluations"]
    assert bedroom_res[0]["status"] == "FAIL" # Lighting < 2.0
    assert bedroom_res[1]["status"] == "FAIL" # Height < 2100
    
    # LDK check
    ldk_res = results[1]["evaluations"]
    assert ldk_res[0]["status"] == "PASS" # Lighting >= 4.0
    assert ldk_res[1]["status"] == "PASS" # Height >= 2100
    
    # CORRIDOR check
    corr_res = results[2]["evaluations"]
    assert corr_res[0]["status"] == "PASS" # Ignored
    assert corr_res[1]["status"] == "PASS" # Ignored
    
    # SLM check
    slm_reasoning = slm_adapter.generate_compliance_reasoning(report["slm_prompt_context"], compliance_data)
    assert "[SLM MOCK RESPONSE]" in slm_reasoning
    
    print("test_stage3_rule_engine passed successfully!")

if __name__ == "__main__":
    test_stage3_rule_engine()
