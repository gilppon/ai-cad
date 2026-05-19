# correction package init
from .patch import CorrectionPatch, CorrectionSession
from .operations import (
    change_room_type, move_wall, add_wall, delete_wall,
    merge_rooms, split_room, move_opening,
    place_leak_source, paint_damage_zone, delete_room,
)
from .rebuild import rebuild_after_correction
from .history import save_session, load_session, list_sessions, get_correction_stats

__all__ = [
    "CorrectionPatch",
    "CorrectionSession",
    "change_room_type",
    "move_wall",
    "add_wall",
    "delete_wall",
    "merge_rooms",
    "split_room",
    "move_opening",
    "place_leak_source",
    "paint_damage_zone",
    "delete_room",
    "rebuild_after_correction",
    "save_session",
    "load_session",
    "list_sessions",
    "get_correction_stats",
]
