"""
Unified Compliance Report Generator with 1:1 Legal Citation Binding.
Binds deterministic calculations (Track 1) and hierarchical law snippets (Track 2) into a structured payload.
"""
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
from .rules import JapanBuildingCodeRules, RuleCheckResult, RuleStatus
from .egov_rag import EGovLawRAGEngine, LawNode

@dataclass
class ComplianceItem:
    rule_id: str
    law_article_id: str
    law_name: str
    hierarchical_path: str
    law_snippet: str
    category: str
    status: str
    actual_value: float
    threshold_value: float
    unit: str
    description: str
    exemption_applicable: bool
    remedy_suggestion: str

@dataclass
class ComplianceReport:
    total_checks: int
    passed_count: int
    failed_count: int
    warning_count: int
    overall_verdict: str
    items: List[ComplianceItem]

class DualTrackComplianceEngine:
    def __init__(self):
        self.rag_engine = EGovLawRAGEngine()

    def evaluate_room(self, room_data: Dict[str, Any]) -> ComplianceReport:
        """
        Runs dual-track verification on a given room geometry.
        
        Args:
            room_data: {
                "room_id": str,
                "room_type": str, # e.g. "living_room", "bedroom"
                "floor_area_m2": float,
                "window_effective_area_m2": float,
                "vent_opening_area_m2": float,
                "stair_width_cm": Optional[float]
            }
        """
        results: List[RuleCheckResult] = []
        
        # 1. Track 1: Deterministic Calculations
        floor_area = room_data.get("floor_area_m2", 15.0)
        window_area = room_data.get("window_effective_area_m2", 1.2)
        vent_area = room_data.get("vent_opening_area_m2", 0.5)
        stair_width = room_data.get("stair_width_cm")

        results.append(JapanBuildingCodeRules.check_daylight_ratio(room_data.get("room_type", "living"), floor_area, window_area))
        results.append(JapanBuildingCodeRules.check_ventilation_ratio(room_data.get("room_type", "living"), floor_area, vent_area))
        if stair_width is not None:
            results.append(JapanBuildingCodeRules.check_stair_width(stair_width))

        # 2. Track 2: 1:1 Legal Citation Binding
        items: List[ComplianceItem] = []
        passed = 0
        failed = 0
        warning = 0

        for r in results:
            if r.status == RuleStatus.PASS:
                passed += 1
            elif r.status == RuleStatus.FAIL:
                failed += 1
            else:
                warning += 1

            # Retrieve exact legal snippet from hierarchical e-Gov RAG
            matched_nodes = self.rag_engine.hybrid_search(r.law_article, top_k=1)
            node = matched_nodes[0] if matched_nodes else LawNode(
                law_id="UNKNOWN", law_name="建築基準法", article_number=r.law_article,
                paragraph_num="", item_num="", hierarchical_path="", full_text="법령 원문 검색 중"
            )

            # Suggest remedy for failures
            remedy = ""
            if r.status == RuleStatus.FAIL:
                if "DAYLIGHT" in r.rule_id:
                    shortage = r.threshold_value - r.actual_value
                    remedy = f"창호 개구부 유효 면적을 최소 {shortage:.2f}m² 추가 확보하거나 채광 보정계수가 높은 위치로 창을 재배치하십시오."
                elif "VENTILATION" in r.rule_id:
                    remedy = "건축기준법 시행령 제20조의2에 따른 24시간 기계환기설비(제1종/제3종 환기장치) 설치 시 법적 적합으로 인정됩니다."
                elif "STAIR" in r.rule_id:
                    remedy = f"계단 벽체 간 안치수를 최소 {r.threshold_value - r.actual_value:.1f}cm 확장하십시오."

            items.append(ComplianceItem(
                rule_id=r.rule_id,
                law_article_id=f"{node.law_name} {node.article_number} {node.paragraph_num}".strip(),
                law_name=node.law_name,
                hierarchical_path=node.hierarchical_path,
                law_snippet=node.full_text,
                category=r.category,
                status=r.status.value,
                actual_value=r.actual_value,
                threshold_value=r.threshold_value,
                unit=r.unit,
                description=r.description,
                exemption_applicable=node.is_exemption_clause,
                remedy_suggestion=remedy
            ))

        verdict = "PASSED" if failed == 0 else "VIOLATION_DETECTED"

        return ComplianceReport(
            total_checks=len(items),
            passed_count=passed,
            failed_count=failed,
            warning_count=warning,
            overall_verdict=verdict,
            items=items
        )
