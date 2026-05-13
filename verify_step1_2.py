# -*- coding: utf-8 -*-
"""
Phase 1 - Step 1-2: E2E Pipeline Test with sample.pdf
engine.py -> room_detect -> room_export -> export_ifc
"""
import sys
import os
import json
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("=" * 60)
    print("Phase 1 - Step 1-2: E2E Pipeline Test")
    print("=" * 60)

    pdf_path = os.path.join("samples", "sample.pdf")
    if not os.path.exists(pdf_path):
        print("[FAIL] Sample PDF not found: {}".format(pdf_path))
        return False

    print("\n[1] Initializing PipelineEngine...")
    from core.engine import PipelineEngine
    engine = PipelineEngine(project_id="e2e_test")
    print("  -> output_dir: {}".format(engine.output_dir))

    print("\n[2] Running process_pdf({})...".format(pdf_path))
    try:
        result = engine.process_pdf(pdf_path, page_index=0)
    except Exception as e:
        print("[FAIL] process_pdf crashed:")
        traceback.print_exc()
        return False

    print("\n[3] Verifying result...")
    # Check status
    status = result.get("status")
    print("  -> status: {}".format(status))
    if status != "success":
        print("[FAIL] Expected status=success, got {}".format(status))
        return False

    artifacts = result.get("artifacts", {})

    # Check rooms JSON
    rooms_json_path = artifacts.get("rooms_json")
    print("\n[4] Checking rooms JSON: {}".format(rooms_json_path))
    if not rooms_json_path or not os.path.exists(rooms_json_path):
        print("[FAIL] rooms JSON file not found")
        return False
    with open(rooms_json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    print("  -> kind: {}".format(payload.get("kind")))
    print("  -> rooms_count: {}".format(payload.get("rooms_count")))
    print("  -> canvas: {}".format(payload.get("canvas")))
    rooms = payload.get("rooms", [])
    for r in rooms[:3]:
        print("  -> room {}: kind={}, area_m2={}".format(r.get("id"), r.get("kind"), r.get("area_m2", "N/A")))
    if len(rooms) > 3:
        print("  -> ... and {} more rooms".format(len(rooms) - 3))
    print("  [PASS] rooms JSON valid")

    # Validate with contracts
    from pipeline.contracts import validate_geometry_payload
    try:
        validate_geometry_payload(payload)
        print("  [PASS] GeometryPayload contract validation")
    except Exception as e:
        print("  [FAIL] Contract validation: {}".format(e))
        return False

    # Check IFC file
    ifc_path = artifacts.get("ifc")
    print("\n[5] Checking IFC file: {}".format(ifc_path))
    if not ifc_path or not os.path.exists(ifc_path):
        print("[FAIL] IFC file not found")
        return False
    ifc_size = os.path.getsize(ifc_path)
    print("  -> size: {} bytes".format(ifc_size))
    if ifc_size < 100:
        print("[FAIL] IFC file too small (probably empty)")
        return False
    print("  [PASS] IFC file exists ({} bytes)".format(ifc_size))

    # Check IFC meta
    ifc_meta_path = artifacts.get("ifc_meta")
    print("\n[6] Checking IFC meta: {}".format(ifc_meta_path))
    if not ifc_meta_path or not os.path.exists(ifc_meta_path):
        print("[FAIL] IFC meta file not found")
        return False
    with open(ifc_meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    print("  -> kind: {}".format(meta.get("kind")))
    print("  -> counts: {}".format(meta.get("counts")))
    print("  [PASS] IFC meta valid")

    print("\n" + "=" * 60)
    print("E2E PIPELINE TEST: ALL PASSED!")
    print("  Artifacts generated:")
    for k, v in artifacts.items():
        print("    - {}: {}".format(k, v))
    print("=" * 60)
    return True

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
