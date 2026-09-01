# -*- coding: utf-8 -*-
"""
SP2 코드보수 회귀 테스트 (code_remediation_plan_v1.0 §4 P1 항목 검증)

A-1 회로차단기 half-open 회복 / A-2 실 ifcopenshell 경로 검증 /
L-3 구조화 facts 계약 / L-4 법령 판본 매니페스트 / A-5 스키마 드리프트 가드
"""
import asyncio
import json
import os
import time
from unittest.mock import MagicMock

import pytest

from harness.circuit_breaker import CircuitBreaker, circuit_breaker


# ================================================================
# A-1: 회로차단기 recovery_timeout 및 half-open 회복
# ================================================================
def test_a1_breaker_opens_after_threshold():
    br = circuit_breaker(failure_threshold=3, recovery_timeout=60)

    @br
    def boom():
        raise RuntimeError("x")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            boom()
    assert br.is_open is True


def test_a1_breaker_blocks_while_open():
    br = circuit_breaker(failure_threshold=2, recovery_timeout=3600)

    @br
    def boom():
        raise RuntimeError("x")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            boom()

    with pytest.raises(RuntimeError, match="Circuit breaker is OPEN"):
        boom()


def test_a1_breaker_recovers_after_timeout():
    """recovery_timeout 경과 후 HALF-OPEN 시험 호출이 성공하면 CLOSED로 완전 복구한다."""
    br = circuit_breaker(failure_threshold=3, recovery_timeout=0.05)

    state = {"fail": True}

    @br
    def flaky():
        if state["fail"]:
            raise RuntimeError("transient")
        return "ok"

    for _ in range(3):
        with pytest.raises(RuntimeError):
            flaky()
    assert br.is_open is True

    # 차단 상태 유지 확인 (타임아웃 전)
    with pytest.raises(RuntimeError, match="Circuit breaker is OPEN"):
        flaky()

    time.sleep(0.06)
    state["fail"] = False
    assert flaky() == "ok"
    assert br.is_open is False
    assert br.failures == 0


def test_a1_half_open_trial_failure_reopens():
    """HALF-OPEN 시험 호출이 실패하면 즉시 재차단된다."""
    br = circuit_breaker(failure_threshold=2, recovery_timeout=0.05)

    state = {"fail": True}

    @br
    def flaky():
        if state["fail"]:
            raise RuntimeError("still down")
        return "ok"

    for _ in range(2):
        with pytest.raises(RuntimeError):
            flaky()
    assert br.is_open is True

    time.sleep(0.06)
    # 재시도 실패 → 즉시 재OPEN
    with pytest.raises(RuntimeError, match="still down"):
        flaky()
    assert br.is_open is True
    # 재OPEN 후 타이머 리셋 확인 - 곧바로 호출하면 차단됨
    with pytest.raises(RuntimeError, match="Circuit breaker is OPEN"):
        flaky()


# ================================================================
# A-2: 실 ifcopenshell 경로 (샌드박스 워커 E2E)
# ================================================================
def test_a2_real_ifc_worker_via_sandbox(tmp_path):
    from engine.exporters.sandbox_runner import SandboxExporterRunner
    from pipeline.paths import OUTPUT_ROOT

    # 주의: 실 빌더(build_ifc_from_multi_floor)는 out/ 컨테인먼트 가드를 강제하므로
    # 산출물은 반드시 out/tmp 이내에 위치해야 한다.
    runner = SandboxExporterRunner(timeout_seconds=60.0)
    script = os.path.join(os.path.dirname(__file__), "..", "engine", "exporters", "ifc_worker.py")
    target = OUTPUT_ROOT / "tmp" / "worker_test.ifc"
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "target_path": str(target),
        "payload": {
            "rooms": [{"id": 1, "kind": "ldk",
                       "polygon": [{"x": 0, "y": 0}, {"x": 400, "y": 0},
                                    {"x": 400, "y": 300}, {"x": 0, "y": 300}],
                       "area_px2": 120000.0}],
            "walls": [{"id": 1, "p1": {"x": 0, "y": 0}, "p2": {"x": 400, "y": 0}}],
            "scale": {"pixel_to_mm": 5.0},
            "metadata": {}
        }
    }

    try:
        res = runner.run_isolated(script, payload)
        assert res.get("success") is True, f"real IFC worker failed: {res}"
        assert target.exists()

        import ifcopenshell
        model = ifcopenshell.open(str(target))
        assert len(model.by_type("IfcProject")) >= 1
        assert len(model.by_type("IfcSpace")) == 1
        assert model.schema == "IFC4"
    finally:
        if target.exists():
            target.unlink()


def test_a2_stub_exporters_removed():
    """가짜 스텁 익스포터가 저장소에서 완전히 제거되었는지 검증 (A-2 DoD: 스텁 파일 0건)."""
    base = os.path.join(os.path.dirname(__file__), "..")
    assert not os.path.exists(os.path.join(base, "engine", "exporters", "export_ifc.py"))
    assert not os.path.exists(os.path.join(base, "engine", "exporters", "export_step.py"))


# ================================================================
# L-3: 규칙 구조화 facts 계약
# ================================================================
def test_l3_lighting_rule_returns_facts():
    from compliance.rules import _evaluate_lighting

    room = {"kind": "LDK", "area_m2": 15.0, "actual_window_area_m2": 1.0}  # 15/7≈2.14 미달 → FAIL
    result = _evaluate_lighting(room, {})
    assert result["status"] == "FAIL"
    facts = result["facts"]
    assert facts["floor_area_m2"] == 15.0
    assert facts["window_area_m2"] == 1.0
    assert facts["required_window_area_m2"] == pytest.approx(15.0 / 7.0)
    assert facts["window_to_floor_ratio"] == pytest.approx(1.0 / 15.0)


