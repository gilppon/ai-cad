from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from domain.models import LeakCase
from pipeline.contracts import validate_geometry_payload, validate_export_metadata
from pipeline.paths import resolve_output_path, resolve_project_path
from harness.circuit_breaker import circuit_breaker

class PipelineEngine:
    """
    Main orchestration engine for the CAD SaaS MVP pipeline.
    """
    def __init__(self, project_id: str = "default"):
        self.project_id = project_id
        from pipeline.paths import OUTPUT_ROOT
        self.output_dir = str(OUTPUT_ROOT / "projects" / project_id)
        os.makedirs(self.output_dir, exist_ok=True)

    @circuit_breaker(failure_threshold=3, recovery_timeout=60)
    def process_pdf(self, pdf_path: str, page_index: int = 0) -> Dict[str, Any]:
        """
        Full pipeline: PDF -> Room Detection -> Geometry -> STEP -> IFC
        """
        print(f"[*] Processing PDF: {pdf_path} (Page: {page_index})")
        
        # 1. Room Detection
        # (Mocking room_detect for now, but in real case we call parser.room_detect)
        try:
            from parser.room_detect import detect_rooms
            room_result = detect_rooms(pdf_path, page=page_index)
        except ImportError:
            print("[!] room_detect not found, using dummy result.")
            room_result = self._get_dummy_room_result()

        # 2. Export Geometry JSON
        from parser.room_export import save_rooms_json
        rooms_json_name = f"page{page_index}_rooms.json"
        rooms_json_path = os.path.join(self.output_dir, rooms_json_name)
        
        save_rooms_json(
            room_result,
            rooms_json_path,
            page=page_index,
            pixel_to_mm=5.0 # Standard scale
        )
        
        with open(rooms_json_path, "r", encoding="utf-8") as f:
            rooms_payload = json.load(f)
        
        validate_geometry_payload(rooms_payload)

        # 3. IFC Export
        from parser.export_ifc import build_ifc_from_meta
        ifc_name = f"page{page_index}_result.ifc"
        ifc_meta_name = f"page{page_index}_result.ifc.meta.json"
        ifc_path = os.path.join(self.output_dir, ifc_name)
        ifc_meta_path = os.path.join(self.output_dir, ifc_meta_name)
        
        # IFC export currently expects a 'scene_export_metadata' kind, 
        # but build_ifc_from_meta is flexible. 
        # We might need to adapt it if it strictly expects wall/door lists.
        build_ifc_from_meta(rooms_payload, out_ifc=ifc_path, out_meta=ifc_meta_path)

        return {
            "status": "success",
            "project_id": self.project_id,
            "artifacts": {
                "rooms_json": rooms_json_path,
                "ifc": ifc_path,
                "ifc_meta": ifc_meta_path
            }
        }

    def _get_dummy_room_result(self) -> Any:
        class Dummy:
            width = 1000
            height = 1000
            rooms = []
            debug = {}
        return Dummy()

if __name__ == "__main__":
    engine = PipelineEngine(project_id="test_run")
    # For testing, we might not have a real PDF, so we'll just test the flow
    # result = engine.process_pdf("sample.pdf")
    # print(result)
