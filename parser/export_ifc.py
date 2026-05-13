# export_ifc.py (Refactored for Domain Models)
import os
import json
import math
import traceback
from datetime import datetime
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
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def build_ifc_from_meta(payload: dict, *, out_ifc: str, out_meta: str):
    """
    Builds an IFC file from a GeometryPayload.
    """
    out_ifc = str(resolve_output_path(out_ifc))
    out_meta = str(resolve_output_path(out_meta))

    model = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="CAD_SaaS_MVP")

    # Units (SI meters)
    ifcopenshell.api.run("unit.assign_unit", model)

    # Contexts
    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body = ifcopenshell.api.run(
        "context.add_context",
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )

    # Site/Building/Storey
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Default Site")
    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Default Building")
    storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Level 0")

    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=project, products=[site])
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=site, products=[building])
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=building, products=[storey])

    scale = payload.get("scale", {}) or {}
    px_to_mm = float(scale.get("pixel_to_mm", 5.0))
    
    wall_h_mm = 2400.0 # Default height
    wall_h_m = _mm_to_m(wall_h_mm)
    wall_t_m = _mm_to_m(120.0)

    def P(x, y, z=0.0):
        return model.create_entity("IfcCartesianPoint", Coordinates=[float(x), float(y), float(z)])

    def D(x, y, z=0.0):
        return model.create_entity("IfcDirection", DirectionRatios=[float(x), float(y), float(z)])

    axis_z = D(0.0, 0.0, 1.0)

    def add_box_representation(product, *, length_m, thickness_m, height_m, angle_deg, center_x_m, center_y_m):
        ang = math.radians(float(angle_deg))
        ref_dir = D(math.cos(ang), math.sin(ang), 0.0)

        a2p3 = model.create_entity(
            "IfcAxis2Placement3D",
            Location=P(center_x_m, center_y_m, 0.0),
            Axis=axis_z,
            RefDirection=ref_dir,
        )
        product.ObjectPlacement = model.create_entity("IfcLocalPlacement", PlacementRelTo=None, RelativePlacement=a2p3)

        a2p2 = model.create_entity("IfcAxis2Placement2D", Location=P(0.0, 0.0, 0.0))
        profile = model.create_entity(
            "IfcRectangleProfileDef",
            ProfileType="AREA",
            XDim=float(length_m),
            YDim=float(thickness_m),
            Position=a2p2,
        )

        solid_pos = model.create_entity(
            "IfcAxis2Placement3D",
            Location=P(-float(length_m) / 2.0, -float(thickness_m) / 2.0, 0.0),
            Axis=axis_z,
            RefDirection=D(1.0, 0.0, 0.0),
        )
        solid = model.create_entity(
            "IfcExtrudedAreaSolid",
            SweptArea=profile,
            Position=solid_pos,
            ExtrudedDirection=axis_z,
            Depth=float(height_m),
        )

        shape_rep = model.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=body,
            RepresentationIdentifier="Body",
            RepresentationType="SweptSolid",
            Items=[solid],
        )
        product.Representation = model.create_entity("IfcProductDefinitionShape", Representations=[shape_rep])

    # Spaces
    rooms_data = payload.get("rooms", [])
    space_entities = []
    for r in rooms_data:
        rid = r.get("id", 0)
        kind_val = r.get("kind", "unknown")
        poly = r.get("polygon", [])

        space = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSpace", name=f"Space_{rid}_{kind_val}")
        ifcopenshell.api.run("aggregate.assign_object", model, relating_object=storey, products=[space])

        if poly:
            xs = [float(p["x"]) for p in poly]
            ys = [float(p["y"]) for p in poly]
            if xs and ys:
                minx, maxx = min(xs), max(xs)
                miny, maxy = min(ys), max(ys)
                cx_m = _px_to_m((minx + maxx) / 2.0, px_to_mm)
                cy_m = _px_to_m((miny + maxy) / 2.0, px_to_mm)
                lx_m = _px_to_m((maxx - minx), px_to_mm)
                ly_m = _px_to_m((maxy - miny), px_to_mm)

                add_box_representation(
                    space,
                    length_m=max(lx_m, 0.1),
                    thickness_m=max(ly_m, 0.1),
                    height_m=wall_h_m,
                    angle_deg=0.0,
                    center_x_m=cx_m,
                    center_y_m=cy_m,
                )
        space_entities.append(space)

    # Walls (if present in payload)
    walls_data = payload.get("walls", [])
    for i, w in enumerate(walls_data):
        # Handle both list format and dict format
        if isinstance(w, (list, tuple)) and len(w) >= 4:
            x1, y1, x2, y2 = w[:4]
            wid = i
        else:
            x1 = w.get("x1_px", w.get("p1", {}).get("x", 0))
            y1 = w.get("y1_px", w.get("p1", {}).get("y", 0))
            x2 = w.get("x2_px", w.get("p2", {}).get("x", 0))
            y2 = w.get("y2_px", w.get("p2", {}).get("y", 0))
            wid = w.get("id", i)

        dx = x2 - x1
        dy = y2 - y1
        length_m = _px_to_m((dx * dx + dy * dy) ** 0.5, px_to_mm)
        if length_m <= 1e-6: continue

        angle_deg = math.degrees(math.atan2(dy, dx))
        cx_m = _px_to_m((x1 + x2) / 2.0, px_to_mm)
        cy_m = _px_to_m((y1 + y2) / 2.0, px_to_mm)

        wall = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWallStandardCase", name=f"Wall_{wid}")
        ifcopenshell.api.run("spatial.assign_container", model, relating_structure=storey, products=[wall])

        add_box_representation(
            wall,
            length_m=length_m,
            thickness_m=wall_t_m,
            height_m=wall_h_m,
            angle_deg=angle_deg,
            center_x_m=cx_m,
            center_y_m=cy_m,
        )

    model.write(out_ifc)

    # Save meta
    _write_json(
        out_meta,
        {
            "schema_version": SCHEMA_VERSION,
            "kind": "ifc_export_metadata",
            "generated_at": _now_iso(),
            "ifc": os.path.basename(out_ifc),
            "counts": {"spaces": len(space_entities), "walls": len(walls_data)},
            "processing": build_processing_metadata("export_ifc"),
        },
    )

def main():
    # CLI entry point if needed
    pass

if __name__ == "__main__":
    main()
