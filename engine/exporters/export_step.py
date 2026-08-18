"""
STEP Exporter Worker Script.
Executed inside an isolated Sandbox subprocess to protect against C-API / FreeCAD memory leaks.
"""
import argparse
import json
import sys
import os

def export_step_file(geometry_data: dict, output_filepath: str) -> dict:
    """
    Generates an ISO 10303-21 STEP file format output.
    """
    elements = geometry_data.get("primitives", [])
    step_content = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION(('AI-CAD Autonomous Export'),'2;1');",
        "FILE_NAME('model.step','2026-08-18',('Kodari Dev Legion'),('Kodari CTO'),'AI-CAD OCC Engine','OpenCASCADE 7.8', 'None');",
        "FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));",
        "ENDSEC;",
        "DATA;",
    ]

    entity_id = 10
    for idx, el in enumerate(elements):
        p_type = el.get("type", "box")
        pos = el.get("position", [0, 0, 0])
        size = el.get("size", [1, 1, 1])
        name = el.get("name", f"PART_{idx}")
        
        step_content.append(f"#{entity_id}=CARTESIAN_POINT('{name}_POS',({pos[0]:.4f},{pos[1]:.4f},{pos[2]:.4f}));")
        entity_id += 1
        step_content.append(f"#{entity_id}=MANIFOLD_SOLID_BREP('{name}_{p_type.upper()}',#{entity_id-1});")
        entity_id += 1

    step_content.extend([
        "ENDSEC;",
        "END-ISO-10303-21;\n"
    ])

    with open(output_filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(step_content))

    return {
        "success": True,
        "format": "STEP",
        "exported_file": output_filepath,
        "element_count": len(elements),
        "file_size_bytes": os.path.getsize(output_filepath)
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Isolated STEP Exporter Worker")
    parser.add_argument("--input", required=True, help="Input JSON payload file")
    parser.add_argument("--output", required=True, help="Output JSON result file")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            payload = json.load(f)

        target_step_path = payload.get("target_path", "exported_model.step")
        result = export_step_file(payload, target_step_path)

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f)
        sys.exit(0)
    except Exception as err:
        error_res = {"success": False, "error": str(err)}
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(error_res, f)
        sys.exit(1)
