# export_ifc.py (Refactored for Advanced BIM Generation)
import os
import json
import math
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import ifcopenshell
import ifcopenshell.api

from domain.models import Room, Point, RoomKind
from pipeline.contracts import SCHEMA_VERSION, build_processing_metadata
from pipeline.paths import resolve_output_path, resolve_project_path

def _load_json(p):
    resolved_path = resolve_project_path(p)
    with open(resolved_path, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_json(p, obj):
    resolved_path = resolve_output_path(p)
    with open(resolved_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def _mm_to_m(x_mm: float) -> float:
    return float(x_mm) / 1000.0

def _px_to_m(x_px: float, px_to_mm: float) -> float:
    return (float(x_px) * float(px_to_mm)) / 1000.0

def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _create_guid():
    return ifcopenshell.guid.new()

def _add_box_rep(model, context, product, length_m, thickness_m, height_m, angle_deg, cx_m, cy_m, cz_m, is_opening=False):
    """
    IFC 엔티티(Wall, Space, Opening 등)에 사각 상자(Box) 형상을 추가합니다.
    """
    def P(x, y, z=0.0): return model.create_entity("IfcCartesianPoint", Coordinates=[float(x), float(y), float(cz_m + z)])
    def D(x, y, z=0.0): return model.create_entity("IfcDirection", DirectionRatios=[float(x), float(y), float(z)])
    axis_z = D(0.0, 0.0, 1.0)
    ang = math.radians(angle_deg)
    ref_dir = D(math.cos(ang), math.sin(ang), 0.0)

    # Local placement
    a2p3 = model.create_entity("IfcAxis2Placement3D", Location=P(cx_m, cy_m, 0), Axis=axis_z, RefDirection=ref_dir)
    product.ObjectPlacement = model.create_entity("IfcLocalPlacement", PlacementRelTo=None, RelativePlacement=a2p3)

    # Profile (2D Rectangle)
    profile = model.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=float(length_m), YDim=float(thickness_m), Position=model.create_entity("IfcAxis2Placement2D", Location=P(0,0)))
    
    # Solid (Extrusion)
    solid = model.create_entity("IfcExtrudedAreaSolid", SweptArea=profile, Position=model.create_entity("IfcAxis2Placement3D", Location=P(-length_m/2, -thickness_m/2, 0), Axis=axis_z, RefDirection=D(1,0,0)), ExtrudedDirection=axis_z, Depth=float(height_m))
    
    # Representation
    rep_id = "Body" if not is_opening else "Clearance" # 개구부 형상은 다를 수 있으나 범용적으로 Body 사용
    shape_rep = model.create_entity("IfcShapeRepresentation", ContextOfItems=context, RepresentationIdentifier="Body", RepresentationType="SweptSolid", Items=[solid])
    product.Representation = model.create_entity("IfcProductDefinitionShape", Representations=[shape_rep])

def _create_opening_in_wall(model, context, wall, width_m, height_m, thickness_m, cx_m, cy_m, cz_m, angle_deg):
    """
    벽체에 구멍(Opening)을 뚫는 IfcOpeningElement 생성 및 Boolean Voiding 처리.
    """
    opening = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcOpeningElement", name="Wall_Opening")
    
    # 벽 두께보다 살짝 두껍게(10% 정도) 파내어 확실하게 뚫리도록 함 (공차 여유)
    void_thickness = thickness_m * 1.1 
    
    _add_box_rep(model, context, opening, width_m, void_thickness, height_m, angle_deg, cx_m, cy_m, cz_m, is_opening=True)
    
    # Boolean 빼기 연산 (Wall - Opening)
    model.create_entity("IfcRelVoidsElement", GlobalId=_create_guid(), RelatingBuildingElement=wall, RelatedOpeningElement=opening)
    return opening

def _create_door_in_opening(model, context, storey, opening, width_m, height_m, thickness_m, cx_m, cy_m, cz_m, angle_deg):
    """
    구멍 뚫린 공간(IfcOpeningElement)에 IfcDoor를 배치.
    """
    door = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcDoor", name="Interior_Door")
    ifcopenshell.api.run("spatial.assign_container", model, relating_structure=storey, products=[door])
    
    _add_box_rep(model, context, door, width_m, thickness_m, height_m, angle_deg, cx_m, cy_m, cz_m)
    
    # 구멍 채우기 (Opening <- Door)
    model.create_entity("IfcRelFillsElement", GlobalId=_create_guid(), RelatingOpeningElement=opening, RelatedBuildingElement=door)
    return door

def _create_window_in_opening(model, context, storey, opening, width_m, height_m, thickness_m, cx_m, cy_m, cz_m, angle_deg):
    """
    구멍 뚫린 공간(IfcOpeningElement)에 IfcWindow를 배치.
    """
    window = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWindow", name="Exterior_Window")
    ifcopenshell.api.run("spatial.assign_container", model, relating_structure=storey, products=[window])
    
    _add_box_rep(model, context, window, width_m, thickness_m, height_m, angle_deg, cx_m, cy_m, cz_m)
    
    # 구멍 채우기 (Opening <- Window)
    model.create_entity("IfcRelFillsElement", GlobalId=_create_guid(), RelatingOpeningElement=opening, RelatedBuildingElement=window)
    return window

def build_ifc_from_multi_floor(payloads: List[dict], *, out_ifc: str):
    """
    다층 구조 기하학 정보(GeometryPayloads)로부터 정밀 BIM(IFC) 파일을 생성합니다.
    """
    out_ifc = str(resolve_output_path(out_ifc))
    model = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="CAD_SaaS_MVP_Advanced")
    ifcopenshell.api.run("unit.assign_unit", model)
    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body = ifcopenshell.api.run(
        "context.add_context", model, context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=context,
    )

    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Default Site")
    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Default Building")
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=project, products=[site])
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=site, products=[building])

    for floor_idx, payload in enumerate(payloads):
        elevation_m = float(payload.get("metadata", {}).get("elevation_m", floor_idx * 3.0))
        storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name=f"Level {floor_idx}")
        ifcopenshell.api.run("aggregate.assign_object", model, relating_object=building, products=[storey])
        storey.Elevation = elevation_m

        scale = payload.get("scale", {}) or {}
        px_to_mm = float(scale.get("pixel_to_mm", 5.0))
        
        floor_h_mm = float(payload.get("metadata", {}).get("floor_height_mm", 2400.0))
        wall_h_m = _mm_to_m(floor_h_mm)
        wall_t_m = 0.12 # Default thickness 120mm

        # 1. Spaces (방/공간)
        rooms_data = payload.get("rooms", [])
        for r in rooms_data:
            rid = r.get("id", 0)
            kind_val = r.get("kind", "unknown")
            poly = r.get("polygon", [])
            
            room_h_mm = r.get("metadata", {}).get("height", floor_h_mm)
            room_h_m = _mm_to_m(room_h_mm)

            space = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSpace", name=f"F{floor_idx}_Space_{rid}_{kind_val}")
            ifcopenshell.api.run("aggregate.assign_object", model, relating_object=storey, products=[space])
            if poly:
                xs = [float(p["x"]) for p in poly]
                ys = [float(p["y"]) for p in poly]
                if xs and ys:
                    cx_m = _px_to_m((min(xs) + max(xs)) / 2.0, px_to_mm)
                    cy_m = _px_to_m((min(ys) + max(ys)) / 2.0, px_to_mm)
                    lx_m = _px_to_m((max(xs) - min(xs)), px_to_mm)
                    ly_m = _px_to_m((max(ys) - min(ys)), px_to_mm)
                    _add_box_rep(model, body, space, lx_m, ly_m, room_h_m, 0.0, cx_m, cy_m, elevation_m)

        # 2. Walls (벽체)
        walls_data = payload.get("walls", [])
        for i, w in enumerate(walls_data):
            x1 = w.get("p1", {}).get("x", 0)
            y1 = w.get("p1", {}).get("y", 0)
            x2 = w.get("p2", {}).get("x", 0)
            y2 = w.get("p2", {}).get("y", 0)
            dx, dy = x2 - x1, y2 - y1
            length_m = _px_to_m((dx**2 + dy**2)**0.5, px_to_mm)
            if length_m < 0.01: continue
            
            angle_deg = math.degrees(math.atan2(dy, dx))
            cx_m = _px_to_m((x1+x2)/2.0, px_to_mm)
            cy_m = _px_to_m((y1+y2)/2.0, px_to_mm)
            
            # 동적 벽체 두께 적용 (JSON에 두께 정보가 있을 경우)
            current_wall_t_m = _mm_to_m(float(w.get("thickness_mm", wall_t_m * 1000)))
            
            wall = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWallStandardCase", name=f"F{floor_idx}_Wall_{i}")
            ifcopenshell.api.run("spatial.assign_container", model, relating_structure=storey, products=[wall])
            _add_box_rep(model, body, wall, length_m, current_wall_t_m, wall_h_m, angle_deg, cx_m, cy_m, elevation_m)
            
            # 3. Doors in Wall (개구부 + 문 배치)
            doors_in_wall = w.get("doors", [])
            for j, d in enumerate(doors_in_wall):
                d_w_m = _mm_to_m(float(d.get("width_mm", 900)))
                d_h_m = _mm_to_m(float(d.get("height_mm", 2100)))
                # 문은 벽 중앙(혹은 특정 오프셋)에 위치한다고 가정 (MVP)
                d_cx_m = cx_m 
                d_cy_m = cy_m
                
                opening = _create_opening_in_wall(model, body, wall, d_w_m, d_h_m, current_wall_t_m, d_cx_m, d_cy_m, elevation_m, angle_deg)
                _create_door_in_opening(model, body, storey, opening, d_w_m, d_h_m, current_wall_t_m * 0.8, d_cx_m, d_cy_m, elevation_m, angle_deg)

            # 4. Windows in Wall (개구부 + 창문 배치)
            windows_in_wall = w.get("windows", [])
            for k, win in enumerate(windows_in_wall):
                win_w_m = _mm_to_m(float(win.get("width_mm", 1200)))
                win_h_m = _mm_to_m(float(win.get("height_mm", 1200)))
                sill_h_m = _mm_to_m(float(win.get("sill_height_mm", 900)))
                
                win_cx_m = cx_m
                win_cy_m = cy_m
                win_cz_m = elevation_m + sill_h_m # 창문은 바닥에서 sill_height만큼 떠있음
                
                opening = _create_opening_in_wall(model, body, wall, win_w_m, win_h_m, current_wall_t_m, win_cx_m, win_cy_m, win_cz_m, angle_deg)
                _create_window_in_opening(model, body, storey, opening, win_w_m, win_h_m, current_wall_t_m * 0.5, win_cx_m, win_cy_m, win_cz_m, angle_deg)

    model.write(out_ifc)

# 단일층 하위호환 래퍼
def build_ifc_from_meta(payload: dict, *, out_ifc: str, out_meta: str):
    build_ifc_from_multi_floor([payload], out_ifc=out_ifc)
    out_meta_path = str(resolve_output_path(out_meta))
    _write_json(
        out_meta_path,
        {
            "schema_version": SCHEMA_VERSION,
            "kind": "ifc_export_metadata",
            "generated_at": _now_iso(),
            "ifc": os.path.basename(out_ifc),
            "counts": {"spaces": len(payload.get("rooms", [])), "walls": len(payload.get("walls", []))},
            "processing": build_processing_metadata("export_ifc"),
        },
    )

def main():
    pass

if __name__ == "__main__":
    main()
