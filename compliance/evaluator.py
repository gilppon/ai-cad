import json
from typing import Dict, Any, List
from compliance.rules import JAPAN_BUILDING_RULES

def evaluate_project(compliance_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates the compliance data extracted in Stage 2 against the deterministic rules.
    Returns a comprehensive compliance report.
    """
    rooms = compliance_data.get("rooms", [])
    openings = compliance_data.get("openings", [])
    
    # Pre-process: Calculate actual_window_area_m2 for each room
    # (For MVP, we just randomly assign some window area or we need a proper geometric intersection.
    # To keep it deterministic without complex geometry here, we'll try to find openings near the room,
    # or just rely on a pre-calculated field if present).
    # Since we didn't calculate intersection in Stage 2, let's do a simple heuristic:
    # If a WINDOW is within the bounding box of a room, add its area to the room.
    
    # This is a naive geometric check for MVP
    px_to_m = compliance_data.get("metrics", {}).get("px_to_m_scale", 0.01)
    
    for room in rooms:
        room_window_px2 = 0.0
        poly = room.get("polygon", [])
        if poly:
            min_x = min(p["x"] for p in poly)
            max_x = max(p["x"] for p in poly)
            min_y = min(p["y"] for p in poly)
            max_y = max(p["y"] for p in poly)
            
            for op in openings:
                if op.get("kind") == "WINDOW":
                    op_p1 = op.get("p1", {"x": 0, "y": 0})
                    op_p2 = op.get("p2", {"x": 0, "y": 0})
                    # Center of opening
                    cx = (op_p1["x"] + op_p2["x"]) / 2
                    cy = (op_p1["y"] + op_p2["y"]) / 2
                    
                    # Add a margin for intersection (walls are thick)
                    margin = 30
                    if (min_x - margin <= cx <= max_x + margin) and (min_y - margin <= cy <= max_y + margin):
                        # Approximate window area: width * 1500mm height
                        w_px = op.get("width_px", 50)
                        w_m = w_px * px_to_m
                        h_m = 1.5 # standard 1.5m window height
                        room_window_px2 += (w_m * h_m) / (px_to_m ** 2) # store as px2, wait, just calc m2 directly
                        
        # Store actual window area in m2
        if "actual_window_area_m2" not in room:
             room["actual_window_area_m2"] = room_window_px2 * (px_to_m ** 2)
             
    # Evaluate
    results = []
    total_violations = 0
    
    for room in rooms:
        room_id = room.get("id", "unknown")
        room_kind = room.get("kind", "UNKNOWN")
        
        room_report = {
            "room_id": room_id,
            "room_kind": room_kind,
            "evaluations": []
        }
        
        for rule in JAPAN_BUILDING_RULES:
            eval_result = rule.evaluate(room, compliance_data)
            
            eval_record = {
                "rule_id": rule.rule_id,
                "rule_name": rule.name,
                "status": eval_result.get("status"),
                "reason": eval_result.get("reason")
            }
            
            if eval_result.get("status") == "FAIL":
                total_violations += 1
                
            room_report["evaluations"].append(eval_record)
            
        results.append(room_report)
        
    # SLM Context preparation (for later fine-tuning/inference)
    # Provide a text-based summary of the violations
    slm_context = "Project Compliance Summary:\n"
    for r in results:
        fails = [e for e in r["evaluations"] if e["status"] == "FAIL"]
        if fails:
            slm_context += f"Room {r['room_id']} ({r['room_kind']}):\n"
            for f in fails:
                slm_context += f"  - [{f['rule_id']}] {f['reason']}\n"
                
    if total_violations == 0:
        slm_context += "No deterministic rule violations found. SLM can perform further contextual checks.\n"
        
    return {
        "status": "success",
        "total_violations": total_violations,
        "room_results": results,
        "slm_prompt_context": slm_context
    }
