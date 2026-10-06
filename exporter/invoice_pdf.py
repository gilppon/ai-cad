"""適格請求書(インボイス) + 銀行振込 안내 PDF — STATE G7 코드분.

B2B 96% 銀行振込 관행 대응. Stripe 단독을 대체하지 않고 병행한다.
- 金額은 PRICING_MAP 세율과 동일. 日本表示는 税込이며 内消費税(10/110)를 병기한다.
- 登録番号·振込先은 env/파라미터 주입. 미설정 시 (未登録)/(請求時に通知) 표기 —
  없는 번호를 찍어내는 문서위조를 방지한다 (SP1/D-1 계승).
- 실제 입금 확인·消込은 운영(수동) 몫이다. 본 모듈은 발행까지만 책임진다.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import exporter.pdf_generator  # noqa: F401  (CID font patch 재사용)

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

TAX_RATE = 0.10


def _tax_included_breakdown(total_incl: int) -> Dict[str, int]:
    tax = int(round(total_incl * TAX_RATE / (1 + TAX_RATE)))
    return {"total_incl": total_incl, "tax": tax, "excl": total_incl - tax}


def _plan_amount(plan_type: str) -> Dict[str, Any]:
    from app.services.payment import StripePaymentService
    info = StripePaymentService.PRICING_MAP.get(plan_type)
    if not info:
        raise ValueError(f"Unknown plan_type: {plan_type}")
    return info


def generate_invoice_pdf(
    user_id: str,
    plan_type: str,
    output_pdf_path: Optional[str] = None,
    invoice_no: Optional[str] = None,
    client_name: str = "御中",
    invoice_registration_number: Optional[str] = None,
) -> Dict[str, Any]:
    """請求書 PDF 발행. 반환: {path, invoice_no, total_incl, tax, ...}."""
    from pipeline.paths import OUTPUT_ROOT

    plan = _plan_amount(plan_type)
    total = int(plan["amount"])
    calc = _tax_included_breakdown(total)

    reg_no = (invoice_registration_number
              or os.getenv("JP_INVOICE_REGISTRATION_NUMBER", "").strip()
              or "(未登録)")
    bank = {
        "bank": os.getenv("JP_BANK_NAME", "").strip() or "(請求時に通知)",
        "branch": os.getenv("JP_BANK_BRANCH", "").strip() or "",
        "account": os.getenv("JP_BANK_ACCOUNT", "").strip() or "",
        "holder": os.getenv("JP_BANK_HOLDER", "").strip() or "",
    }
    if not output_pdf_path:
        output_pdf_path = str(Path(OUTPUT_ROOT) / "projects" / user_id / "invoice.pdf")
    parent = os.path.dirname(os.path.abspath(output_pdf_path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
    inv_no = invoice_no or f"INV-{today.replace('-', '')}-{abs(hash(user_id + plan_type)) % 10000:04d}"

    title = ParagraphStyle("t", fontName="HeiseiKakuGo-W5", fontSize=18, leading=24, alignment=1)
    body = ParagraphStyle("b", fontName="HeiseiKakuGo-W5", fontSize=10, leading=15)
    small = ParagraphStyle("s", fontName="HeiseiKakuGo-W5", fontSize=8, leading=12)

    story = [
        Paragraph("請 求 書（適格請求書）", title),
        Paragraph(f"請求書番号: {inv_no} / 発行日: {today}", small),
        Paragraph(f"登録番号: {reg_no}", small),
        Spacer(1, 6),
        Paragraph(client_name, body),
        Spacer(1, 6),
    ]
    rows = [["品目", "金額(税込)"],
            [str(plan["name"]), f"¥{calc['total_incl']:,}"],
            ["うち消費税額(10%)", f"¥{calc['tax']:,}"]]
    t = Table(rows, colWidths=[350, 130])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, "black"),
        ("FONTNAME", (0, 0), (-1, -1), "HeiseiKakuGo-W5"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story += [t, Spacer(1, 6)]
    bank_line = f"お振込先: {bank['bank']} {bank['branch']} {bank['account']} {bank['holder']}".strip()
    story += [
        Paragraph(bank_line, body),
        Paragraph("※お振込手数料はお客様負担となります。入金確認後の役務提供となります。", small),
        Paragraph("※本書は請求書であり領収書ではありません。", small),
    ]
    SimpleDocTemplate(output_pdf_path, pagesize=A4,
                      leftMargin=36, rightMargin=36).build(story)
    logger.info(f"[Invoice] {output_pdf_path} ({inv_no}, ¥{total:,})")
    return {"path": output_pdf_path, "invoice_no": inv_no,
            "plan_type": plan_type, **calc}
