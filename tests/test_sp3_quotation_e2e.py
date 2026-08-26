# -*- coding: utf-8 -*-
"""
SP3 코드보수 회귀 테스트 (code_remediation_plan_v1.0 §3/§4 Q-1, Q-2 검증)

BIM 적산(takeoff) → 단가(pricing) → 내역(breakdown) → 견적 문서/PDF → IFC Pset 부착
"""
import json
import math
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from takeoff.overlap_resolver import resolve_wall_overlaps
from takeoff.quantities import (
    takeoff_from_payload, summarize_by_basis,
    FLOOR_AREA, CEIL_AREA, WALL_LENGTH, WALL_AREA, ROOM_COUNT,
)
from pricing.unit_price_book import UnitPriceBook, PricingError
from pricing.breakdown import build_breakdown

# ----------------------------------------------------------------
# 공용 픽스처: 10m × 8m 직사각형 2룸 + 벽 4본 (pixel_to_mm=5.0 → 1px=5mm)
# ----------------------------------------------------------------
def make_payload() -> dict:
    return {
        "page_index": 0,
        "scale": {"pixel_to_mm": 5.0},
        "metadata": {"floor_height_mm": 2400.0},
        "rooms": [
            {"id": 1, "kind": "ldk",
             "polygon": [{"x": 0, "y": 0}, {"x": 2000, "y": 0}, {"x": 2000, "y": 1600}, {"x": 0, "y": 1600}],
             "area_px2": 2000 * 1600},
            {"id": 2, "kind": "balcony",
             "polygon": [{"x": 2000, "y": 0}, {"x": 3600, "y": 0}, {"x": 3600, "y": 800}, {"x": 2000, "y": 800}],
             "area_px2": 1600 * 800},
        ],
        "walls": [
            {"id": 1, "p1": {"x": 0, "y": 0}, "p2": {"x": 2000, "y": 0}, "thickness_px": 10},
            {"id": 2, "p1": {"x": 2000, "y": 0}, "p2": {"x": 2000, "y": 1600}, "thickness_px": 10},
            {"id": 3, "p1": {"x": 2000, "y": 1600}, "p2": {"x": 0, "y": 1600}, "thickness_px": 10},
            # 중복 세그먼트 (역방향) → 제거 대상
            {"id": 4, "p1": {"x": 0, "y": 1600}, "p2": {"x": 0, "y": 0}, "thickness_px": 10},
            {"id": 5, "p1": {"x": 0, "y": 0}, "p2": {"x": 2000, "y": 0}, "thickness_px": 10},
        ],
    }


@pytest.fixture(scope="module")
def book():
    return UnitPriceBook.load()


# ================================================================
# A) 包絡処理 - 중복 제거 및 코너 공제
# ================================================================
def test_overlap_resolver_dedup_and_corner():
    walls = make_payload()["walls"]
    resolved = resolve_wall_overlaps(walls)
    # 5본 중 1본은 역방향 중복 → 4본만 남음 (id=4는 유니크이므로 4본: 1,2,3,4 / id=5 제거)
    ids = {r.wall_id for r in resolved}
    assert 5 not in ids and len(resolved) == 4

    # 모든 벽 양끝이 맞닿아 있으므로 각 벽 2개 끝단 공제 적용
    for r in resolved:
        assert r.corner_deductions_px == 2
    # 코너 보정 후 순연장 = raw - thickness(두께 기본 0이므로 여기선 raw와 동일해야 함)
    assert all(r.length_px <= r.raw_length_px for r in resolved)


def test_overlap_corner_deduction_math():
    """L자로 맞닿은 두 벽: 각 끝단에서 두께 절반씩 공제되는지 정밀 검증."""
    walls = [
        {"id": 1, "p1": {"x": 0, "y": 0}, "p2": {"x": 1000, "y": 0}, "thickness_px": 20},
        {"id": 2, "p1": {"x": 1000, "y": 0}, "p2": {"x": 1000, "y": 500}, "thickness_px": 20},
    ]
    resolved = resolve_wall_overlaps(walls)
    by_id = {r.wall_id: r for r in resolved}
    # wall1: p1 고립, p2 공유 → 공제 1회 (10px)
    assert by_id[1].corner_deductions_px == 1
    assert by_id[1].length_px == pytest.approx(1000 - 10)
    assert by_id[2].length_px == pytest.approx(500 - 10)


