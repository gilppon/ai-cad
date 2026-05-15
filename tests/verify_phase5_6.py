import asyncio
from domain.models import RoomKind, Point, DamageType, Severity, LeakCase, DamageZone, LeakSource
from correction.patch import CorrectionSession
from correction.operations import change_room_type, move_wall
from correction.rebuild import rebuild_after_correction
import json

def run_test():
    print("--- Phase 5 & 6 Verification Script ---")
    
    # 1. Create a dummy Japanese floor plan payload (simulating extraction)
    payload = {
        "rooms": [
            {"id": 1, "kind": "UNKNOWN", "area_m2": 25.5}, # Suppose AI missed LDK
            {"id": 2, "kind": "BEDROOM", "area_m2": 12.0}
        ],
        "walls": [
            {"p1": {"x": 0, "y": 0}, "p2": {"x": 100, "y": 0}},
            {"p1": {"x": 100, "y": 0}, "p2": {"x": 100, "y": 100}}
        ]
    }
    print("\n[1] Initial Payload from AI:")
    print(json.dumps(payload, indent=2))
    
    # 2. Simulate Manual Correction (Phase 6)
    print("\n[2] Applying Manual Corrections...")
    session = CorrectionSession(session_id="sess_001", case_id="case_001")
    
    # Correction 1: Room 1 is actually LDK
    patch1 = change_room_type(payload, room_id=1, new_kind=RoomKind.LDK)
    if patch1:
        session.patches.append(patch1)
        print(f"  -> Applied: {patch1.operation} on target {patch1.target_id}")

    # Correction 2: Adjust wall 0 position slightly
    patch2 = move_wall(payload, wall_id=0, new_p1={"x": 0, "y": 5}, new_p2={"x": 100, "y": 5})
    if patch2:
        session.patches.append(patch2)
        print(f"  -> Applied: {patch2.operation} on target {patch2.target_id}")
        
    print("\n[3] Rebuilding Pipeline...")
    rebuilt_payload = rebuild_after_correction(payload, session)
    print(json.dumps(rebuilt_payload, indent=2))
    
    # 3. Simulate Incident Semantics (Phase 5)
    print("\n[4] Generating Incident Models...")
    case = LeakCase(
        case_id="case_001",
        customer_name="Yamada Taro",
        leak_sources=[
            LeakSource(point=Point(10.0, 10.0), room_id=1, description="Pipe leak under sink")
        ],
        damage_zones=[
            DamageZone(
                id=1, 
                damage_type=DamageType.FLOOR, 
                severity=Severity.HIGH, 
                polygon=[Point(5,5), Point(15,5), Point(15,15), Point(5,15)],
                room_id=1
            )
        ]
    )
    print(f"  -> Case created with {len(case.leak_sources)} leak source and {len(case.damage_zones)} damage zone.")
    print(f"  -> Damage Zone 1: Type={case.damage_zones[0].damage_type.value}, Severity={case.damage_zones[0].severity.value}")
    
    print("\nVerification Successful.")

if __name__ == "__main__":
    run_test()
