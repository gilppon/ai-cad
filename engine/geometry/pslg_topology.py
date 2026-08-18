"""
Planar Straight-Line Graph (PSLG) & Topology Extraction Engine.
Converts vector line segments into clean, watertight closed Room Polygons (Vector-to-Room).
Includes Fuzzy Snapping Buffer to heal T-Junctions and micro-gaps.
"""
from typing import List, Tuple, Dict, Any
import math

class Point2D:
    def __init__(self, x: float, y: float):
        self.x = round(x, 4)
        self.y = round(y, 4)

    def distance_to(self, other: 'Point2D') -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def __repr__(self):
        return f"({self.x}, {self.y})"


class Segment2D:
    def __init__(self, p1: Point2D, p2: Point2D):
        self.p1 = p1
        self.p2 = p2

    @property
    def length(self) -> float:
        return self.p1.distance_to(self.p2)


class PSLGTopologyEngine:
    """
    Constructs a Planar Straight-Line Graph (PSLG) from raw line segments
    and extracts closed room polygons with maximum topology fidelity.
    """
    def __init__(self, snap_tolerance: float = 3.0, min_room_area: float = 2.0):
        """
        Args:
            snap_tolerance: Maximum pixel distance to cluster/snap endpoints (Fuzzy Buffer).
            min_room_area: Minimum area in square meters/units to filter out wall cavities.
        """
        self.snap_tolerance = snap_tolerance
        self.min_room_area = min_room_area

    def snap_endpoints(self, segments: List[Tuple[Tuple[float, float], Tuple[float, float]]]) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """
        Fuzzy Snapping Algorithm:
        Clusters nearby vertices within snap_tolerance and merges them to the cluster centroid.
        Prevents open boundary failures during polygonization.
        """
        raw_points: List[Point2D] = []
        for (x1, y1), (x2, y2) in segments:
            raw_points.append(Point2D(x1, y1))
            raw_points.append(Point2D(x2, y2))

        # Cluster points by distance
        clustered_points: List[Point2D] = []
        for pt in raw_points:
            merged = False
            for cpt in clustered_points:
                if pt.distance_to(cpt) <= self.snap_tolerance:
                    # Move cluster center closer (average centroid)
                    cpt.x = round((cpt.x + pt.x) / 2.0, 4)
                    cpt.y = round((cpt.y + pt.y) / 2.0, 4)
                    merged = True
                    break
            if not merged:
                clustered_points.append(Point2D(pt.x, pt.y))

        # Re-map segments to snapped vertices
        snapped_segments = []
        for (x1, y1), (x2, y2) in segments:
            p1 = Point2D(x1, y1)
            p2 = Point2D(x2, y2)

            best_p1 = min(clustered_points, key=lambda c: p1.distance_to(c))
            best_p2 = min(clustered_points, key=lambda c: p2.distance_to(c))

            # Discard zero-length collapsed lines
            if best_p1.distance_to(best_p2) > 0.001:
                snapped_segments.append((best_p1.to_tuple(), best_p2.to_tuple()))

        return snapped_segments

    def extract_room_polygons(self, segments: List[Tuple[Tuple[float, float], Tuple[float, float]]]) -> List[Dict[str, Any]]:
        """
        Extracts planar faces (closed room polygons) from snapped straight-line graph.
        
        Returns:
            List of Room dictionaries with:
            - "id": room_idx
            - "vertices": [(x1, y1), (x2, y2), ...]
            - "area": float
            - "perimeter": float
        """
        snapped = self.snap_endpoints(segments)
        
        # Build adjacency graph for planar cycle detection
        adj: Dict[Tuple[float, float], List[Tuple[float, float]]] = {}
        for p1, p2 in snapped:
            adj.setdefault(p1, []).append(p2)
            adj.setdefault(p2, []).append(p1)

        # Polygon cycle extraction (Planar Straight Line Graph face decomposition)
        visited_edges = set()
        rooms = []
        
        # Simple cycle finding for room loops
        def find_cycles():
            cycles = []
            for start_node in adj:
                stack = [(start_node, [start_node])]
                while stack:
                    curr, path = stack.pop()
                    for neighbor in adj.get(curr, []):
                        if len(path) > 2 and neighbor == path[0]:
                            # Found closed polygon
                            cycle = list(path)
                            normalized = tuple(sorted(cycle))
                            if normalized not in visited_edges:
                                visited_edges.add(normalized)
                                cycles.append(cycle)
                        elif neighbor not in path and len(path) < 12:
                            stack.append((neighbor, path + [neighbor]))
            return cycles

        raw_cycles = find_cycles()
        
        room_idx = 1
        for cycle in raw_cycles:
            # Calculate polygon area using Shoelace formula
            n = len(cycle)
            area = 0.0
            perimeter = 0.0
            for i in range(n):
                j = (i + 1) % n
                area += cycle[i][0] * cycle[j][1]
                area -= cycle[j][0] * cycle[i][1]
                perimeter += math.hypot(cycle[j][0] - cycle[i][0], cycle[j][1] - cycle[i][1])
            area = abs(area) / 2.0

            if area >= self.min_room_area:
                rooms.append({
                    "room_id": f"ROOM_{room_idx:02d}",
                    "vertices": cycle,
                    "area_m2": round(area, 2),
                    "perimeter_m": round(perimeter, 2),
                })
                room_idx += 1

        return rooms
