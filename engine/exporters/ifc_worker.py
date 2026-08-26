"""
Isolated Real-IFC Export Worker. (SP2/A-2)

구 스텁(손작성 IFC 텍스트)을 대체하는 실경로 워커이다.
SSOT 원칙에 따라 IFC 생성 로직은 parser/export_ifc.build_ifc_from_multi_floor(ifcopenshell)를
그대로 사용하며, 본 워커는 SandboxExporterRunner/ExporterWorkerPool의 서브프로세스 계약
(--input JSON / --output JSON)을 수행하는 얇은 어댑터일 뿐이다.

입력 페이로드 형식:
{
  "target_path": "<출력 .ifc 경로 (out/ 이내)>",
  "payload": { "rooms": [...], "walls": [...], "scale": {...}, "metadata": {...} },
  "floors": [ <payload>, <payload>, ... ]   # 다층 옵션 (없으면 payload 1층으로 구성)
}
"""
import argparse
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def run(payload: dict) -> dict:
    from parser.export_ifc import build_ifc_from_multi_floor

    target = payload.get("target_path")
    if not target:
        raise ValueError("target_path is required")

    floors = payload.get("floors") or [payload.get("payload") or {}]
    build_ifc_from_multi_floor(floors, out_ifc=target)

    space_count = sum(len(f.get("rooms", [])) for f in floors)
    wall_count = sum(len(f.get("walls", [])) for f in floors)
    return {
        "success": True,
        "format": "IFC4",
        "exported_file": target,
        "space_count": space_count,
        "wall_count": wall_count,
        "file_size_bytes": os.path.getsize(target),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Isolated Real-IFC Export Worker (ifcopenshell)")
    parser.add_argument("--input", required=True, help="Input JSON payload file")
    parser.add_argument("--output", required=True, help="Output JSON result file")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            payload = json.load(f)

        result = run(payload)

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f)
        sys.exit(0)
    except Exception as err:
        error_res = {"success": False, "error": str(err)}
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(error_res, f)
        sys.exit(1)
