# structure.py
from typing import List, Dict, Any
import math

import logging

logger = logging.getLogger(__name__)

class StructureHarness:
    """
    Validates structural integrity of the CAD model.
    """
    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        self.rooms = payload.get("rooms", [])
        self.walls = payload.get("walls", [])

    def check_all(self) -> Dict[str, Any]:
        results = {
            "orphaned_rooms": self.find_orphaned_rooms(),
            "overlapping_rooms": self.find_overlapping_rooms(),
            "integrity_score": 1.0
        }
        
        total_issues = len(results["orphaned_rooms"]) + len(results["overlapping_rooms"])
        results["integrity_score"] = max(0.0, 1.0 - (total_issues * 0.1))
        
        return results

    def find_orphaned_rooms(self) -> List[int]:
        """
        Finds rooms that have no walls within a certain threshold.
        """
        from shapely.geometry import Polygon, LineString
        orphans = []
        if not self.walls:
            return [r.get("id") for r in self.rooms]

        # Convert walls to LineStrings
        wall_lines = []
        for w in self.walls:
            p1 = w.get("p1", {})
            p2 = w.get("p2", {})
            wall_lines.append(LineString([(p1.get("x", 0), p1.get("y", 0)), (p2.get("x", 0), p2.get("y", 0))]))

        for r in self.rooms:
            poly_pts = [(p["x"], p["y"]) for p in r.get("polygon", [])]
            if len(poly_pts) < 3:
                orphans.append(r.get("id"))
                continue
            
            room_poly = Polygon(poly_pts)
            # Check if any wall is close to the room boundary
            has_nearby_wall = False
            for wl in wall_lines:
                if room_poly.distance(wl) < 50.0: # 50px threshold
                    has_nearby_wall = True
                    break
            
            if not has_nearby_wall:
                orphans.append(r.get("id"))

        return orphans

    def find_overlapping_rooms(self) -> List[List[int]]:
        """
        Detects if rooms overlap significantly (more than 10% of smaller room's area).
        """
        from shapely.geometry import Polygon
        overlaps = []
        room_polys = []
        
        for r in self.rooms:
            pts = [(p["x"], p["y"]) for p in r.get("polygon", [])]
            if len(pts) >= 3:
                room_polys.append((r.get("id"), Polygon(pts)))

        for i in range(len(room_polys)):
            for j in range(i + 1, len(room_polys)):
                id1, poly1 = room_polys[i]
                id2, poly2 = room_polys[j]
                
                if poly1.intersects(poly2):
                    inter_area = poly1.intersection(poly2).area
                    min_area = min(poly1.area, poly2.area)
                    if min_area > 0 and (inter_area / min_area) > 0.1:
                        overlaps.append([id1, id2])
        return overlaps

def validate_structure(payload: Dict[str, Any]) -> bool:
    harness = StructureHarness(payload)
    results = harness.check_all()
    logger.info(f"[*] Structural Integrity Score: {results['integrity_score']:.2f}")
    if results["integrity_score"] < 0.5:
        logger.error("[!] Warning: Low structural integrity detected.")
        return False
    return True
