"""
IFC (Industry Foundation Classes) Exporter Worker Script.
Executed inside an isolated Sandbox subprocess to protect against C-API / IfcOpenShell memory leaks.
"""
import argparse
import json
import sys
import os

def export_ifc_file(geometry_data: dict, output_filepath: str) -> dict:
    """
    Generates an IFC4 Building Information Model (BIM) standard output.
    """
    elements = geometry_data.get("primitives", [])
    rooms = geometry_data.get("rooms", [])

    ifc_lines = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');",
        "FILE_NAME('building.ifc','2026-08-18',('Kodari Legion'),('BIM Studio'),'IfcOpenShell','IFC4','None');",
        "FILE_SCHEMA(('IFC4'));",
        "ENDSEC;",
        "DATA;",
        "#1=IFCPROJECT('2vM$Y0bTH6xvhz9qVwY12a',#2,'AI-CAD Project',$,$,$,$,(#10),#11);",
        "#2=IFCOWNERHISTORY(#3,#4,$,.ADDED.,$,$,$,$);",
        "#3=IFCPERSONANDORGANIZATION(#5,#6,$);",
        "#4=IFCAPPLICATION(#6,'2026.1','AI-CAD System','AICAD');",
        "#5=IFCPERSON('KODARI','Dev Manager',$,$,$,$,$,$);",
        "#6=IFCORGANIZATION($,'Kodari Engineering Legion',$,$,$);",
    ]

    entity_id = 20
    for idx, r in enumerate(rooms):
        room_id = r.get("room_id", f"SPACE_{idx}")
        area = r.get("area_m2", 15.0)
        ifc_lines.append(f"#{entity_id}=IFCSPACE('000{idx}SpaceGUID',#2,'{room_id}','Living Space',$,$,$,$,.ELEMENT.,.INTERNAL.,{area:.2f});")
        entity_id += 1

    ifc_lines.extend([
        "ENDSEC;",
        "END-ISO-10303-21;\n"
    ])

    with open(output_filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(ifc_lines))

    return {
        "success": True,
        "format": "IFC4",
        "exported_file": output_filepath,
        "space_count": len(rooms),
        "file_size_bytes": os.path.getsize(output_filepath)
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Isolated IFC Exporter Worker")
    parser.add_argument("--input", required=True, help="Input JSON payload file")
    parser.add_argument("--output", required=True, help="Output JSON result file")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            payload = json.load(f)

        target_ifc_path = payload.get("target_path", "exported_building.ifc")
        result = export_ifc_file(payload, target_ifc_path)

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f)
        sys.exit(0)
    except Exception as err:
        error_res = {"success": False, "error": str(err)}
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(error_res, f)
        sys.exit(1)
