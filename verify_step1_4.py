# -*- coding: utf-8 -*-
"""
verify_step1_4.py - Raster Pipeline Verification
Tests the full E2E flow for an image-based/scanned PDF.
"""
import os
import json
from core.engine import PipelineEngine

def test_raster_pipeline():
    print("="*60)
    print("Phase 1 - Step 1-4: Raster Pipeline Test (sample.pdf)")
    print("="*60)
    
    pdf_path = "samples/sample.pdf"
    project_id = "raster_test_run"
    
    # 1. Initialize
    print(f"\n[1] Initializing PipelineEngine for {project_id}...")
    engine = PipelineEngine(project_id=project_id)
    
    # 2. Run
    print(f"\n[2] Running process_pdf({pdf_path})...")
    # This might take some time if OpenCV/DL models are involved
    result = engine.process_pdf(pdf_path)
    
    # 3. Verify
    print("\n[3] Verifying result...")
    assert result["status"] == "success"
    
    rooms_json = result["artifacts"]["rooms_json"]
    print(f"\n[4] Checking rooms JSON: {rooms_json}")
    with open(rooms_json, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["kind"] == "geometry_payload"
    print(f"  -> rooms_count: {data['rooms_count']}")
    # Even if it's 0, it should be a valid list
    assert isinstance(data["rooms"], list)
    print("  [PASS] rooms JSON valid")
    
    ifc_path = result["artifacts"]["ifc"]
    print(f"\n[5] Checking IFC file: {ifc_path}")
    assert os.path.exists(ifc_path)
    print(f"  -> size: {os.path.getsize(ifc_path)} bytes")
    print("  [PASS] IFC file generated")

    print("\n" + "="*60)
    print("RASTER PIPELINE TEST: ALL PASSED!")
    print("="*60)

if __name__ == "__main__":
    test_raster_pipeline()
