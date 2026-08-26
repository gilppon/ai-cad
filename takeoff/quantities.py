"""BIM 지오메트리 → 물리 수량 산출 엔진 (SP3/Q-1).

설계 원칙 (code_remediation_plan_v1.0 §3.2):
  - 수량은 가격과 독립된 '물리량'으로만 산출한다
  - 모든 라인은 원천(room_id / wall_id)으로 역추적 가능해야 한다
  - 면적 합계 검증: 룸 면적 총합 vs 산출 면적 편차 > 1% 시 경고

스케일은 payload["scale"]["pixel_to_mm"]를 SSOT로 사용하며,
부재 시 compliance.extractor.resolve_px_to_m와 동일한 레거시 폴백(0.01)을 적용한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

from takeoff.overlap_resolver import resolve_wall_overlaps

logger = logging.getLogger(__name__)

# SP4/H-5: 레거시 폴백 스케일의 단일 정의는 core.units로 수렴
from core.units import DEFAULT_PX_TO_M, pixel_to_mm_to_px_to_m

# 물리 수량 기준 코드 (가격과 분리된 순수 물리량)
FLOOR_AREA = "FLOOR-AREA"
CEIL_AREA = "CEIL-AREA"
WALL_AREA = "WALL-AREA"
WALL_LENGTH = "WALL-LENGTH"
ROOM_COUNT = "ROOM-COUNT"
DOOR_COUNT = "DOOR-COUNT"
WINDOW_COUNT = "WINDOW-COUNT"


@dataclass
class QuantityLine:
    basis: str                 # 물리량 기준 코드 (FLOOR-AREA 등)
    unit: str                  # m² / m / 式
    quantity: float
    source_kind: str           # room | wall | opening | floor
    source_ref: Any            # room_id / wall_id / opening id
    part: str = ""             # RoomKind 값 (발코니·욕실 등 부위별 필터용)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _resolve_px_to_m(payload: Dict[str, Any]) -> float:
    scale = payload.get("scale") or {}
    px_to_mm = scale.get("pixel_to_mm")
    if px_to_mm:
        try:
            return pixel_to_mm_to_px_to_m(float(px_to_mm))
        except (TypeError, ValueError):
            pass
    logger.warning("[Takeoff] No scale info in payload - using legacy default %.4f m/px", DEFAULT_PX_TO_M)
    return DEFAULT_PX_TO_M


def _polygon_area_px(poly: List[Dict[str, float]]) -> float:
    """신발끈 공식으로 다각형 면적(px²) 계산."""
    if not poly or len(poly) < 3:
        return 0.0
    s = 0.0
    n = len(poly)
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        s += float(p1["x"]) * float(p2["y"]) - float(p2["x"]) * float(p1["y"])
    return abs(s) / 2.0


def _count_openings(compliance_doc: Dict[str, Any] | None) -> List[QuantityLine]:
    lines: List[QuantityLine] = []
    if not compliance_doc:
        return lines
    counts = {"DOOR": 0, "WINDOW": 0}
    for op in compliance_doc.get("openings", []):
        kind = str(op.get("kind", "")).upper()
        if kind in counts:
            counts[kind] += 1
    if counts["DOOR"]:
        lines.append(QuantityLine(DOOR_COUNT, "式", float(counts["DOOR"]), "opening", "doors",
                                  meta={"source": "page_compliance.json"}))
    if counts["WINDOW"]:
        lines.append(QuantityLine(WINDOW_COUNT, "式", float(counts["WINDOW"]), "opening", "windows",
                                  meta={"source": "page_compliance.json"}))
    return lines


def takeoff_from_payload(payload: Dict[str, Any],
                         compliance_doc: Dict[str, Any] | None = None) -> List[QuantityLine]:
    """
    단층 GeometryPayload에서 물리 수량 라인을 산출한다.

    반환 라인의 역추적 계약:
      - FLOOR-AREA/CEIL-AREA/ROOM-COUNT → source_kind="room", source_ref=room id
      - WALL-AREA/WALL-LENGTH          → source_kind="wall", source_ref=wall id
    """
    px_to_m = _resolve_px_to_m(payload)

    rooms = payload.get("rooms", []) or []
    walls = payload.get("walls", []) or []
    metadata = payload.get("metadata") or {}
    floor_height_mm = float(metadata.get("floor_height_mm", 2400.0))

    lines: List[QuantityLine] = []

    # --- 룸 기반 수량 (바닥/천장 면적, 호실 수) ---
    for r in rooms:
        rid = r.get("id", "?")
        part = str(r.get("kind", "unknown")).lower()

        area_px2 = float(r.get("area_px2", 0.0) or 0.0)
        if area_px2 <= 0 and r.get("polygon"):
            area_px2 = _polygon_area_px(r["polygon"])
        area_m2 = area_px2 * (px_to_m ** 2)
        if area_m2 > 0:
            lines.append(QuantityLine(FLOOR_AREA, "m²", round(area_m2, 3), "room", rid, part))
            lines.append(QuantityLine(CEIL_AREA, "m²", round(area_m2, 3), "room", rid, part))

        lines.append(QuantityLine(ROOM_COUNT, "式", 1.0, "room", rid, part))

    # --- 벽 기반 수량 (包絡処리 적용) ---
    resolved_walls = resolve_wall_overlaps(walls)
    for rw in resolved_walls:
        length_m = rw.length_px * px_to_m
        thickness_m = rw.thickness_px * px_to_m
        wall_height_m = floor_height_mm / 1000.0
        if length_m <= 0:
            continue
        lines.append(QuantityLine(
            WALL_LENGTH, "m", round(length_m, 3), "wall", rw.wall_id,
            meta={"corner_deductions": rw.corner_deductions_px},
        ))
        wall_area = length_m * wall_height_m  # 두께는 면적 산출에서 제외(표면적 기준)
        if wall_area > 0:
            lines.append(QuantityLine(
                WALL_AREA, "m²", round(wall_area, 3), "wall", rw.wall_id,
                meta={"height_m": wall_height_m, "thickness_m": round(thickness_m, 4)},
            ))

    # --- 개구부 수량 (컴플라이언스 문서에 존재할 때만) ---
    lines.extend(_count_openings(compliance_doc))

    # --- 정합성 검증: 바닥 면적 총합 vs 룸 면적 총합 (±1% 허용) ---
    takeoff_floor_total = sum(l.quantity for l in lines if l.basis == FLOOR_AREA)
    declared_total = sum(float(r.get("area_m2", 0.0) or 0.0) for r in rooms)
    if declared_total > 0:
        deviation = abs(takeoff_floor_total - declared_total) / declared_total
        if deviation > 0.01:
            logger.warning(
                "[Takeoff] Floor area mismatch: takeoff %.3f m² vs declared %.3f m² (%.2f%% off)",
                takeoff_floor_total, declared_total, deviation * 100,
            )

    logger.info(f"[Takeoff] {len(lines)} quantity lines from "
                f"{len(rooms)} rooms / {len(walls)} walls")
    return lines


def summarize_by_basis(lines: List[QuantityLine]) -> Dict[str, float]:
    """기준별 총량 집계 (작업항목 조인용)."""
    totals: Dict[str, float] = {}
    for l in lines:
        totals[l.basis] = totals.get(l.basis, 0.0) + l.quantity
    return {k: round(v, 3) for k, v in totals.items()}
