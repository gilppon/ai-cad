import os
import json
from compliance.extractor import extract_compliance_data

def test_stage2_compliance_extraction():
    # 1. Create a dummy payload
    dummy_payload = {
        "page_index": 0,
        "rooms": [
            {
                "id": 1,
                "kind": "BEDROOM",
                "area_px2": 10000.0,
                "height_mm": 2400.0,
                "polygon": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}, {"x": 0, "y": 100}]
            },
            {
                "id": 2,
                "kind": "LDK",
                "area_px2": 50000.0,
                "polygon": [{"x": 100, "y": 0}, {"x": 600, "y": 0}, {"x": 600, "y": 100}, {"x": 100, "y": 100}]
            }
        ]
    }
    
    output_dir = "out/test_compliance"
    os.makedirs(output_dir, exist_ok=True)
    
    # 2. Extract
    compliance = extract_compliance_data(dummy_payload, output_dir, page_index=0)
    
    # 3. Verify
    assert compliance["page_index"] == 0
    assert len(compliance["rooms"]) == 2
    
    # Check scaling (area_px2 * (0.01^2) = area_px2 * 0.0001)
    # 10000 * 0.0001 = 1.0 m2
    assert compliance["rooms"][0]["area_m2"] == 1.0
    # 50000 * 0.0001 = 5.0 m2
    assert compliance["rooms"][1]["area_m2"] == 5.0
    
    # Check default height injection
    assert compliance["rooms"][1]["height_mm"] == 2400.0
    
    # Check total metrics
    assert compliance["metrics"]["total_area_m2"] == 6.0
    
    print("test_stage2_compliance_extraction passed successfully!")

if __name__ == "__main__":
    test_stage2_compliance_extraction()
