# -*- coding: utf-8 -*-
"""入出力基準 체크리스트 게이트: 기계확인만 True, 사람 몫은 要確認."""
from __future__ import annotations

import tempfile
from pathlib import Path


def _sample_ifc() -> str:
    from parser.export_ifc import build_ifc_from_multi_floor
    from pipeline.paths import OUTPUT_ROOT
    out = OUTPUT_ROOT / "tmp" / "checklist_gate.ifc"
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


def test_checklist_machine_items_true_for_valid_ifc():
    from compliance.bim_checklist import build_nyushutsuryoku_checklist
    items = build_nyushutsuryoku_checklist(_sample_ifc(), pdf_ready=True)
    by_item = {c["item_ja"]: c for c in items}
    assert by_item["IFC2X3による提出"]["ok"] is True
    assert by_item["IfcProject・IfcSpaceの存在"]["ok"] is True
    assert by_item["PDF申請図書の同時提出"]["ok"] is True


def test_checklist_human_items_always_require_confirmation():
    from compliance.bim_checklist import build_nyushutsuryoku_checklist
    items = build_nyushutsuryoku_checklist(_sample_ifc(), pdf_ready=True)
    by_item = {c["item_ja"]: c for c in items}
    assert by_item["確認申請図書表現標準への準拠（目視）"]["ok"] is False
    assert by_item["確認申請用CDEへの取込"]["ok"] is False


def test_checklist_without_ifc_is_all_unconfirmed():
    from compliance.bim_checklist import build_nyushutsuryoku_checklist
    items = build_nyushutsuryoku_checklist(None)
    machine = [c for c in items if "IFC" in c["item_ja"] or "Ifc" in c["item_ja"]]
    assert all(c["ok"] is False for c in machine)


def test_checklist_feeds_seiyaku():
    from compliance.bim_checklist import build_nyushutsuryoku_checklist
    from exporter.seiyaku_pdf import generate_seiyaku_pdf
    import os
    items = build_nyushutsuryoku_checklist(_sample_ifc(), pdf_ready=False)
    pdf = os.path.join(tempfile.mkdtemp(), "seiyaku2.pdf")
    out = generate_seiyaku_pdf("gate-proj2", _sample_ifc(), items, output_pdf_path=pdf)
    assert os.path.exists(out)
