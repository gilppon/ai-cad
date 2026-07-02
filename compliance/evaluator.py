import json
from typing import Dict, Any, List
from compliance.rules import JAPAN_BUILDING_RULES

def point_to_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculates the shortest distance from a point (px, py) to a line segment (x1, y1) - (x2, y2)."""
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5

def is_point_near_polygon_boundary(px: float, py: float, poly: List[Dict[str, float]], max_dist: float = 30.0) -> bool:
    """Checks if a point (px, py) is within max_dist of any segment of the polygon."""
    if not poly or len(poly) < 2:
        return False
    n = len(poly)
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        dist = point_to_segment_distance(px, py, p1["x"], p1["y"], p2["x"], p2["y"])
        if dist <= max_dist:
            return True
    return False

def evaluate_project(compliance_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates the compliance data extracted in Stage 2 against the deterministic rules.
    Returns a comprehensive compliance report.
    """
    rooms = compliance_data.get("rooms", [])
    openings = compliance_data.get("openings", [])
    
    # Pre-process: Calculate actual_window_area_m2 for each room
    # To keep it deterministic, we find openings near the room walls using segment distance.
    px_to_m = compliance_data.get("metrics", {}).get("px_to_m_scale", 0.01)
    
    for room in rooms:
        room_window_px2 = 0.0
        poly = room.get("polygon", [])
        if poly:
            for op in openings:
                if op.get("kind") == "WINDOW":
                    op_p1 = op.get("p1", {"x": 0, "y": 0})
                    op_p2 = op.get("p2", {"x": 0, "y": 0})
                    # Center of opening
                    cx = (op_p1["x"] + op_p2["x"]) / 2
                    cy = (op_p1["y"] + op_p2["y"]) / 2
                    
                    # If window is near any wall segment of this room
                    if is_point_near_polygon_boundary(cx, cy, poly, max_dist=30.0):
                        # Approximate window area: width * 1.5m height
                        w_px = op.get("width_px", 50)
                        w_m = w_px * px_to_m
                        h_m = 1.5 # standard 1.5m window height
                        room_window_px2 += (w_m * h_m) / (px_to_m ** 2)
                        
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
