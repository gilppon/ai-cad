# scene/annotations.py — 사진·메모·노트 앵커링 시스템
from __future__ import annotations

from typing import List, Optional

from domain.models import (
    LeakCase, IncidentAnnotation, Point, _now_iso,
)


def _next_annotation_id(case: LeakCase) -> int:
    """기존 어노테이션의 최대 id + 1 반환"""
    if not case.annotations:
        return 1
    return max(a.id for a in case.annotations) + 1


def attach_photo(
    case: LeakCase,
    photo_path: str,
    anchor: Point,
    room_id: Optional[int] = None,
    text: str = "",
) -> IncidentAnnotation:
    """
    사진을 좌표 및 room에 앵커링하여 LeakCase에 추가.

    Args:
        case: 대상 LeakCase
        photo_path: 사진 파일 경로 (상대 or 절대)
        anchor: 앵커 좌표 (도면 좌표계)
        room_id: 연결할 room ID (None이면 나중에 mapper가 자동 바인딩)
        text: 사진 설명 텍스트

    Returns:
        생성된 IncidentAnnotation
    """
    ann = IncidentAnnotation(
        id=_next_annotation_id(case),
        anchor_point=anchor,
        anchor_room_id=room_id,
        text=text or f"Photo: {photo_path}",
        category="photo",
        attached_photo=photo_path,
        created_at=_now_iso(),
    )
    case.annotations.append(ann)
    case.bump_version()
    return ann


def attach_note(
    case: LeakCase,
    text: str,
    anchor: Point,
    room_id: Optional[int] = None,
    category: str = "note",
) -> IncidentAnnotation:
    """
    텍스트 메모를 좌표 및 room에 앵커링하여 LeakCase에 추가.

    Args:
        case: 대상 LeakCase
        text: 메모 내용
        anchor: 앵커 좌표 (도면 좌표계)
        room_id: 연결할 room ID
        category: 카테고리 (note, warning, inspection, etc.)

    Returns:
        생성된 IncidentAnnotation
    """
    ann = IncidentAnnotation(
        id=_next_annotation_id(case),
        anchor_point=anchor,
        anchor_room_id=room_id,
        text=text,
        category=category,
        attached_photo=None,
        created_at=_now_iso(),
    )
    case.annotations.append(ann)
    case.bump_version()
    return ann


def list_annotations_for_room(
    case: LeakCase,
    room_id: int,
) -> List[IncidentAnnotation]:
    """특정 room에 앵커링된 모든 어노테이션 조회"""
    return [a for a in case.annotations if a.anchor_room_id == room_id]


def remove_annotation(
    case: LeakCase,
    annotation_id: int,
) -> bool:
    """
    ID로 어노테이션 삭제.

    Returns:
        True if found and removed, False otherwise.
    """
    for i, ann in enumerate(case.annotations):
        if ann.id == annotation_id:
            case.annotations.pop(i)
            case.bump_version()
            return True
    return False
