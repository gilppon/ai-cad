from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from domain.models import LeakCase
from pipeline.contracts import validate_geometry_payload, validate_export_metadata
from core.units import RASTER_PIXEL_TO_MM
from pipeline.paths import resolve_output_path, resolve_project_path
from harness.circuit_breaker import circuit_breaker
import fitz
from parser.text_extract import extract_text_from_page, find_room_height

import logging

logger = logging.getLogger(__name__)

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
    def process_document(self, pdf_path: str) -> Dict[str, Any]:
        """
        Processes a multi-page PDF and aggregates all floors into a single IFC.
        """
        logger.info(f"[*] Starting multi-page processing: {pdf_path}")
        from parser.pdf_type import detect_pdf_type
        pdf_info = detect_pdf_type(pdf_path)
        page_count = pdf_info["metadata"]["page_count"]
        pdf_type = pdf_info["pdf_type"]
        
        all_floor_payloads = []
        
        for i in range(page_count):
            logger.info(f"[*] --- Processing Page {i+1}/{page_count} ---")
            payload = self._extract_page_geometry(pdf_path, i, pdf_type)
            if payload:
                all_floor_payloads.append(payload)
        
        if not all_floor_payloads:
            return {"status": "error", "message": "No geometry extracted from any page."}

        # 3. Aggregated IFC Export
        from parser.export_ifc import build_ifc_from_multi_floor
        ifc_name = "full_project.ifc"
        ifc_path = os.path.join(self.output_dir, ifc_name)
        
        build_ifc_from_multi_floor(all_floor_payloads, out_ifc=ifc_path)

        rooms_json_paths = [os.path.join(self.output_dir, f"page{i}_rooms.json") for i in range(page_count)]
        compliance_paths = [os.path.join(self.output_dir, f"page{i}_compliance.json") for i in range(page_count)]
        
        return {
            "status": "success",
            "project_id": self.project_id,
            "page_count": page_count,
            "artifacts": {
                "ifc": ifc_path,
                "compliance": compliance_paths[0] if page_count == 1 else compliance_paths,
                "rooms_json": rooms_json_paths[0] if page_count == 1 else rooms_json_paths,
                "all_compliance": compliance_paths,
                "all_rooms_json": rooms_json_paths
            }
        }

    def _extract_page_geometry(self, pdf_path: str, page_index: int, pdf_type: str) -> Optional[Dict[str, Any]]:
        """
        Extracts geometry payload for a single page.
        """
        rooms_json_name = f"page{page_index}_rooms.json"
        rooms_json_path = os.path.join(self.output_dir, rooms_json_name)

        if pdf_type == "vector" or pdf_type == "auto":
             # If pdf_type is auto, we re-detect for the page or assume it's detected already
             if pdf_type == "auto":
                 from parser.pdf_type import detect_pdf_type
                 pdf_info = detect_pdf_type(pdf_path)
                 pdf_type = pdf_info["pdf_type"]

        if pdf_type == "vector":
            from parser.pdf_vector import extract_vector_geometry
            payload = extract_vector_geometry(pdf_path, page_index=page_index)
        else:
            try:
                from parser.room_detect import detect_rooms
                room_result = detect_rooms(pdf_path, page=page_index)
                from parser.room_export import save_rooms_json
                save_rooms_json(room_result, rooms_json_path, page=page_index, pixel_to_mm=RASTER_PIXEL_TO_MM)
                with open(rooms_json_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception as e:
                logger.error(f"[!] Error on page {page_index}: {e}")
                return None

        validate_geometry_payload(payload)
        
        # Structure Integrity Check
        from harness.structure import validate_structure
        if not validate_structure(payload):
            logger.error(f"[!] Structural validation failed for page {page_index}")
            # We could raise an error or just flag it in metadata
            payload["metadata"] = payload.get("metadata", {})
            payload["metadata"]["integrity_warning"] = True

        # 4. PDF Text Extraction (for room heights/labels)
        try:
            doc = fitz.open(pdf_path)
            page = doc[page_index]
            text_blocks = extract_text_from_page(page)
            
            # Rendering scale check (2.0 for image-based, 1.0 for vector)
            text_scale = 2.0 if pdf_type != "vector" else 1.0
            
            detected_heights = []
            for room in payload.get("rooms", []):
                poly = room.get("polygon", [])
                height = find_room_height(text_blocks, poly, scale=text_scale)
                if height:
                    room["metadata"] = room.get("metadata", {})
                    room["metadata"]["height"] = height
                    detected_heights.append(height)
            
            # If heights were detected, set a floor-level default
            if detected_heights:
                avg_height = sum(detected_heights) / len(detected_heights)
                payload["metadata"] = payload.get("metadata", {})
                payload["metadata"]["floor_height_mm"] = avg_height
                logger.info(f"[*] Detected floor height: {avg_height}mm (from {len(detected_heights)} rooms)")
            
            doc.close()
        except Exception as te:
            logger.error(f"[!] Text extraction failed for page {page_index}: {te}")

        # --- Stage 2: Compliance Extraction ---
        from compliance.extractor import extract_compliance_data
        extract_compliance_data(payload, self.output_dir, page_index)

        # Save cache
        with open(rooms_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            
        return payload

    def process_pdf(self, pdf_path: str, page_index: int = 0) -> Dict[str, Any]:
        """
        Legacy support for single page processing.
        """
        payload = self._extract_page_geometry(pdf_path, page_index, "auto")
        if not payload:
            return {"status": "error"}
            
        from parser.export_ifc import build_ifc_from_meta
        ifc_path = os.path.join(self.output_dir, f"page{page_index}_result.ifc")
        ifc_meta_path = ifc_path + ".meta.json"
        build_ifc_from_meta(payload, out_ifc=ifc_path, out_meta=ifc_meta_path)
        
        rooms_json_path = os.path.join(self.output_dir, f"page{page_index}_rooms.json")
        comp_path = os.path.join(self.output_dir, f"page{page_index}_compliance.json")
        return {
            "status": "success", 
            "artifacts": {
                "ifc": ifc_path,
                "ifc_meta": ifc_meta_path,
                "rooms_json": rooms_json_path,
                "compliance": comp_path
            }
        }

    def process_with_incident(
        self,
        pdf_path: str,
        leak_case: "LeakCase",
        page_index: int = 0,
    ) -> Dict[str, Any]:
        """
        PDF 처리 + LeakCase 인시던트 매핑 통합 파이프라인.

        1. PDF → geometry payload 추출
        2. LeakCase → geometry payload에 인시던트 합성
        3. 인시던트 포함 IFC 생성
        4. LeakCase JSON 저장

        Args:
            pdf_path: PDF 파일 경로
            leak_case: 인시던트 데이터가 담긴 LeakCase 인스턴스
            page_index: 처리할 페이지 번호

        Returns:
            결과 dict (status, artifacts, incident_warnings)
        """
        from scene.incident_mapper import map_incident_to_scene, validate_incident_mapping
        from scene.serializer import save_leak_case
        from pipeline.contracts import validate_incident_payload

        # 1. 기하학 추출
        payload = self._extract_page_geometry(pdf_path, page_index, "auto")
        if not payload:
            return {"status": "error", "message": "Geometry extraction failed"}

        # 2. 인시던트 매핑
        scene_payload = map_incident_to_scene(leak_case, payload)

        # 3. 인시던트 검증
        validate_incident_payload(scene_payload.get("incident", {}))
        incident_warnings = validate_incident_mapping(scene_payload)

        # 4. 인시던트 포함 geometry 저장
        rooms_json_path = os.path.join(self.output_dir, f"page{page_index}_rooms.json")
        with open(rooms_json_path, "w", encoding="utf-8") as f:
            json.dump(scene_payload, f, indent=2)

        # 5. IFC 생성 (인시던트 메타데이터 포함)
        from parser.export_ifc import build_ifc_from_meta
        ifc_path = os.path.join(self.output_dir, f"page{page_index}_result.ifc")
        build_ifc_from_meta(scene_payload, out_ifc=ifc_path, out_meta=ifc_path + ".meta.json")

        # 6. LeakCase 독립 JSON 저장
        case_json_path = os.path.join(self.output_dir, f"incident_{leak_case.case_id}.json")
        save_leak_case(leak_case, case_json_path)

        comp_path = os.path.join(self.output_dir, f"page{page_index}_compliance.json")
        return {
            "status": "success",
            "artifacts": {
                "ifc": ifc_path,
                "rooms_json": rooms_json_path,
                "compliance": comp_path,
                "incident_json": case_json_path,
            },
            "incident_warnings": incident_warnings,
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
    # logger.info(result)
