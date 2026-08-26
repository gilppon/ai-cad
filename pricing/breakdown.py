"""공사비내역서(工事費内訳書) 빌더 (SP3/Q-1).

일본 적산 관행 구조 (code_remediation_plan_v1.0 §3.3):
  総工事費(税込)
   ├─ 直接工事費            = Σ(작업항목 수량 × 단가)
   ├─ 共通仮設費            = 直接工事費 × common_temporary_rate
   ├─ 工事原価              = 直接工事費 + 共通仮設費
   └─ 経費(一般管理費)      = 工事原価 × general_admin_rate
       消費税               = (工事原価 + 経費) × consumption_tax_rate

모든 금액은 엔화 정수(원단위 절상)로 계산한다.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from pricing.unit_price_book import UnitPriceBook
from takeoff.quantities import QuantityLine, summarize_by_basis
from takeoff.classification import classification_for_basis

logger = logging.getLogger(__name__)


def _yen(value: float) -> int:
    """엔화 반올림 (원단위, half-up)."""
    return int(math.floor(float(value) + 0.5))


@dataclass
class EstimateLine:
    item_code: str
    name_ja: str
    category_work: str          # 工種
    classification: str         # bSJ 계열 분류
    part: str                   # 部位 (RoomKind)
    basis: str
    unit: str
    quantity: float
    unit_price: int
    amount: int                 # quantity × unit_price (엔)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def build_estimate_lines(quantity_lines: List[QuantityLine],
                         book: UnitPriceBook) -> List[EstimateLine]:
    """
    물리 수량 라인 × 작업항목 마스터 → 견적 명산 라인.

    조인 규칙:
      - 작업항목의 basis별 총량을 기본으로 하되, part_filter가 지정된 항목은
        해당 부위(RoomKind) 수량만 집계한다 (部位別内訳書 개념)
      - 수량 0인 항목은 명산에서 제외한다
      - 알 수 없는 basis를 참조하는 작업항목이 수량 문서와 만나지 못하면 경고만 남긴다
        (단, 수량 문서에 없는 코드를 견적서가 요구하면 PricingError - fail-closed는 조회 축에서 유지)
    """
    by_basis_part: Dict[Tuple[str, str], float] = {}
    for l in quantity_lines:
        key = (l.basis, l.part)
        by_basis_part[key] = by_basis_part.get(key, 0.0) + l.quantity
    totals_by_basis = summarize_by_basis(quantity_lines)

    lines: List[EstimateLine] = []
    for item in book.work_items:
        if item.part_filter:
            qty = sum(
                v for (basis, part), v in by_basis_part.items()
                if basis == item.basis and part in item.part_filter
            )
        else:
            qty = totals_by_basis.get(item.basis, 0.0)

        if qty <= 0:
            continue

        lines.append(EstimateLine(
            item_code=item.item_code,
            name_ja=item.name_ja,
            category_work=item.category_work,
            classification=classification_for_basis(item.basis),
            part="・".join(item.part_filter) if item.part_filter else "共通",
            basis=item.basis,
            unit=item.unit,
            quantity=round(qty, 3),
            unit_price=item.unit_price,
            amount=_yen(qty * item.unit_price),
        ))

    # 공종 → 품목 순 안정 정렬 (내역서 가독성)
    lines.sort(key=lambda x: (x.category_work, x.item_code))
    logger.info(f"[Breakdown] {len(lines)} estimate lines built")
    return lines


def build_breakdown(quantity_lines: List[QuantityLine],
                    book: UnitPriceBook) -> Dict[str, Any]:
    """직공공사비/공사일반공사비/경비/소비세/총액 구조의 내역서를 생성한다."""
    estimate_lines = build_estimate_lines(quantity_lines, book)

    direct_cost = sum(l.amount for l in estimate_lines)
    common_temporary = _yen(direct_cost * book.common_temporary_rate)
    construction_cost = direct_cost + common_temporary
    expenses = _yen(construction_cost * book.general_admin_rate)
    taxable_base = construction_cost + expenses
    consumption_tax = _yen(taxable_base * book.consumption_tax_rate)
    total_including_tax = taxable_base + consumption_tax

    # 공종별 소계 (工種別内訳서 뷰)
    work_subtotals: Dict[str, int] = {}
    for l in estimate_lines:
        work_subtotals[l.category_work] = work_subtotals.get(l.category_work, 0) + l.amount

    return {
        "lines": [l.to_dict() for l in estimate_lines],
        "work_type_subtotals": dict(sorted(work_subtotals.items())),
        "direct_cost": direct_cost,                       # 直接入工事費
        "common_temporary_cost": common_temporary,        # 共通仮設費
        "construction_cost": construction_cost,           # 工事原価
        "expenses": expenses,                             # 経費(一般管理費)
        "taxable_base": taxable_base,                     # 課税対象額
        "consumption_tax": consumption_tax,               # 消費税
        "total_including_tax": total_including_tax,       # 総工事費(税込)
        "rates": {
            "common_temporary_rate": book.common_temporary_rate,
            "general_admin_rate": book.general_admin_rate,
            "consumption_tax_rate": book.consumption_tax_rate,
        },
        "currency": "JPY",
    }
