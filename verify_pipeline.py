import os
import json
from core.engine import PipelineEngine
from unittest.mock import MagicMock

def verify_pipeline():
    print("=== Pipeline Verification ===")
    
    # 1. Setup Engine
    engine = PipelineEngine(project_id="verify_test")
    
    # 2. Mock Room Detection
    # Instead of a real PDF, we'll mock detect_rooms to return a fixed result
    import parser.room_detect
    
    mock_room = parser.room_detect.Room(
        id=1,
        contour=[(100, 100), (400, 100), (400, 400), (100, 400)],
        area_px=90000.0,
        bbox=(100, 100, 300, 300),
        kind="LDK"
    )
    mock_result = parser.room_detect.RoomResult(
        width=1000,
        height=1000,
        rooms=[mock_room],
        debug={}
    )
    
    parser.room_detect.detect_rooms = MagicMock(return_value=mock_result)
    
    # 3. Run Pipeline
    # Using a dummy pdf path
    result = engine.process_pdf("dummy.pdf")
    
    # 4. Check Results
    print(f"Status: {result['status']}")
    print(f"Artifacts: {list(result['artifacts'].keys())}")
    
    ifc_path = result['artifacts']['ifc']
    if os.path.exists(ifc_path):
        print(f"IFC File generated: {ifc_path} ({os.path.getsize(ifc_path)} bytes)")
    else:
        print("Error: IFC file not found!")
        exit(1)

    rooms_json_path = result['artifacts']['rooms_json']
    with open(rooms_json_path, "r", encoding="utf-8") as f:
        rooms_data = json.load(f)
        print(f"Rooms JSON validated. Found {len(rooms_data['rooms'])} rooms.")

    print("=== Verification Successful ===")

if __name__ == "__main__":
    verify_pipeline()
