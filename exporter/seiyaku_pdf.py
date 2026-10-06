"""BIM図面審査 適合誓約書 PDF 생성기 — STATE G6.

국교성 BIM図面審査(2026-04-01)에 필요한 3종 중 誓約書를 프로젝트 산출물에서
자동 초안 생성한다. 나머지 2종(入出力基準 운용·表現標準 도면)은 체크리스트로 첨부.

정직성 원칙:
- 본 문서는 신청자申告 초안이다. 본 도구가 적합을 보증하지 않으며,
  최종 판단은 심사기관·유자격자가 한다 (문서 본문에 명기).
- IFC 파일명+SHA256을 기재해 산출물과 1:1로 묶는다. 해시 없는 誓約書는 발급하지 않는다.
- 日付는 Asia/Tokyo.
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import exporter.pdf_generator  # noqa: F401  (CID font patch 재사용)

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

DISCLAIMER_JA = (
    "本誓約書は申請者の申告に基づく書面であり、本ツールは適合を保証しません。"
    "最終判断は審査機関・有資格者（建築士）が行います。"
)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_seiyaku_pdf(
    project_id: str,
    ifc_path: str,
    checklist: List[Dict[str, Any]],
    applicant: str = "",
    output_pdf_path: Optional[str] = None,
) -> str:
    """適合誓約書 초안 PDF 생성. IFC 해시 없으면 발급 거부 (fail-closed)."""
    from pipeline.paths import OUTPUT_ROOT

    if not ifc_path or not os.path.exists(ifc_path):
        raise ValueError("IFC 산출물 없이 誓約書를 발급할 수 없습니다 (fail-closed)")
    if not checklist:
        raise ValueError("入出力基準 체크리스트 없이 誓約書를 발급할 수 없습니다")

    digest = _sha256_file(ifc_path)
    if not output_pdf_path:
        output_pdf_path = str(Path(OUTPUT_ROOT) / "projects" / project_id / "seiyaku.pdf")
    parent = os.path.dirname(os.path.abspath(output_pdf_path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
    body = ParagraphStyle("body", fontName="HeiseiKakuGo-W5", fontSize=10, leading=15)
    title = ParagraphStyle("title", fontName="HeiseiKakuGo-W5", fontSize=18,
                           leading=24, alignment=1, spaceAfter=12)
    small = ParagraphStyle("small", fontName="HeiseiKakuGo-W5", fontSize=8, leading=12)

    story = [
        Paragraph("適合誓約書（BIM図面審査）", title),
        Paragraph(f"作成日: {today} / プロジェクト: {project_id}", small),
        Spacer(1, 6),
        Paragraph(
            "下記の建築物に係る確認申請について、BIM図面審査の入出力基準に"
            "従って申請図書を作成したことを誓約します。", body),
        Spacer(1, 6),
    ]
    rows = [["No", "確認項目", "結果"]]
    for i, c in enumerate(checklist, 1):
        ok = "適合" if c.get("ok") else "要確認"
        rows.append([str(i), str(c.get("item_ja", "")), ok])
    t = Table(rows, colWidths=[30, 380, 70])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, "black"),
        ("FONTNAME", (0, 0), (-1, -1), "HeiseiKakuGo-W5"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story += [t, Spacer(1, 6)]

    story += [
        Paragraph(f"対象IFC: {os.path.basename(ifc_path)}", small),
        Paragraph(f"SHA256: {digest}", small),
        Paragraph(f"申請者: {applicant or '(未記入 — 署名欄に記名押印のこと)'}", body),
        Spacer(1, 12),
        Paragraph("署名欄: ____________________ 印", body),
        Spacer(1, 6),
        Paragraph(DISCLAIMER_JA, small),
    ]
    SimpleDocTemplate(output_pdf_path, pagesize=A4,
                      leftMargin=36, rightMargin=36).build(story)
    logger.info(f"[Seiyaku] {output_pdf_path} (ifc sha256 {digest[:12]}...)")
    return output_pdf_path
