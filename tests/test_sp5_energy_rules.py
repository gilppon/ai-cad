# -*- coding: utf-8 -*-
"""
SP5 코드보수 회귀 테스트 (code_remediation_plan_v1.0 §6 SP5 - 建築物省エネ法 BEI 규칙)

공표 기준값 검증: 2026-04 중규모 비주거 인상(0.75/0.80/0.85), 대규모 2024-04,
주택·소규모 1.0. 판정 데이터 부재 시 가짜「適合」금지(N/A).
"""
import json
import os
from unittest.mock import MagicMock

import pytest

from compliance.rules_energy import (
    evaluate_energy_compliance,
    resolve_bei_threshold,
    LAW_META,
    STRENGTHENED_EFFECTIVE_DATE,
    USE_CATEGORY_THRESHOLDS,
)


# ================================================================
# 공표 기준값 자체 정합 (국토교통성 고시 수치 고정)
# ================================================================
def test_official_threshold_table():
    assert USE_CATEGORY_THRESHOLDS["factory"]["threshold"] == 0.75
    for cat in ("office", "school", "hotel", "department_store"):
        assert USE_CATEGORY_THRESHOLDS[cat]["threshold"] == 0.80
    for cat in ("hospital", "restaurant", "community_hall"):
        assert USE_CATEGORY_THRESHOLDS[cat]["threshold"] == 0.85
    assert STRENGTHENED_EFFECTIVE_DATE.isoformat() == "2026-04-01"
    assert LAW_META["law_id"] == "427AC0000000053"


# ================================================================
# 규모·용도·시점별 적용 기준 해석
# ================================================================
@pytest.mark.parametrize("area,use,jdate,expected", [
    # 중규모 비주거 - 2026-04 이후: 용도별 강화 기준
    (500, "factory",   "2026-04-01", 0.75),
    (1500, "office",   "2026-08-26", 0.80),
    (999, "school",    "2027-01-01", 0.80),
    (300, "hospital",  "2026-05-01", 0.85),
    # 중규모 비주거 - 2026-04 이전: 종전 기준 1.0
    (500, "factory",   "2026-03-31", 1.00),
    # 대규모 비주거 - 2024-04부터 이미 강화
    (2500, "office",   "2024-06-01", 0.80),
    (2500, "restaurant", "2024-04-01", 0.85),
    (2500, "office",   "2024-03-31", 1.00),
    # 소규모 비주거 / 주택: 1.0
    (100, "office",    "2027-01-01", 1.00),
])
def test_threshold_resolution_matrix(area, use, jdate, expected):
    res = resolve_bei_threshold(
        building_type="non_residential",
        use_category=use,
        total_floor_area_m2=area,
        judgment_date=jdate,
    )
    assert res["threshold"] == pytest.approx(expected)


def test_residential_and_missing_area_defaults():
    res_home = resolve_bei_threshold(building_type="residential",
                                     use_category=None, total_floor_area_m2=135.0)
    assert res_home["threshold"] == pytest.approx(1.0)
    res_unknown = resolve_bei_threshold(building_type="non_residential",
                                        use_category="office", total_floor_area_m2=None)
    assert res_unknown["threshold"] == pytest.approx(1.0)


# ================================================================
# BEI 판정 본체
# ================================================================
def _section(design, baseline, **kw):
    base = {
        "building_type": "non_residential",
        "use_category": "office",
        "total_floor_area_m2": 800.0,
        "design_primary_energy_mj_per_year": design,
        "baseline_primary_energy_mj_per_year": baseline,
        "judgment_date": kw.pop("judgment_date", "2026-08-26"),
    }
    base.update(kw)
    return base


def test_bei_pass_fail_boundary():
    # office(중규모, 2026-04+) → 0.80 / baseline 100,000 가정
    ok = evaluate_energy_compliance(_section(78_000, 100_000))
    assert ok["status"] == "PASS" and ok["facts"]["bei"] == pytest.approx(0.78)

    boundary = evaluate_energy_compliance(_section(80_000, 100_000))
    assert boundary["status"] == "PASS" and boundary["facts"]["bei"] == pytest.approx(0.80)  # ≤ 포함

    fail = evaluate_energy_compliance(_section(81_000, 100_000))
    assert fail["status"] == "FAIL" and fail["facts"]["bei"] == pytest.approx(0.81)
    assert "0.80" in fail["standard_value"]
    # FAIL 소견은 재검토 지시를 포함 (판정 위조 아님)
    assert "再検討" in fail["inspector_comment"]