def test_l3_ceiling_rule_returns_facts():
    from compliance.rules import _evaluate_ceiling_height

    room = {"kind": "BEDROOM", "height_mm": 2000.0}
    result = _evaluate_ceiling_height(room, {})
    assert result["status"] == "FAIL"
    assert result["facts"]["height_mm"] == 2000.0
    assert result["facts"]["required_height_mm"] == 2100.0


def test_l3_evaluator_passes_facts_through():
    from compliance.evaluator import evaluate_project

    data = {
        "rooms": [{"id": "r1", "kind": "LDK", "area_m2": 15.0,
                    "height_mm": 2400.0, "actual_window_area_m2": 3.0}],
        "openings": [],
        "metrics": {"px_to_m_scale": 0.01},
    }
    report = evaluate_project(data)
    evals = report["room_results"][0]["evaluations"]
    lighting = next(e for e in evals if e["rule_id"] == "RULE-JP-LAW-28")
    ceiling = next(e for e in evals if e["rule_id"] == "RULE-JP-ORD-21")
    assert lighting["facts"]["floor_area_m2"] == 15.0
    assert ceiling["facts"]["height_mm"] == 2400.0


def test_l3_checksheet_calculated_value_from_facts(monkeypatch):
    """체크시트가 reason 문자열이 아닌 facts로 BIM計測値를 조립하는지 E2E 검증."""
    from fastapi.testclient import TestClient
    from app.main import app

    project_id = "proj_sp2_l3"
    comp_dir = os.path.join("out", "projects", project_id)
    os.makedirs(comp_dir, exist_ok=True)
    comp_path = os.path.join(comp_dir, "page0_compliance.json")
    with open(comp_path, "w", encoding="utf-8") as f:
        json.dump({
            "rooms": [{"id": "room_1", "kind": "LDK", "area_m2": 14.0,
                       "height_mm": 2500.0,
                       "polygon": [{"x": 0, "y": 0}, {"x": 100, "y": 0},
                                    {"x": 100, "y": 100}, {"x": 0, "y": 100}],
                       "actual_window_area_m2": 3.5}],  # 14/7=2.0 이상 → PASS
            "openings": [],
            "metrics": {"px_to_m_scale": 0.01},
        }, f, ensure_ascii=False)

    fake_db = MagicMock()

    def make_chain(rows):
        """
        임의 길이의 PostgREST 체인을 지원하는 목.

        SP6/P0-1: 소유권 검증이 `.eq("id", ...).eq("user_id", ...)` 2단 체인으로
        바뀌었다. `.eq()` 가 자기 자신을 반환하도록 만들어 체인 길이에
        의존하지 않게 한다 (기존 목은 단일 .eq() 만 지원해 깨졌다).
        """
        chain = MagicMock()
        chain.execute.return_value = rows
        chain.eq.return_value = chain
        return chain

    def table(name):
        if name == "profiles":
            rows = MagicMock()
            rows.data = [{"id": "user_sp2", "plan_type": "free", "credits": 10}]
            t = MagicMock()
            t.select.return_value = make_chain(rows)
            t.update.return_value = make_chain(rows)
            return t
        if name == "projects":
            rows = MagicMock()
            rows.data = [{"id": project_id, "original_filename": "sp2_test.pdf"}]
            t = MagicMock()
            t.select.return_value = make_chain(rows)
            return t
        return MagicMock()

    fake_db.table.side_effect = table

    async def override():
        return {"user_id": "user_sp2", "db": fake_db}

    from app.api.deps import get_current_user_and_db
    app.dependency_overrides[get_current_user_and_db] = override
    try:
        client = TestClient(app)
        res = client.get(f"/api/v1/projects/{project_id}/compliance-checksheet?format=json")
        assert res.status_code == 200
        data = res.json()

        lighting = next(i for i in data["check_items"] if "第28条" in i["article_no"])
        # facts 기반 계측치: 3.5m²/14m² = 1/4.0
        assert "窓 3.50m²" in lighting["calculated_value"]
        assert "1/4.0" in lighting["calculated_value"]

        height = next(i for i in data["check_items"] if "令第21条" in i["article_no"])
        assert height["calculated_value"] == "2.50m"

        # L-4: 근거 법령 판본 표기 포함
        assert data.get("legal_basis") and "建築基準法" in data["legal_basis"]
    finally:
        app.dependency_overrides.pop(get_current_user_and_db, None)
        if os.path.exists(comp_path):
            os.remove(comp_path)


# ================================================================
# L-4: 법령 판본 매니페스트
# ================================================================
def test_l4_manifest_loaded_with_fixed_revisions():
    from app.api.v1.endpoints import _load_law_manifest, _legal_basis_note

    manifest = _load_law_manifest()
    law_ids = [l["law_id"] for l in manifest.get("laws", [])]
    assert "325AC0000000201" in law_ids      # 建築基準法
    assert "325CO0000000338" in law_ids      # 建築基準法施行令
    note = _legal_basis_note()
    assert "建築基準法" in note
    assert "昭和二十五年法律第二百一号" in note


# ================================================================
# A-5: 스키마 드리프트 정적 가드
# ================================================================
def test_a5_schema_contains_runtime_columns():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "supabase", "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read().lower()
    for col in ("plan_type", "credits", "stripe_subscription_id", "metadata jsonb"):
        assert col in sql, f"schema.sql missing runtime column: {col}"
