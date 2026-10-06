"""BIM図面審査 入出力基準チェックリスト 생성기 — STATE G6 증거분.

機械가 확인할 수 있는 것만 True로 한다. 目視·CDE取込 등 사람 몫은
ok=False + 要確認으로 명시한다. 전부 True인 가짜 체크리스트는 만들지 않는다.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def build_nyushutsuryoku_checklist(
    ifc_path: Optional[str] = None,
    pdf_ready: bool = False,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    schema_ok = False
    has_project_space = False
    basis = "IFC 미지정"
    if ifc_path and os.path.exists(ifc_path):
        try:
            import ifcopenshell
            model = ifcopenshell.open(ifc_path)
            schema_ok = (model.schema == "IFC2X3")
            has_project_space = (len(model.by_type("IfcProject")) >= 1
                                 and len(model.by_type("IfcSpace")) >= 1)
            basis = f"schema={model.schema}"
        except Exception as e:
            basis = f"IFC 판독 실패: {e}"

    items.append({"item_ja": "IFC2X3による提出", "ok": schema_ok,
                  "basis_ja": basis})
    items.append({"item_ja": "IfcProject・IfcSpaceの存在", "ok": has_project_space,
                  "basis_ja": basis})
    items.append({"item_ja": "PDF申請図書の同時提出", "ok": bool(pdf_ready),
                  "basis_ja": "提出時に確認" if pdf_ready else "要確認（目視）"})
    items.append({"item_ja": "確認申請図書表現標準への準拠（目視）", "ok": False,
                  "basis_ja": "要確認（目視）"})
    items.append({"item_ja": "確認申請用CDEへの取込", "ok": False,
                  "basis_ja": "要確認（ArcSync等で取込テスト）"})
    return items
