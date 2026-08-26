"""建築物省エネ法(건축물 채에네기야법) BEI 규칙 세트 — SP5.

근거 (모두 공식 자료로 교차 검증됨, data/laws/manifest.json notes 참조):
  - 법령: 建築物のエネルギー消費の合理性に関する法律 (e-Gov law_id: 427AC0000000053)
  - 2025-04-01: 원칙적으로 모든 신축 주택·건축물에 省エネ基준 적합 의무화
  - 2024-04-01: 대규모 비주거(≥2000㎡) 용도별 BEI 기준 인상
  - 2026-04-01: 중규모 비주거(300㎡≤A<2000㎡) 동일 수준으로 인상 (적판 신청분부터)
      工場等                          → BEI ≤ 0.75
      事務所等·学校等·ホテル等·百貨店等 → BEI ≤ 0.80
      病院等·飲食店等·集会所等         → BEI ≤ 0.85
  - 주택 및 300㎡ 미만 비주거: BEI ≤ 1.0

보안 정책 (SP1/L-2 계승): 산출 데이터 부재 시 가짜「適合」을 만들지 않고 N/A(判定不能)를 반환한다.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

RULE_ID_ENERGY = "RULE-JP-SHOENE-BEI"

LAW_META = {
    "law_id": "427AC0000000053",
    "title_ja": "建築物のエネルギー消費の合理性に関する法律（建築物省エネ法）",
    "title_ko": "건축물 에너지소비 합리화 관련 법률(건축물 채에네기야법)",
    "law_num_ja": "平成二十七年法律第五十三号",
}

# 2026-04-01 시행 (대규모는 2024-04-01부터 동일 수준)
STRENGTHENED_EFFECTIVE_DATE = date(2026, 4, 1)
LARGE_SCALE_EFFECTIVE_DATE = date(2024, 4, 1)

# 비주거 용도별 강화 기준 (en 키 ↔ 일본어 공식 명칭)
USE_CATEGORY_THRESHOLDS: Dict[str, Dict[str, Any]] = {
    "factory":          {"label_ja": "工場等",   "threshold": 0.75},
    "office":           {"label_ja": "事務所等", "threshold": 0.80},
    "school":           {"label_ja": "学校等",   "threshold": 0.80},
    "hotel":            {"label_ja": "ホテル等", "threshold": 0.80},
    "department_store": {"label_ja": "百貨店等", "threshold": 0.80},
    "hospital":         {"label_ja": "病院等",   "threshold": 0.85},
    "restaurant":       {"label_ja": "飲食店等", "threshold": 0.85},
    "community_hall":   {"label_ja": "集会所等", "threshold": 0.85},
}

MEDIUM_SCALE_MIN_M2 = 300.0
LARGE_SCALE_MIN_M2 = 2000.0
DEFAULT_BEI_THRESHOLD = 1.0


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def resolve_bei_threshold(*,
                          building_type: str,
                          use_category: Optional[str],
                          total_floor_area_m2: Optional[float],
                          judgment_date: Any = None) -> Dict[str, Any]:
    """
    규모·용도·적판 시점에 따라 적용되는 BEI 기준값을 결정한다.

    반환: {"threshold": float, "basis_ja": str, "strengthened": bool}
    """
    is_residential = str(building_type or "").strip().lower() in ("residential", "housing", "home")
    jdate = _parse_date(judgment_date) or date.today()
    area = float(total_floor_area_m2) if total_floor_area_m2 is not None else None

    if is_residential:
        return {
            "threshold": DEFAULT_BEI_THRESHOLD,
            "basis_ja": "住宅部分：一次エネルギー消量性能 BEI≦1.0",
            "strengthened": False,
        }

    cat = str(use_category or "").strip().lower()
    cat_info = USE_CATEGORY_THRESHOLDS.get(cat)

    # 비주거 대규모(≥2000㎡): 2024-04부터 용도별 기준
    if area is not None and area >= LARGE_SCALE_MIN_M2:
        if cat_info and jdate >= LARGE_SCALE_EFFECTIVE_DATE:
            return {
                "threshold": cat_info["threshold"],
                "basis_ja": f"大規模非住宅（{cat_info['label_ja']}）：BEI≦{cat_info['threshold']:.2f}",
                "strengthened": True,
            }
        return {
            "threshold": DEFAULT_BEI_THRESHOLD,
            "basis_ja": "大規模非住宅：BEI≦1.0",
            "strengthened": False,
        }

    # 비주거 중규모(300~2000㎡): 2026-04 적판 신청분부터 인상 기준
    if area is not None and MEDIUM_SCALE_MIN_M2 <= area < LARGE_SCALE_MIN_M2:
        if cat_info and jdate >= STRENGTHENED_EFFECTIVE_DATE:
            return {
                "threshold": cat_info["threshold"],
                "basis_ja": f"中規模非住宅（{cat_info['label_ja']}）：BEI≦{cat_info['threshold']:.2f}"
                            f"（2026年4月1日以降の適判申請分）",
                "strengthened": True,
            }
        return {
            "threshold": DEFAULT_BEI_THRESHOLD,
            "basis_ja": "中規模非住宅：BEI≦1.0（2026年3月31日までの適判申請分）",
            "strengthened": False,
        }

    # 소규모 비주거(<300㎡) 또는 면적 불명
    return {
        "threshold": DEFAULT_BEI_THRESHOLD,
        "basis_ja": "小規模非住宅：BEI≦1.0",
        "strengthened": False,
    }


def evaluate_energy_compliance(section: Dict[str, Any],
                               judgment_date: Any = None) -> Dict[str, Any]:
    """
    page0_compliance.json의 'energy' 섹션을 평가해 체크시트 항목 1건을 생성한다.

    섹션 필수 입력:
      building_type: "residential" | "non_residential"
      use_category:  USE_CATEGORY_THRESHOLDS 키 (비주거인 경우)
      total_floor_area_m2: float
      design_primary_energy_mj_per_year / baseline_primary_energy_mj_per_year: float

    반환 키는 체크시트 조립 계약과 동일하다:
      article_no / item_name_jp / standard_value / calculated_value /
      status(PASS|FAIL|N/A) / inspector_comment / facts
    """
    building_type = section.get("building_type")
    design_e = section.get("design_primary_energy_mj_per_year")
    baseline_e = section.get("baseline_primary_energy_mj_per_year")

    resolution = resolve_bei_threshold(
        building_type=str(building_type or ""),
        use_category=section.get("use_category"),
        total_floor_area_m2=section.get("total_floor_area_m2"),
        judgment_date=judgment_date or section.get("judgment_date"),
    )
    threshold = resolution["threshold"]

    article_no = f"{LAW_META['title_ja']}（{LAW_META['law_num_ja']}）"
    item_name = "一次エネルギー消費性能（BEI）"
    standard_value = f"BEI ≦ {threshold:.2f}"

    facts = {
        "bei": None,
        "threshold": threshold,
        "basis_ja": resolution["basis_ja"],
        "building_type": str(building_type or ""),
        "use_category": str(section.get("use_category") or ""),
    }

    def _item(status: str, calc: str, comment: str, extra_facts: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(facts)
        merged.update(extra_facts)
        return {
            "article_no": article_no,
            "item_name_jp": item_name,
            "standard_value": standard_value,
            "calculated_value": calc,
            "status": status,
            "inspector_comment": comment,
            "facts": merged,
        }

    # 필수 산출치 부재: 의무 대상이므로 판정 불가를 명시 (가짜適合 금지)
    if design_e is None or baseline_e is None or not baseline_e:
        return _item(
            "N/A",
            "-",
            "省エネ適判に必要な設計・基準一次エネルギー消費量が未入力のため、"
            "自動判定を実施できません。Webプログラム（建築研究所）の算出結果を登録してください。",
            {},
        )

    bei = float(design_e) / float(baseline_e)
    facts["bei"] = round(bei, 4)

    if bei <= threshold:
        return _item(
            "PASS",
            f"BEI = {bei:.2f}",
            f"設計一次エネルギー消費量が基準を下回り（BEI={bei:.2f}≦{threshold:.2f}）、"
            "建築物省エネ法に基づく省エネ基準に適合することを確認した。",
            {"applied_threshold_basis": resolution["basis_ja"]},
        )

    return _item(
        "FAIL",
        f"BEI = {bei:.2f}",
        f"BEIが基準値を超過している（BEI={bei:.2f}＞{threshold:.2f}）。"
        "高効率設備の選定、外皮性能の向上、再生可能エネルギー設備の導入等による再検討が必要である。",
        {"applied_threshold_basis": resolution["basis_ja"]},
    )
