# -*- coding: utf-8 -*-
"""STATE G6 誓約書 게이트: IFC 해시 없으면 발급 거부, 산출물·면책 포함."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


def _sample_ifc(tmp: Path) -> str:
    from parser.export_ifc import build_ifc_from_multi_floor
    from pipeline.paths import OUTPUT_ROOT
    out = OUTPUT_ROOT / "tmp" / "seiyaku_gate.ifc"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "rooms": [{"id": 1, "kind": "ldk",
                   "polygon": [{"x": 0, "y": 0}, {"x": 400, "y": 0},
                               {"x": 400, "y": 300}, {"x": 0, "y": 300}]}],
        "walls": [{"p1": {"x": 0, "y": 0}, "p2": {"x": 400, "y": 0}, "thickness_mm": 120}],
        "metadata": {},
        "scale": {"pixel_to_mm": 5.0},
    }
    build_ifc_from_multi_floor([payload], out_ifc=str(out))
    return str(out)


CHECKLIST = [
    {"item_ja": "入出力基準に従ったBIM運用", "ok": True},
    {"item_ja": "確認申請図書表現標準に準拠した図面出力", "ok": True},
    {"item_ja": "IFC2X3 + PDF同時提出", "ok": False},
]


def test_seiyaku_generates_with_hash_and_disclaimer():
    from exporter.seiyaku_pdf import generate_seiyaku_pdf
    ifc = _sample_ifc(Path(tempfile.mkdtemp()))
    pdf = os.path.join(tempfile.mkdtemp(), "seiyaku.pdf")
    out = generate_seiyaku_pdf("gate-proj", ifc, CHECKLIST, applicant="山田工務店", output_pdf_path=pdf)
    assert os.path.exists(out) and os.path.getsize(out) > 1000


def test_seiyaku_refuses_without_ifc():
    from exporter.seiyaku_pdf import generate_seiyaku_pdf
    with pytest.raises(ValueError):
        generate_seiyaku_pdf("gate-proj", "/nonexistent/x.ifc", CHECKLIST)


def test_seiyaku_refuses_without_checklist():
    from exporter.seiyaku_pdf import generate_seiyaku_pdf
    ifc = _sample_ifc(Path(tempfile.mkdtemp()))
    with pytest.raises(ValueError):
        generate_seiyaku_pdf("gate-proj", ifc, [])
