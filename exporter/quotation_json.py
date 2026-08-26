"""数量取合書 호환 견적 문서(JSON) 조립기 — SP3/Q-1.

takeoff(물리 수량) + pricing(단가·내역) 결과를 하나의 버전화된 견적 문서로 직렬화한다.
모든 명산 라인은 source_ref로 원천 엔티티 역추적을 보장한다.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pricing.breakdown import build_breakdown
from pricing.unit_price_book import UnitPriceBook, DEFAULT_PRICE_BOOK
from takeoff.quantities import takeoff_from_payload

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_quotation_document(project_id: str,
                             payload: Dict[str, Any],
                             compliance_doc: Optional[Dict[str, Any]] = None,
                             price_book_path: str | Path = DEFAULT_PRICE_BOOK) -> Dict[str, Any]:
    """
    GeometryPayload(+옵션 컴플라이언스 개구부) → 数量取合書 호환 견적 JSON.
    """
    book = UnitPriceBook.load(price_book_path)

    quantity_lines = takeoff_from_payload(payload, compliance_doc)
    breakdown = build_breakdown(quantity_lines, book)

    document = {
        "schema_version": "1.0",
        "document_kind": "quotation",          # 数量取合書・見積書 원장
        "project_id": project_id,
        "issued_at": _now_iso(),
        "currency": "JPY",
        "price_book": {
            "path": str(book.source_path),
            "schema_version": book.schema_version,
            "valid_from": book.valid_from,
            "item_count": len(book.work_items),
        },
        # 물리 수량 (원천 역추적 가능)
        "quantities": [l.to_dict() for l in quantity_lines],
        # 공사비내역
        "breakdown": breakdown,
        "totals": {
            "direct_cost": breakdown["direct_cost"],
            "construction_cost": breakdown["construction_cost"],
            "taxable_base": breakdown["taxable_base"],
            "consumption_tax": breakdown["consumption_tax"],
            "total_including_tax": breakdown["total_including_tax"],
        },
    }
    logger.info(f"[Quotation] Built for {project_id}: "
                f"total ¥{breakdown['total_including_tax']:,} (tax incl.)")
    return document


def save_quotation(document: Dict[str, Any], output_dir: str | Path) -> Path:
    out_path = Path(output_dir) / "quotation.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(document, f, indent=2, ensure_ascii=False)
    return out_path


def load_quotation(output_dir: str | Path) -> Optional[Dict[str, Any]]:
    out_path = Path(output_dir) / "quotation.json"
    if not out_path.exists():
        return None
    with open(out_path, "r", encoding="utf-8") as f:
        return json.load(f)