def test_missing_data_is_na_never_fake_pass():
    item = evaluate_energy_compliance({
        "building_type": "non_residential",
        "use_category": "office",
        "total_floor_area_m2": 500.0,
        # 에너지 수치 누락
        "judgment_date": "2026-08-26",
    })
    assert item["status"] == "N/A"
    assert item["calculated_value"] == "-"
    assert "自動判定を実施できません" in item["inspector_comment"]


def test_residential_judgment():
    item = evaluate_energy_compliance({
        "building_type": "residential",
        "total_floor_area_m2": 120.0,
        "design_primary_energy_mj_per_year": 9_000,
        "baseline_primary_energy_mj_per_year": 10_000,
    })
    assert item["status"] == "PASS"
    assert item["facts"]["threshold"] == 1.0


# ================================================================
# 매니페스트 등재 확인
# ================================================================
def test_manifest_contains_shoene_law():
    manifest_path = os.path.join("data", "laws", "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    law_ids = {l["law_id"] for l in manifest["laws"]}
    assert "427AC0000000053" in law_ids
    notes = " ".join(manifest.get("notes", []))
    assert "0.75" in notes and "0.85" in notes  # 확증 기록 존재


# ================================================================
# 체크시트 E2E: energy 섹션 → 항목 추가 + 不適合 강등
# ================================================================
class FakeTable:
    def __init__(self, rows): self._rows = rows
    def select(self, *a): return self
    def update(self, rec):
        for r in self._rows: r.update(rec)
        return self
    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self
    def execute(self):
        class R: pass
        R.data = list(self._rows)
        return R()


def test_checksheet_energy_section_e2e(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    project_id = "proj_sp5_energy"
    comp_dir = os.path.join("out", "projects", project_id)
    os.makedirs(comp_dir, exist_ok=True)
    comp_path = os.path.join(comp_dir, "page0_compliance.json")

    with open(comp_path, "w", encoding="utf-8") as f:
        json.dump({
            "rooms": [{"id": "r1", "kind": "LDK", "area_m2": 20.0,
                       "height_mm": 2400.0, "actual_window_area_m2": 4.0}],
            "openings": [],
            "metrics": {"px_to_m_scale": 0.01},
            "energy": {
                "building_type": "non_residential",
                "use_category": "factory",
                "total_floor_area_m2": 600.0,
                "design_primary_energy_mj_per_year": 90_000,
                "baseline_primary_energy_mj_per_year": 100_000,
                "judgment_date": "2026-08-26",
            },
        }, f, ensure_ascii=False)

    fake_db = MagicMock()

    def table(name):
        if name == "profiles":
            return FakeTable([{"id": "user_sp5", "plan_type": "free", "credits": 10}])
        if name == "projects":
            # SP6/P0-1: 소유권 필터 .eq("user_id", ...) 가 강제되므로 user_id 필수
            return FakeTable([
                {"id": project_id, "user_id": "user_sp5", "original_filename": "sp5.pdf"}
            ])
        return FakeTable([])

    fake_db.table.side_effect = table

    async def override():
        return {"user_id": "user_sp5", "db": fake_db}

    from app.api.deps import get_current_user_and_db
    app.dependency_overrides[get_current_user_and_db] = override
    try:
        client = TestClient(app)
        res = client.get(f"/api/v1/projects/{project_id}/compliance-checksheet?format=json")
        assert res.status_code == 200
        data = res.json()

        energy_items = [i for i in data["check_items"] if "省エネ法" in i["article_no"]]
        assert len(energy_items) == 1
        e = energy_items[0]
        assert e["status"] == "FAIL"          # factory 0.90 > 0.75
        assert "BEI = 0.90" in e["calculated_value"]
        assert data["overall_judgment"] == "不適合"  # FAIL 시 강등
        assert data.get("legal_basis")  # L-4 근거 표기 유지
    finally:
        app.dependency_overrides.pop(get_current_user_and_db, None)
        if os.path.exists(comp_path):
            os.remove(comp_path)
