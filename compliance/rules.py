from dataclasses import dataclass
from typing import Callable, Any, Dict, List

@dataclass
class ComplianceRule:
    rule_id: str
    name: str
    description: str
    evaluate: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]  # (room, global_context) -> result

def _evaluate_lighting(room: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rule 1: 건축기준법 제28조 (채광 및 환기)
    거실(LDK, BEDROOM 등)의 창문 면적은 바닥 면적의 1/7 이상이어야 한다.
    """
    # 거실이 아니면 패스 (단순화를 위해 LDK, BEDROOM만 거실로 간주)
    habitable_kinds = ["LDK", "BEDROOM", "LIVING", "DINING"]
    if room.get("kind", "UNKNOWN") not in habitable_kinds:
        return {"status": "PASS", "reason": "거실(Habitable Room)에 해당하지 않음"}

    area_m2 = room.get("area_m2", 0.0)
    if area_m2 <= 0:
        return {"status": "PASS", "reason": "면적 측정 불가"}

    required_window_area = area_m2 / 7.0

    # 해당 방에 연결된 WINDOW 면적 합산 (근사치: 폭 * 높이)
    # 현재 도면에서 창문 높이를 알 수 없으므로, 기본 높이를 1.5m(1500mm)로 가정하여 계산
    window_area_m2 = 0.0
    openings = context.get("openings", [])

    # TODO: 방과 개구부의 정확한 연결성(connected_rooms) 파악 로직 고도화 필요
    # MVP 단계에서는 해당 방의 bounding box 주변에 있는 WINDOW를 임의 할당하거나,
    # 또는 향후 SLM에서 시각적으로 판단하도록 위임할 수 있음.
    # 현재는 extractor.py에서 connected_rooms가 비어있음.
    # 테스트를 위해 임시로 방 안에 포함된 개구부를 계산하는 로직 추가

    # -----------------------------
    # 임시 계산: 만약 창문 면적이 충족되지 않으면 FAIL 반환
    # (실제 기하학 계산은 evaluator.py 등에서 보강)
    # -----------------------------
    room_window_area = room.get("actual_window_area_m2", 0.0)

    # SP2/L-3: 리포트 계층이 재파싱 없이 소비할 수 있도록 구조화 수치를 함께 반환한다.
    facts = {
        "floor_area_m2": float(area_m2),
        "window_area_m2": float(room_window_area),
        "required_window_area_m2": float(required_window_area),
        "window_to_floor_ratio": (float(room_window_area) / float(area_m2)) if area_m2 > 0 else None,
        "required_ratio_denominator": 7.0,
    }

    if room_window_area >= required_window_area:
        return {
            "status": "PASS",
            "reason": f"창문 면적({room_window_area:.2f}m²)이 최소 기준({required_window_area:.2f}m²) 충족",
            "facts": facts,
        }
    else:
        return {
            "status": "FAIL",
            "reason": f"채광 부족: 창문 면적({room_window_area:.2f}m²)이 최소 기준({required_window_area:.2f}m²) 미달 (바닥 면적 {area_m2:.2f}m²)",
            "facts": facts,
        }

def _evaluate_ceiling_height(room: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rule 2: 건축기준법 시행령 제21조 (거실의 반자 높이)
    거실의 층고는 2.1m (2100mm) 이상이어야 한다.
    """
    habitable_kinds = ["LDK", "BEDROOM", "LIVING", "DINING"]
    if room.get("kind", "UNKNOWN") not in habitable_kinds:
        return {"status": "PASS", "reason": "거실(Habitable Room)에 해당하지 않음"}

    height_mm = room.get("height_mm", 0.0)

    facts = {
        "height_mm": float(height_mm),
        "required_height_mm": 2100.0,
    }

    if height_mm >= 2100.0:
        return {
            "status": "PASS",
            "reason": f"반자 높이({height_mm}mm)가 최소 기준(2100mm) 충족",
            "facts": facts,
        }
    else:
        return {
            "status": "FAIL",
            "reason": f"반자 높이 미달: 층고가 {height_mm}mm로 최소 기준(2100mm) 미만임",
            "facts": facts,
        }

# 규칙 목록 선언
JAPAN_BUILDING_RULES = [
    ComplianceRule(
        rule_id="RULE-JP-LAW-28",
        name="거실의 채광 (건축기준법 제28조)",
        description="거실의 채광 유효 개구부 면적은 바닥 면적의 1/7 이상이어야 합니다.",
        evaluate=_evaluate_lighting
    ),
    ComplianceRule(
        rule_id="RULE-JP-ORD-21",
        name="거실의 반자 높이 (시행령 제21조)",
        description="거실의 반자 높이는 2.1m 이상이어야 합니다.",
        evaluate=_evaluate_ceiling_height
    )
]
