"""お見積書 PDF 생성기 — SP3/Q-1.

ReportLab 기반 A4 견적서. 인보이스(適格請求書発行事業者) 등록번호는
환경변수 JP_INVOICE_REGISTRATION_NUMBER 또는 파라미터로만 주입하며
미설정 시 (未登録) 표기한다 — 법적 문서 위조 방지 정책 (SP1/D-1 계승).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 폰트 바인딩(HeiseiKakuGo-W5/HeiseiMin-W3 + ps2tt 패치)은 기존 보고서 생성기의 설정을 재사용한다.
import exporter.pdf_generator  # noqa: F401  (side-effect: reportlab CID font patch)

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

logger = logging.getLogger(__name__)


def _yen(value) -> str:
    return f"¥{int(round(float(value))):,}"


class QuotationPDFGenerator:
    """일본 상거래 관행 양식의 見積書 1장 생성기."""

    @staticmethod
    def generate(
        project_id: str,
        quotation_doc: Dict[str, Any],
        output_pdf_path: str = None,
        invoice_registration_number: str = None,
        client_name: str = "御中",
        subject_name: str = None,
        notes: Optional[List[str]] = None,
    ) -> str:
        from pipeline.paths import OUTPUT_ROOT

        if not output_pdf_path:
            output_pdf_path = str(Path(OUTPUT_ROOT) / "projects" / project_id / "quotation.pdf")

        output_pdf_path = os.path.abspath(output_pdf_path)
        parent_dir = os.path.dirname(output_pdf_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        invoice_reg_no = (
            invoice_registration_number
            or os.getenv("JP_INVOICE_REGISTRATION_NUMBER", "").strip()
            or "(未登録)"
        )

        breakdown = quotation_doc.get("breakdown", {})
        totals = quotation_doc.get("totals", {})
        lines: List[Dict[str, Any]] = breakdown.get("lines", [])

        doc = SimpleDocTemplate(
            output_pdf_path, pagesize=A4,
            leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36,
        )
        story = []

        title_style = ParagraphStyle(name='QTitle', fontName='HeiseiKakuGo-W5',
                                     fontSize=20, leading=24, alignment=1,
                                     textColor=colors.HexColor('#0F172A'), spaceAfter=10)
        label_style = ParagraphStyle(name=' QLabel', fontName='HeiseiKakuGo-W5',
                                     fontSize=8.5, leading=11, textColor=colors.HexColor('#334155'))
        value_style = ParagraphStyle(name='QValue', fontName='HeiseiMin-W3',
                                     fontSize=8.5, leading=11, textColor=colors.HexColor('#0F172A'))
        th_style = ParagraphStyle(name='QTh', fontName='HeiseiKakuGo-W5', fontSize=8,
                                  leading=10, alignment=1, textColor=colors.HexColor('#FFFFFF'))
        td_style = ParagraphStyle(name='QTd', fontName='HeiseiMin-W3', fontSize=8,
                                  leading=10, textColor=colors.HexColor('#111827'))
        td_num_style = ParagraphStyle(name='QTdNum', parent=td_style, alignment=2)
        note_style = ParagraphStyle(name='QNote', fontName='HeiseiMin-W3', fontSize=7,
                                    leading=9, textColor=colors.HexColor('#64748B'))

        story.append(Paragraph("お 見 積 書", title_style))

        date_str = datetime.now().strftime("%Y年 %m月 %d日")
        subject = subject_name or f"漏水修繕工事 ({project_id})"

        meta_html = (
            f"発行日: {date_str}<br/>"
            f"案件番号: {project_id}<br/>"
            f"件名: {subject}<br/>"
            f"登録番号: {invoice_reg_no} (適格請求書発行事業者)"
        )
        meta_table = Table([
            [Paragraph(meta_html, value_style),
             Table([[Paragraph(f"<font size='7'>【見積有効期限】</font><br/>発行日から30日間", label_style)]],
                   colWidths=[150], style=TableStyle([
                       ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#CBD5E1')),
                       ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                       ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                   ]))]
        ], colWidths=[330, 160], style=TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story.append(meta_table)
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"{client_name}", value_style))
        story.append(Spacer(1, 10))

        # --- 명산 테이블 ---
        header = [
            Paragraph("<b>品目コード</b>", th_style),
            Paragraph("<b>品目</b>", th_style),
            Paragraph("<b>工種</b>", th_style),
            Paragraph("<b>数量</b>", th_style),
            Paragraph("<b>単位</b>", th_style),
            Paragraph("<b>単価</b>", th_style),
            Paragraph("<b>金額</b>", th_style),
        ]
        rows = [header]
        max_rows = 22
        for line in lines[:max_rows]:
            rows.append([
                Paragraph(str(line.get("item_code", "-")), td_style),
                Paragraph(str(line.get("name_ja", "-")), td_style),
                Paragraph(str(line.get("category_work", "-")), td_style),
                Paragraph(f"{float(line.get('quantity', 0)):,.2f}", td_num_style),
                Paragraph(str(line.get("unit", "-")), td_num_style),
                Paragraph(_yen(line.get("unit_price", 0)), td_num_style),
                Paragraph(_yen(line.get("amount", 0)), td_num_style),
            ])
        if len(lines) > max_rows:
            rows.append([
                Paragraph("", td_style),
                Paragraph(f"…他 {len(lines) - max_rows}品目 (詳細は内訳書参照)", td_style),
                Paragraph("", td_style), Paragraph("", td_style),
                Paragraph("", td_style), Paragraph("", td_style), Paragraph("", td_style),
            ])

        col_widths = [58, 168, 48, 46, 30, 62, 78]
        detail_table = Table(rows, colWidths=col_widths, repeatRows=1)
        detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#94A3B8')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ]))
        story.append(detail_table)
        story.append(Spacer(1, 12))

        # --- 합계 블록 ---
        def summary_row(label: str, amount_key: str, bold: bool = False) -> list:
            style = ParagraphStyle(name=f'QS_{label}', parent=value_style,
                                   fontName='HeiseiKakuGo-W5' if bold else 'HeiseiMin-W3')
            return [Paragraph(label, style), Paragraph(_yen(totals.get(amount_key, 0)), td_num_style)]

        summary_data = [
            summary_row("直接工事費 小計", "direct_cost"),
            summary_row("共通仮設費", "construction_cost"),  # placeholder replaced below
        ]
        # 정확한 구성요소 표기
        summary_data = [
            summary_row("直接工事費", "direct_cost"),
            [Paragraph(f"共通仮設費 (率 {breakdown.get('rates', {}).get('common_temporary_rate', 0):.0%})", value_style),
             Paragraph(_yen(breakdown.get("common_temporary_cost", 0)), td_num_style)],
            summary_row("工事原価", "construction_cost", bold=True),
            [Paragraph(f"経費・一般管理費 (率 {breakdown.get('rates', {}).get('general_admin_rate', 0):.0%})", value_style),
             Paragraph(_yen(breakdown.get("expenses", 0)), td_num_style)],
            summary_row("課税対象額", "taxable_base"),
            summary_row("消費税 (10%)", "consumption_tax"),
        ]
        total_row = [
            Paragraph("総工事費 (税込)", ParagraphStyle(name='QTotalL', fontName='HeiseiKakuGo-W5',
                                                       fontSize=10, leading=13,
                                                       textColor=colors.HexColor('#FFFFFF'))),
            Paragraph(_yen(totals.get("total_including_tax", 0)),
                      ParagraphStyle(name='QTotalV', fontName='HeiseiKakuGo-W5', fontSize=10,
                                     leading=13, alignment=2, textColor=colors.HexColor('#FFFFFF'))),
        ]
        summary_table = Table(summary_data + [total_row], colWidths=[300, 130])
        summary_style = [
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#94A3B8')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#1E293B')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]
        summary_table.setStyle(TableStyle(summary_style))
        story.append(summary_table)
        story.append(Spacer(1, 14))

        default_notes = notes or [
            "本見積書の金額は、BIM三次元モデル(IFC)から自動算出した数量に基づく参考見積です。",
            "消費税率および諸率は単価マスタ(data/pricing)の設定に従います。",
            "数量は現地調査(数量取合書)により確定し、過不足は精算いたします。",
        ]
        for note in default_notes:
            story.append(Paragraph(f"・{note}", note_style))

        doc.build(story)
        logger.info(f"[QuotationPDF] Generated {output_pdf_path}")
        return output_pdf_path