# ================================================================
# B) 수량 산출 - 물리량·역추적·정합성
# ================================================================
def test_takeoff_quantities_traceable():
    payload = make_payload()
    lines = takeoff_from_payload(payload)

    floors = summarize_by_basis(lines)
    px_to_m = 0.005
    expected_total_m2 = (2000 * 1600 + 1600 * 800) * (px_to_m ** 2)
    assert floors[FLOOR_AREA] == pytest.approx(expected_total_m2, rel=1e-6)
    assert floors[CEIL_AREA] == pytest.approx(expected_total_m2, rel=1e-6)
    assert floors[ROOM_COUNT] == 2.0

    # 역추적 계약: 모든 라인이 원천 참조를 가진다
    for l in lines:
        assert l.source_ref is not None
        if l.basis in (FLOOR_AREA, CEIL_AREA):
            assert l.source_kind == "room"

    # 부위 필터용 part 기록 확인
    balcony_floor = [l for l in lines if l.basis == FLOOR_AREA and l.part == "balcony"]
    assert len(balcony_floor) == 1
    assert balcony_floor[0].quantity == pytest.approx(1600 * 800 * px_to_m ** 2)


def test_takeoff_wall_area_uses_storey_height():
    payload = make_payload()
    payload["walls"] = [{"id": 9, "p1": {"x": 0, "y": 0}, "p2": {"x": 1000, "y": 0}}]  # 1000px = 5m
    lines = [l for l in takeoff_from_payload(payload) if l.source_kind == "wall"]
    length = next(l for l in lines if l.basis == WALL_LENGTH)
    area = next(l for l in lines if l.basis == WALL_AREA)
    assert length.quantity == pytest.approx(5.0)
    assert area.quantity == pytest.approx(5.0 * 2.4)  # 층고 2400mm


# ================================================================
# C) 단가 마스터 fail-closed
# ================================================================
def test_pricebook_rejects_unknown_item_code():
    book = UnitPriceBook.load()
    with pytest.raises(PricingError):
        book.get_item("NO-SUCH-CODE")


def test_pricebook_rejects_bad_schema(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "schema_version": "9.9", "currency": "JPY",
        "consumption_tax_rate": 0.1, "common_temporary_rate": 0.15,
        "general_admin_rate": 0.12,
        "work_items": [{"item_code": "X", "name_ja": "x", "basis": "FLOOR-AREA", "unit": "m²", "unit_price": 100}],
    }), encoding="utf-8")
    with pytest.raises(PricingError):
        UnitPriceBook.load(bad)


# ================================================================
# D) 내역서 수학 - 세율 구조 정밀 검증
# ================================================================
def test_breakdown_math_exact(book):
    payload = make_payload()
    lines = takeoff_from_payload(payload)
    breakdown = build_breakdown(lines, book)

    direct = sum(l["amount"] for l in breakdown["lines"])
    assert breakdown["direct_cost"] == direct
    expected_temporary = math.floor(direct * 0.15 + 0.5)
    assert breakdown["common_temporary_cost"] == expected_temporary
    assert breakdown["construction_cost"] == direct + expected_temporary
    expected_expenses = math.floor((direct + expected_temporary) * 0.12 + 0.5)
    assert breakdown["expenses"] == expected_expenses
    taxable = direct + expected_temporary + expected_expenses
    assert breakdown["taxable_base"] == taxable
    assert breakdown["consumption_tax"] == math.floor(taxable * 0.10 + 0.5)
    assert breakdown["total_including_tax"] == taxable + breakdown["consumption_tax"]

    # 부위 필터 검증: 발코니 방수(WTR-01)는 balcony 면적으로만 계상
    wtr01 = next(l for l in breakdown["lines"] if l["item_code"] == "WTR-01")
    px_to_m = 0.005
    assert wtr01["quantity"] == pytest.approx(1600 * 800 * px_to_m ** 2, rel=1e-6)


# ================================================================
# E) API E2E - 견적 JSON/PDF
# ================================================================
class FakeTable:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *a): return self

    def update(self, rec):
        for r in self._rows:
            r.update(rec)
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def execute(self):
        class R: pass
        R.data = list(self._rows)
        return R()


