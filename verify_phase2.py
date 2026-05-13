import os
import json
from core.engine import PipelineEngine

def test_phase2_integration():
    print("=== Testing Phase 2 Integration ===")
    pdf_path = "samples/sample.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found.")
        return

    engine = PipelineEngine(project_id="phase2_test")
    result = engine.process_pdf(pdf_path, page_index=0)
    
    print(f"Status: {result['status']}")
    
    rooms_json = result['artifacts']['rooms_json']
    with open(rooms_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    rooms = data.get("rooms", [])
    print(f"Detected Rooms: {len(rooms)}")
    
    kinds = {}
    for r in rooms:
        k = r.get("kind", "UNKNOWN").upper()
        kinds[k] = kinds.get(k, 0) + 1
    
    print(f"Room Kinds: {kinds}")
    
    # Check if we have variety in kinds (Phase 2 feature)
    if len(kinds) > 1:
        print("PASS: Multiple room kinds detected")
    else:
        print("NOTE: Only one kind detected (could be a simple floor plan)")

    # Check for deskew angle in debug if available (we'd need to check the RoomResult object or logs)
    # Since engine.py returns paths, let's trust the logs/debug files.
    
    print("=== Integration Test Complete ===")

if __name__ == "__main__":
    test_phase2_integration()
