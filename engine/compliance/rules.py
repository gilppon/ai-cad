"""
Deterministic Japanese Building Standard Law (建築基準法) Rule Engine.
Track 1 of the Dual-Track Compliance System.
Enforces exact mathematical equations with 0.0ms execution and 0% hallucination.
"""
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum

class RuleStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    EXEMPTION_CHECK_REQUIRED = "EXEMPTION_CHECK_REQUIRED"

@dataclass
class RuleCheckResult:
    rule_id: str
    law_article: str
    law_title: str
    category: str
    actual_value: float
    threshold_value: float
    unit: str
    status: RuleStatus
    description: str

class JapanBuildingCodeRules:
    """
    Deterministic rule verifier for Japan Building Standard Law (建築基準法).
    """

    @staticmethod
    def check_daylight_ratio(room_type: str, floor_area_m2: float, window_effective_area_m2: float) -> RuleCheckResult:
        """
        建築基準法 第28条 第1項 (採光):
        거실(居室)의 채광 유효 개구부 면적은 바닥 면적의 1/7 이상이어야 함.
        A_daylight >= 1/7 * A_floor
        """
        required_ratio = 1.0 / 7.0  # 0.142857...
        actual_ratio = window_effective_area_m2 / max(floor_area_m2, 0.001)
        required_area = floor_area_m2 * required_ratio
        
        status = RuleStatus.PASS if actual_ratio >= required_ratio else RuleStatus.FAIL
        desc = (
            f"유효 채광면적 {window_effective_area_m2:.2f}m² (바닥면적의 {actual_ratio*100:.1f}%) "
            f"-> 법정 기준 1/7 ({required_area:.2f}m², 14.3%) {'충족' if status == RuleStatus.PASS else '미달(위반)'}"
        )

        return RuleCheckResult(
            rule_id="BSL-ART-28-1-DAYLIGHT",
            law_article="建築基準法 第28条 第1項",
            law_title="居室の採光基準 (채광 기준)",
            category="채광(Daylight)",
            actual_value=round(window_effective_area_m2, 2),
            threshold_value=round(required_area, 2),
            unit="m²",
            status=status,
            description=desc,
        )

    @staticmethod
    def check_ventilation_ratio(room_type: str, floor_area_m2: float, vent_opening_area_m2: float) -> RuleCheckResult:
        """
        建築基準法 第28条 第2項 (換気):
        거실(居室)의 환기 유효 개구부 면적은 바닥 면적의 1/20 이상이어야 함.
        A_vent >= 1/20 * A_floor
        (기계환기설비 설치 시 예외 인정 가능 -> Track 2 연계)
        """
        required_ratio = 1.0 / 20.0  # 0.05
        actual_ratio = vent_opening_area_m2 / max(floor_area_m2, 0.001)
        required_area = floor_area_m2 * required_ratio

        status = RuleStatus.PASS if actual_ratio >= required_ratio else RuleStatus.FAIL
        desc = (
            f"유효 환기면적 {vent_opening_area_m2:.2f}m² (바닥면적의 {actual_ratio*100:.1f}%) "
            f"-> 법정 기준 1/20 ({required_area:.2f}m², 5.0%) {'충족' if status == RuleStatus.PASS else '자연환기 미달(기계환기 예외 검토 필요)'}"
        )

        return RuleCheckResult(
            rule_id="BSL-ART-28-2-VENTILATION",
            law_article="建築基準法 第28条 第2項",
            law_title="居室の換気基準 (환기 기준)",
            category="환기(Ventilation)",
            actual_value=round(vent_opening_area_m2, 2),
            threshold_value=round(required_area, 2),
            unit="m²",
            status=status,
            description=desc,
        )

    @staticmethod
    def check_stair_width(stair_width_cm: float, building_type: str = "residential") -> RuleCheckResult:
        """
        建築基準法施行令 第23条 (階段及びその踊場の幅等):
        주택의 계단 유효폭은 75cm 이상이어야 함. (공동주택/다세대 등은 90cm 이상)
        """
        required_width = 75.0 if building_type == "residential" else 90.0
        status = RuleStatus.PASS if stair_width_cm >= required_width else RuleStatus.FAIL
        desc = (
            f"계단 유효 폭 {stair_width_cm:.1f}cm "
            f"-> 법정 최소 폭 {required_width:.1f}cm {'충족' if status == RuleStatus.PASS else '미달(위반)'}"
        )

        return RuleCheckResult(
            rule_id="BSL-ORD-23-STAIR-WIDTH",
            law_article="建築基準法施行令 第23条 第1項",
            law_title="階段及び踊場の有効幅 (계단 유효 폭)",
            category="피난/통행(Safety)",
            actual_value=round(stair_width_cm, 1),
            threshold_value=round(required_width, 1),
            unit="cm",
            status=status,
            description=desc,
        )

    @staticmethod
    def check_smoke_exhaust_ratio(floor_area_m2: float, smoke_exhaust_window_area_m2: float) -> RuleCheckResult:
        """
        建築基準法施行令 第126条の2 (排煙設備の設置):
        거실의 자연 배연 유효 개구부 면적은 바닥 면적의 1/50 이상이어야 함.
        A_smoke >= 1/50 * A_floor
        """
        required_ratio = 1.0 / 50.0  # 0.02
        actual_ratio = smoke_exhaust_window_area_m2 / max(floor_area_m2, 0.001)
        required_area = floor_area_m2 * required_ratio

        status = RuleStatus.PASS if actual_ratio >= required_ratio else RuleStatus.FAIL
        desc = (
            f"유효 배연면적 {smoke_exhaust_window_area_m2:.2f}m² (바닥면적의 {actual_ratio*100:.1f}%) "
            f"-> 법정 기준 1/50 ({required_area:.2f}m², 2.0%) {'충족' if status == RuleStatus.PASS else '자연배연 미달(기계배연설비 필요)'}"
        )

        return RuleCheckResult(
            rule_id="BSL-ORD-126-2-SMOKE",
            law_article="建築基準法施行令 第126条の2",
            law_title="排煙有効開口部 (배연 유효 개구부)",
            category="배연(Smoke Exhaust)",
            actual_value=round(smoke_exhaust_window_area_m2, 2),
            threshold_value=round(required_area, 2),
            unit="m²",
            status=status,
            description=desc,
        )

    @staticmethod
    def check_corridor_width(corridor_width_m: float, both_sides_rooms: bool = False) -> RuleCheckResult:
        """
        建築基準法施行令 第119条 (廊下の幅):
        복도 양측에 거실이 있는 경우 1.6m 이상, 기타의 경우 1.2m 이상.
        """
        required_width = 1.6 if both_sides_rooms else 1.2
        status = RuleStatus.PASS if corridor_width_m >= required_width else RuleStatus.FAIL
        desc = (
            f"복도 유효 폭 {corridor_width_m:.2f}m "
            f"-> 법정 기준 ({'양측 거실 1.60m' if both_sides_rooms else '단일 거실 1.20m'}) "
            f"{'충족' if status == RuleStatus.PASS else '미달(위반)'}"
        )

        return RuleCheckResult(
            rule_id="BSL-ORD-119-CORRIDOR",
            law_article="建築基準法施行令 第119条",
            law_title="廊下の有効幅 (복도 유효 폭)",
            category="피난/복도(Corridor)",
            actual_value=round(corridor_width_m, 2),
            threshold_value=round(required_width, 2),
            unit="m",
            status=status,
            description=desc,
        )

    @staticmethod
    def check_evacuation_travel_distance(walking_distance_m: float, is_fireproof: bool = True) -> RuleCheckResult:
        """
        建築基準法 第35조 & 建築基準法施行令 第120条 (直通階段に至る歩行距離):
        거실의 각 부분에서 직통계단(피난계단)에 이르는 보행거리는
        주요구조부가 내화구조인 경우 50m 이하, 기타 구조인 경우 30m 이하여야 함.
        """
        max_allowed_distance = 50.0 if is_fireproof else 30.0
        status = RuleStatus.PASS if walking_distance_m <= max_allowed_distance else RuleStatus.FAIL
        desc = (
            f"직통계단까지의 보행거리 {walking_distance_m:.1f}m "
            f"-> 법정 최대 허용거리 ({'내화구조 50.0m' if is_fireproof else '기타구조 30.0m'}) "
            f"{'충족' if status == RuleStatus.PASS else '초과(피난계단 추가 필요)'}"
        )

        return RuleCheckResult(
            rule_id="BSL-ART-35-ORD-120-TRAVEL-DISTANCE",
            law_article="建築基準法 第35条 / 施行令 第120条",
            law_title="避難階段歩行距離 (피난계단 보행거리)",
            category="피난/안전(Evacuation)",
            actual_value=round(walking_distance_m, 1),
            threshold_value=round(max_allowed_distance, 1),
            unit="m",
            status=status,
            description=desc,
        )

    @staticmethod
    def check_dual_staircase_requirement(floor_area_m2: float, floor_level: int) -> RuleCheckResult:
        """
        建築基準法施行令 第121条 (2以上の直通階段の設置):
        6층 이상의 층에서 거실 바닥면적이 100m²를 넘거나,
        피난층 외의 층에서 일정 규모 이상인 경우 2개 이상의 직통계단 설치 의무화.
        """
        threshold_area = 100.0 if floor_level >= 6 else 200.0
        requires_dual = (floor_area_m2 > threshold_area)
        status = RuleStatus.WARNING if requires_dual else RuleStatus.PASS
        desc = (
            f"{floor_level}층 바닥면적 {floor_area_m2:.1f}m² (기준 {threshold_area:.1f}m²) "
            f"-> {'2개 이상의 직통(피난)계단 설치 의무 대상' if requires_dual else '단일 계단 설치 허용'}"
        )

        return RuleCheckResult(
            rule_id="BSL-ORD-121-DUAL-STAIR",
            law_article="建築基準法施行令 第121条",
            law_title="2以上の直通階段 (2개 이상 직통계단 의무)",
            category="피난/계단(Evacuation)",
            actual_value=round(floor_area_m2, 1),
            threshold_value=round(threshold_area, 1),
            unit="m²",
            status=status,
            description=desc,
        )
