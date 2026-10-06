"""개구부(문·창) 후보 추출 C8 (프로덕션 경로).

벽선 집합의 동일 축 정렬선 사이 틈(gap)에서 개구부 후보를 도출한다.
- 검출 수학은 `parser/export_step._derive_doors_from_wall_gaps` (STEP8 실전 경로)와
  동일 함수를 사용한다. 이중구현이 아니라 단일 구현의 생산 연결이다.
- 좌표 단위: `extract_room_result_from_page`의 2x 렌더 px (fitz Matrix 2.0).
  gap 8~80px = 문 크기 후보. 그 이상은 열린 공간으로 보고 제외한다.
- 후보는 후보일 뿐 확정문이 아니다. 최종 판단은 현장·유자격자 몫이다.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence


def derive_openings(walls_lines: Sequence[Any],
                    min_gap_px: float = 8.0,
                    max_gap_px: float = 80.0) -> List[Dict[str, Any]]:
    """walls_lines: [{"x1","y1","x2","y2"}] 또는 [x1,y1,x2,y2] 혼용 허용."""
    from parser.export_step import _derive_doors_from_wall_gaps

    segs = []
    for w in walls_lines or []:
        try:
            if isinstance(w, dict):
                segs.append((float(w["x1"]), float(w["y1"]),
                             float(w["x2"]), float(w["y2"])))
            else:
                segs.append((float(w[0]), float(w[1]), float(w[2]), float(w[3])))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    if not segs:
        return []
    return _derive_doors_from_wall_gaps(segs, min_gap_px=min_gap_px,
                                        max_gap_px=max_gap_px)


def summarize_openings(openings: List[Dict[str, Any]]) -> Dict[str, Any]:
    gaps = sorted(o.get("gap_px", 0) for o in openings or [])
    return {
        "count": len(gaps),
        "min_gap_px": round(gaps[0], 1) if gaps else None,
        "max_gap_px": round(gaps[-1], 1) if gaps else None,
        "unit": "render-px (2x)",
    }
