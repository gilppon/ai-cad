# -*- coding: utf-8 -*-
"""
verify_step1_3.py - Vector Pipeline Verification
Tests the full E2E flow for a vector-based PDF.
"""
import os
import json
from core.engine import PipelineEngine

def test_vector_pipeline():
    print("="*60)
    print("Phase 1 - Step 1-3: Vector Pipeline Test")
    print("="*60)
    
    pdf_path = "samples/vector_test.pdf"
    project_id = "vector_test_run"
    
    # 1. Initialize
    print(f"\n[1] Initializing PipelineEngine for {project_id}...")
    engine = PipelineEngine(project_id=project_id)
    
    # 2. Run
    print(f"\n[2] Running process_pdf({pdf_path})...")
    result = engine.process_pdf(pdf_path)
    
    # 3. Verify
    print("\n[3] Verifying result...")
    assert result["status"] == "success"
    
    rooms_json = result["artifacts"]["rooms_json"]
    print(f"\n[4] Checking rooms JSON: {rooms_json}")
    with open(rooms_json, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["kind"] == "geometry_payload"
    # Our synthetic PDF has 4 (box) + 12 (inner) = 16 lines
    print(f"  -> walls_count: {data['walls_count']}")
    assert data["walls_count"] >= 16
    assert data["rooms_count"] == 0  # Vector extractor doesn't find rooms yet
    print("  [PASS] rooms JSON valid and contains walls")
    
    ifc_path = result["artifacts"]["ifc"]
    print(f"\n[5] Checking IFC file: {ifc_path}")
    assert os.path.exists(ifc_path)
    print(f"  -> size: {os.path.getsize(ifc_path)} bytes")
    print("  [PASS] IFC file generated")

    print("\n" + "="*60)
    print("VECTOR PIPELINE TEST: ALL PASSED!")
    print("="*60)

if __name__ == "__main__":
    test_vector_pipeline()
