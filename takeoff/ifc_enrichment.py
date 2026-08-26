"""IFC 수량 속성세트(Pset) 부착 — SP3/Q-2.

parser/export_ifc.py가 생성한 IFC4 모델의 IfcSpace/IfcWall에
수량산출 결과를 IfcPropertySet으로 역주입하여, BIM 모델 자체가 견적 원장이 되게 한다.
(ISO 19650 정보 일관성: 수량은 IFC 엔티티명 F{i}_Space_{rid}_{kind} / F{i}_Wall_{i}로 정합 매칭)

검증 계약: 부착 후 ifcopenshell로 재파싱하여 Pset 조회가 가능해야 한다.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

PSET_NAME = "Pset_QuantityTakeoff_Kodari"


def _space_name(floor_idx: int, room_id: Any, kind: str) -> str:
    return f"F{floor_idx}_Space_{room_id}_{kind}"


def _wall_name(floor_idx: int, wall_id: Any) -> str:
    return f"F{floor_idx}_Wall_{wall_id}"


def enrich_ifc_with_quantities(ifc_path: str | Path,
                               payloads: List[Dict[str, Any]],
                               quantity_lines_by_floor: List[List[Any]]) -> Dict[str, int]:
    """
    다층 payload와 각 층의 수량 라인을 받아 IFC에 Pset을 부착한다.

    quantity_lines_by_floor[f] 의 각 라인은 takeoff.quantities.QuantityLine.
    반환: {"spaces_tagged": int, "walls_tagged": int, "psets_written": int}
    """
    import ifcopenshell
    import ifcopenshell.api

    model = ifcopenshell.open(str(ifc_path))

    spaces = {s.Name or "": s for s in model.by_type("IfcSpace")}
    walls = {w.Name or "": w for w in model.by_type("IfcWallStandardCase")}

    spaces_tagged = walls_tagged = psets_written = 0

    def attach(element, props: Dict[str, str]) -> bool:
        nonlocal psets_written
        try:
            pset = ifcopenshell.api.run(
                "pset.add_pset", model,
                product=element, name=PSET_NAME,
            )
            ifcopenshell.api.run(
                "pset.edit_pset", model, pset=pset,
                properties={k: str(v) for k, v in props.items()},
            )
            psets_written += 1
            return True
        except Exception as e:
            logger.warning(f"[IFCEnrich] Failed to attach pset to {element.Name}: {e}")
            return False

    for floor_idx, lines in enumerate(quantity_lines_by_floor):
        # 룸별 집계
        room_qty: Dict[Any, Dict[str, float]] = {}
        wall_qty: Dict[Any, Dict[str, float]] = {}
        for l in lines:
            bucket = room_qty if l.source_kind == "room" else wall_qty if l.source_kind == "wall" else None
            if bucket is None:
                continue
            entry = bucket.setdefault(l.source_ref, {})
            entry[l.basis] = entry.get(l.basis, 0.0) + l.quantity

        for rid, qty in room_qty.items():
            kind_hint = ""
            for l in quantity_lines_by_floor[floor_idx]:
                if l.source_kind == "room" and l.source_ref == rid and l.part:
                    kind_hint = l.part
                    break
            target = spaces.get(_space_name(floor_idx, rid, kind_hint))
            if target is None:
                logger.debug(f"[IFCEnrich] Space not found by name: {_space_name(floor_idx, rid, kind_hint)}")
                continue
            props = {
                "Basis_FloorArea_m2": f"{qty.get('FLOOR-AREA', 0.0):.3f}",
                "Basis_CeilArea_m2": f"{qty.get('CEIL-AREA', 0.0):.3f}",
                "UnitPriceRef": f"{rid}:{kind_hint}",
            }
            if attach(target, props):
                spaces_tagged += 1

        for wid, qty in wall_qty.items():
            target = walls.get(_wall_name(floor_idx, wid))
            if target is None:
                logger.debug(f"[IFCEnrich] Wall not found by name: {_wall_name(floor_idx, wid)}")
                continue
            props = {
                "Basis_WallLength_m": f"{qty.get('WALL-LENGTH', 0.0):.3f}",
                "Basis_WallArea_m2": f"{qty.get('WALL-AREA', 0.0):.3f}",
            }
            if attach(target, props):
                walls_tagged += 1

    model.write(str(ifc_path))
    result = {
        "spaces_tagged": spaces_tagged,
        "walls_tagged": walls_tagged,
        "psets_written": psets_written,
    }
    logger.info(f"[IFCEnrich] {result}")
    return result


def read_back_psets(ifc_path: str | Path) -> Dict[str, Dict[str, str]]:
    """부착 검증용 - Pset_QuantityTakeoff_Kodari가 붙은 엔티티의 속성을 재파싱해 반환."""
    import ifcopenshell
    import ifcopenshell.util.element

    model = ifcopenshell.open(str(ifc_path))
    out: Dict[str, Dict[str, str]] = {}
    for element in list(model.by_type("IfcSpace")) + list(model.by_type("IfcWallStandardCase")):
        psets = ifcopenshell.util.element.get_psets(element)
        data = psets.get(PSET_NAME)
        if data:
            out[element.Name or "?"] = {
                k: str(v) for k, v in data.items() if k not in ("id",)
            }
    return out
