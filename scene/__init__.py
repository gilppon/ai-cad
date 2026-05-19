# scene package — Incident Semantics Layer
from .serializer import leak_case_to_dict, dict_to_leak_case, save_leak_case, load_leak_case
from .incident_mapper import map_incident_to_scene, validate_incident_mapping, compute_damage_spread
from .annotations import attach_photo, attach_note, list_annotations_for_room, remove_annotation

__all__ = [
    "leak_case_to_dict",
    "dict_to_leak_case",
    "save_leak_case",
    "load_leak_case",
    "map_incident_to_scene",
    "validate_incident_mapping",
    "compute_damage_spread",
    "attach_photo",
    "attach_note",
    "list_annotations_for_room",
    "remove_annotation",
]
