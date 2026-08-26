"""단가 마스터 로더 (SP3/Q-1).

설계 원칙:
  - fail-closed: 알 수 없는 품목 코드·basis는 조용한 0엔 계상을 금지하고 예외를 던진다
  - 단가 데이터는 data/pricing/*.json (버전관리 대상)에서만 주입받는다
  - 초기 초판은 공개 적산기준 수준의 시장 참고단가이며, 사업자 단가로 교체 가능해야 한다
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

DEFAULT_PRICE_BOOK = Path(__file__).resolve().parent.parent / "data" / "pricing" / "unit_prices_jp.json"

SUPPORTED_SCHEMA_VERSIONS = {"1.0"}


class PricingError(Exception):
    """단가 마스터 조회·정합성 실패 (fail-closed)."""


@dataclass
class WorkItem:
    item_code: str
    name_ja: str
    basis: str                 # 물리량 기준 코드 (takeoff.quantities 상수)
    unit: str
    unit_price: int            # JPY
    category_work: str         # 工種 (解体工/防水工/仕上工...)
    part_filter: List[str] = field(default_factory=list)  # RoomKind 값 필터 (빈 목록 = 전체)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_code": self.item_code,
            "name_ja": self.name_ja,
            "basis": self.basis,
            "unit": self.unit,
            "unit_price": self.unit_price,
            "category_work": self.category_work,
            "part_filter": list(self.part_filter),
        }


class UnitPriceBook:
    """단가 마스터. 스키마 검증 후 불변 취급한다."""

    def __init__(self, raw: Dict[str, Any], source_path: str | Path = DEFAULT_PRICE_BOOK):
        version = str(raw.get("schema_version", ""))
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            raise PricingError(f"Unsupported price book schema_version: {version!r}")
        if raw.get("currency") != "JPY":
            raise PricingError(f"Unsupported currency: {raw.get('currency')!r} (JPY only)")

        meta_rates = ("consumption_tax_rate", "common_temporary_rate", "general_admin_rate")
        for rate_key in meta_rates:
            value = raw.get(rate_key)
            if not isinstance(value, (int, float)) or not (0.0 <= float(value) <= 0.5):
                raise PricingError(f"Invalid {rate_key}: {value!r}")

        items: List[WorkItem] = []
        seen_codes = set()
        for entry in raw.get("work_items", []):
            code = entry.get("item_code")
            if not code:
                raise PricingError("work_item missing item_code")
            if code in seen_codes:
                raise PricingError(f"Duplicate item_code in price book: {code}")
            seen_codes.add(code)
            for required in ("name_ja", "basis", "unit"):
                if not entry.get(required):
                    raise PricingError(f"work_item {code} missing required field: {required}")
            price = entry.get("unit_price")
            if not isinstance(price, int) or price < 0:
                raise PricingError(f"work_item {code} has invalid unit_price: {price!r}")
            items.append(WorkItem(
                item_code=code,
                name_ja=str(entry["name_ja"]),
                basis=str(entry["basis"]),
                unit=str(entry["unit"]),
                unit_price=price,
                category_work=str(entry.get("category_work", "その他")),
                part_filter=[str(p).lower() for p in entry.get("part_filter", [])],
            ))

        if not items:
            raise PricingError("Price book contains no work items")

        self.schema_version = version
        self.currency = "JPY"
        self.valid_from = str(raw.get("valid_from", ""))
        self.consumption_tax_rate = float(raw["consumption_tax_rate"])
        self.common_temporary_rate = float(raw["common_temporary_rate"])
        self.general_admin_rate = float(raw["general_admin_rate"])
        self.work_items = items
        self.source_path = str(source_path)

    @classmethod
    def load(cls, path: str | Path = DEFAULT_PRICE_BOOK) -> "UnitPriceBook":
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        book = cls(raw, source_path=path)
        logger.info(f"[UnitPriceBook] Loaded {len(book.work_items)} work items from {path}")
        return book

    # ------------------------------------------------------------
    # 조회 API (fail-closed)
    # ------------------------------------------------------------
    def get_item(self, item_code: str) -> WorkItem:
        for item in self.work_items:
            if item.item_code == item_code:
                return item
        raise PricingError(f"Unknown item_code in estimate: {item_code!r}")

    def require_basis(self, basis: str) -> bool:
        """작업항목이 참조하는 basis가 수량 문서에 존재하는지 확인용 헬퍼."""
        return any(item.basis == basis for item in self.work_items)