def _override_deps(project_id: str):
    fake_db = MagicMock()

    def table(name):
        if name == "profiles":
            return FakeTable([{"id": "user_sp3", "plan_type": "free", "credits": 50}])
        return FakeTable([{"id": project_id}])

    fake_db.table.side_effect = table

    async def override():
        return {"user_id": "user_sp3", "db": fake_db}

    from app.api.deps import get_current_user_and_db
    app.dependency_overrides[get_current_user_and_db] = override
    return get_current_user_and_db


PROJECT_SP3 = "proj_sp3_quote"


@pytest.fixture()
def quotation_project(monkeypatch):
    monkeypatch.setenv("PAYMENT_ALLOW_MOCK_WEBHOOK", "")  # 미사용 명시
    project_dir = os.path.join("out", "projects", PROJECT_SP3)
    os.makedirs(project_dir, exist_ok=True)
    with open(os.path.join(project_dir, "page0_rooms.json"), "w", encoding="utf-8") as f:
        json.dump(make_payload(), f, ensure_ascii=False)
    yield
    app.dependency_overrides.clear()


def test_api_quotation_e2e(quotation_project):
    from pipeline.paths import OUTPUT_ROOT

    key = _override_deps(PROJECT_SP3)
    try:
        client = TestClient(app)

        res = client.post(f"/api/v1/projects/{PROJECT_SP3}/quotation")
        assert res.status_code == 200, res.text
        doc = res.json()

        assert doc["document_kind"] == "quotation"
        assert doc["currency"] == "JPY"
        assert len(doc["quantities"]) > 0
        assert all(q["source_ref"] is not None for q in doc["quantities"])
        assert doc["totals"]["total_including_tax"] > 0

        # 결정론성: 재요청 시 동일 총액
        res2 = client.post(f"/api/v1/projects/{PROJECT_SP3}/quotation")
        assert res2.status_code == 200
        assert res2.json()["totals"]["total_including_tax"] == doc["totals"]["total_including_tax"]

        # 저장된 원장 확인
        saved = OUTPUT_ROOT / "projects" / PROJECT_SP3 / "quotation.json"
        assert saved.exists()

        # PDF 다운로드
        res_pdf = client.get(f"/api/v1/projects/{PROJECT_SP3}/quotation.pdf")
        assert res_pdf.status_code == 200
        assert res_pdf.headers["content-type"] == "application/pdf"
        assert res_pdf.content.startswith(b"%PDF")
        assert len(res_pdf.content) > 1500

        # 미변환 프로젝트 → 404
        res404 = client.post("/api/v1/projects/proj_sp3_none/quotation")
        assert res404.status_code == 404
    finally:
        app.dependency_overrides.pop(key, None)


# ================================================================
# F) Q-2: IFC Pset 부착 + 재파싱 검증
# ================================================================
def test_q2_ifc_pset_enrichment_roundtrip(tmp_path):
    from parser.export_ifc import build_ifc_from_meta
    from takeoff.ifc_enrichment import enrich_ifc_with_quantities, read_back_psets

    # 실 빌더는 out/ 컨테인먼트 가드를 강제하므로 산출물을 out/tmp에 둔다
    from pipeline.paths import OUTPUT_ROOT
    target = OUTPUT_ROOT / "tmp" / "sp3_enrich.ifc"
    target.parent.mkdir(parents=True, exist_ok=True)
    meta_path = str(target) + ".meta.json"

    try:
        build_ifc_from_meta(make_payload(), out_ifc=str(target), out_meta=meta_path)

        lines = takeoff_from_payload(make_payload())
        result = enrich_ifc_with_quantities(str(target), [make_payload()], [lines])
        assert result["spaces_tagged"] == 2
        assert result["psets_written"] >= 2

        psets = read_back_psets(str(target))
        space_entries = {k: v for k, v in psets.items() if "Space" in k}
        assert len(space_entries) >= 2
        sample = next(iter(space_entries.values()))
        assert "Basis_FloorArea_m2" in sample
    finally:
        for p in (target, Path(str(target) + ".meta.json")):
            if Path(p).exists():
                Path(p).unlink()
