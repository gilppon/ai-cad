import uuid
from typing import Dict, Any, List, Optional, Tuple
from domain.models import RoomKind
from correction.patch import CorrectionPatch

def _find_room(payload: Dict[str, Any], room_id: int) -> Optional[Dict[str, Any]]:
    for r in payload.get("rooms", []):
        if r.get("id") == room_id:
            return r
    return None

def change_room_type(payload: Dict[str, Any], room_id: int, new_kind: RoomKind, author: str = "operator") -> Optional[CorrectionPatch]:
    room = _find_room(payload, room_id)
    if not room:
        return None
    
    before_kind = room.get("kind", "UNKNOWN")
    new_kind_str = new_kind.value if hasattr(new_kind, "value") else str(new_kind)
    
    if before_kind == new_kind_str:
        return None
        
    patch = CorrectionPatch(
        id=str(uuid.uuid4()),
        operation="change_room_type",
        target_id=room_id,
        before={"kind": before_kind},
        after={"kind": new_kind_str},
        author=author
    )
    
    room["kind"] = new_kind_str
    return patch

def move_wall(payload: Dict[str, Any], wall_id: int, new_p1: Dict[str, float], new_p2: Dict[str, float], author: str = "operator") -> Optional[CorrectionPatch]:
    walls = payload.get("walls", [])
    if wall_id < 0 or wall_id >= len(walls):
        return None
        
    wall = walls[wall_id]
    
    if isinstance(wall, dict):
        before = {
            "p1": wall.get("p1", {}),
            "p2": wall.get("p2", {})
        }
        after = {
            "p1": new_p1,
            "p2": new_p2
        }
        wall["p1"] = new_p1
        wall["p2"] = new_p2
    elif isinstance(wall, (list, tuple)) and len(wall) >= 4:
        before = {"x1": wall[0], "y1": wall[1], "x2": wall[2], "y2": wall[3]}
        after = {"x1": new_p1["x"], "y1": new_p1["y"], "x2": new_p2["x"], "y2": new_p2["y"]}
        wall[0], wall[1] = new_p1["x"], new_p1["y"]
        wall[2], wall[3] = new_p2["x"], new_p2["y"]
    else:
        return None

    patch = CorrectionPatch(
        id=str(uuid.uuid4()),
        operation="move_wall",
        target_id=wall_id,
        before=before,
        after=after,
        author=author
    )
    return patch
