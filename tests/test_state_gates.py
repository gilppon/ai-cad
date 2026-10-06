"""STATE Phase 0~2 게이트 테스트: 新2号분류 / BELS / 盛土·소방 / engine 배선 / CORS."""
from __future__ import annotations


def test_shin_go_new2_wooden_2f():
    from compliance.rules_building import classify_new_go
    r = classify_new_go("wooden", 2, 120.0)
    assert r["category"] == "new-2go"
    assert r["structural_docs_required"] is True


def test_shin_go_new3_wooden_1f_small():
    from compliance.rules_building import classify_new_go
    r = classify_new_go("wooden", 1, 150.0)
    assert r["category"] == "new-3go"
    assert r["structural_docs_required"] is False


def test_shin_go_new2_1f_over_200():
    from compliance.rules_building import classify_new_go
    r = classify_new_go("wooden", 1, 250.0)
    assert r["category"] == "new-2go"


def test_shin_go_unknown_is_safe_side():
    from compliance.rules_building import classify_new_go
    r = classify_new_go("wooden", 2, None)
    assert r["structural_docs_required"] is True
    # 1층이어도 면적 미입력 시 특례 추정 금지 (fail-open 방지)
    r1 = classify_new_go("wooden", 1, None)
    assert r1["category"] == "unknown"
    assert r1["structural_docs_required"] is True


def test_bels_mapping_and_cap():
    from compliance.rules_bels import rate_bels_stars
    assert rate_bels_stars(0.45, True, True)["stars"] == 6
    assert rate_bels_stars(0.65, True, False)["stars"] == 4  # 상한 아님 (원래 4)
    capped = rate_bels_stars(0.45, True, False)
    assert capped["stars"] == 4  # 재에네無 주택 상한
    assert rate_bels_stars(None)["stars"] is None
    assert rate_bels_stars(1.2)["stars"] == 0


def test_site_checks_never_pass():
    from compliance.rules_site import check_morido_regulation, check_fire_and_ordinance
    for v in (True, False, None):
        assert check_morido_regulation(v)["status"] == "N/A"
    assert check_fire_and_ordinance()["status"] == "N/A"
    assert "判定を確定しません" in check_fire_and_ordinance()["comment_ja"]


def test_engine_pslg_wired_flag():
    import core.engine as ce
    assert hasattr(ce, "_ENGINE_PSLG_AVAILABLE")
    # engine 패키지가 있으면 True, 없어도 import 실패 없이 False
    assert isinstance(ce._ENGINE_PSLG_AVAILABLE, bool)


def test_cors_headers_whitelisted():
    from app.main import app
    middlewares = [m for m in app.user_middleware]
    assert middlewares, "CORS middleware missing"
    # allow_headers에 와일드카드가 없어야 함
    import app.main as main_mod
    import inspect
    src = inspect.getsource(main_mod)
    assert 'allow_headers=["*"]' not in src
    assert "Authorization" in src


def test_no_dummy_room_result():
    import core.engine as ce
    assert not hasattr(ce.PipelineEngine, "_get_dummy_room_result")


def test_worker_requires_user_id():
    import inspect
    from app.worker.tasks import process_pdf_task
    sig = inspect.signature(process_pdf_task.run if hasattr(process_pdf_task, "run") else process_pdf_task)
    assert "user_id" in sig.parameters


def test_ifc_schema_is_2x3():
    from parser.export_ifc import build_ifc_from_multi_floor
    from pipeline.paths import OUTPUT_ROOT
    payload = {
        "rooms": [{"id": 1, "kind": "living",
                   "polygon": [{"x": 0, "y": 0}, {"x": 3000, "y": 0},
                               {"x": 3000, "y": 3000}, {"x": 0, "y": 3000}]}],
        "walls": [{"p1": {"x": 0, "y": 0}, "p2": {"x": 3000, "y": 0}, "thickness_mm": 120}],
        "metadata": {},
        "scale": {"pixel_to_mm": 1.0},
    }
    out = OUTPUT_ROOT / "state_gate_probe.ifc"
    build_ifc_from_multi_floor([payload], out_ifc=str(out))
    try:
        import ifcopenshell
        model = ifcopenshell.open(str(out))
        assert model.schema == "IFC2X3"
        assert len(model.by_type("IfcProject")) >= 1
    finally:
        try:
            out.unlink()
            (out.parent / (out.name + ".meta.json")).unlink()
        except OSError:
            pass
