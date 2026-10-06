# -*- coding: utf-8 -*-
"""
Phase 1 - Step 1-1: Module-level unit verification
"""
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "[PASS]"
FAIL = "[FAIL]"
results = []

def test(name, func):
    try:
        func()
        results.append((name, PASS, ""))
        print("  {} {}".format(PASS, name))
    except Exception as e:
        results.append((name, FAIL, str(e)))
        print("  {} {}: {}".format(FAIL, name, e))

print("=" * 60)
print("Phase 1 - Step 1-1: Module Unit Verification")
print("=" * 60)

# --- 1. domain ---
print("\n[1] domain/models.py")
def t_domain():
    from domain.models import Room, Wall, Point, RoomKind, LeakCase
    p = Point(x=1.0, y=2.0)
    assert p.x == 1.0
    r = Room(id=1, polygon=[p], kind=RoomKind.LDK)
    assert r.kind == RoomKind.LDK
    w = Wall(id=1, p1=Point(0,0), p2=Point(100,0))
    assert w.kind == "STRUCTURAL"
    lc = LeakCase(case_id="TEST-001")
    assert lc.case_id == "TEST-001"
test("domain.models - all classes", t_domain)

def t_domain_init():
    from domain import Room, Wall, Point, RoomKind, LeakCase
    assert Room is not None
test("domain.__init__ - re-export", t_domain_init)

# --- 2. pipeline ---
print("\n[2] pipeline/contracts.py")
def t_contracts_build():
    from pipeline.contracts import build_geometry_payload, validate_geometry_payload
    payload = build_geometry_payload(
        page=0,
        canvas={"width": 1000, "height": 800},
        rooms=[{"id": 1, "kind": "unknown", "polygon": []}],
    )
    assert payload["kind"] == "geometry_payload"
    assert payload["rooms_count"] == 1
    validate_geometry_payload(payload)
test("contracts - build + validate GeometryPayload", t_contracts_build)

def t_contracts_export():
    from pipeline.contracts import build_export_metadata, validate_export_metadata
    meta = build_export_metadata(
        page_index=0,
        rooms=[{"id": 1}],
        walls=[{"id": 1}],
        doors=[],
        edges=[],
        params={"wall_height_mm": 2400},
    )
    validate_export_metadata(meta)
test("contracts - build + validate ExportMetadata", t_contracts_export)

# --- 3. pipeline/paths ---
print("\n[3] pipeline/paths.py")
def t_paths():
    from pipeline.paths import resolve_output_path, resolve_project_path, PROJECT_ROOT, OUTPUT_ROOT
    # Output path must be under out/ directory
    out = resolve_output_path(str(OUTPUT_ROOT / "test_output.json"))
    assert str(out).endswith("test_output.json")
    # Project path must be under project root
    proj = resolve_project_path(str(PROJECT_ROOT / "samples" / "sample.pdf"))
    assert str(proj).endswith("sample.pdf")
    # Verify security: paths outside root should be rejected
    try:
        resolve_output_path("C:/tmp/evil.json")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass  # Expected - security guard works!
    print("      -> Security guard: WORKING")
test("paths - resolve + security guard", t_paths)

# --- 4. harness ---
print("\n[4] harness/circuit_breaker.py")
def t_cb_class():
    from harness.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker(max_failures=2)
    @cb
    def always_ok():
        return 42
    assert always_ok() == 42
test("CircuitBreaker - normal call", t_cb_class)

def t_cb_factory():
    from harness.circuit_breaker import circuit_breaker
    @circuit_breaker(failure_threshold=3, recovery_timeout=60)
    def test_func():
        return "ok"
    assert test_func() == "ok"
test("circuit_breaker() - factory decorator", t_cb_factory)

def t_cb_trip():
    from harness.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker(max_failures=2)
    @cb
    def always_fail():
        raise ValueError("boom")
    # Trip it
    for _ in range(2):
        try:
            always_fail()
        except ValueError:
            pass
    # Now it should be open
    try:
        always_fail()
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "OPEN" in str(e)
test("CircuitBreaker - trip after max failures", t_cb_trip)

# --- 5. parser/pdf_type ---
print("\n[5] parser/pdf_type.py")
def t_pdf_type():
    from parser.pdf_type import detect_pdf_type
    result = detect_pdf_type("samples/sample.pdf")
    assert "pdf_type" in result
    assert result["pdf_type"] in ("image", "vector", "unknown")
    print("      -> PDF type: {}, confidence: {}".format(result["pdf_type"], result.get("confidence")))
test("pdf_type - sample PDF detection", t_pdf_type)

# --- 6. parser/room_detect ---
print("\n[6] parser/room_detect.py")
def t_room_detect_import():
    from parser.room_detect import detect_rooms, detect_rooms_from_walls, RoomResult
    assert callable(detect_rooms)
    assert callable(detect_rooms_from_walls)
test("room_detect - import OK", t_room_detect_import)

# --- 7. parser/image_outline ---
print("\n[7] parser/image_outline.py")
def t_image_outline_import():
    from parser.image_outline import extract_room_result_from_page, extract_outlines_from_image_pdf
    assert callable(extract_room_result_from_page)
    assert callable(extract_outlines_from_image_pdf)
test("image_outline - import OK", t_image_outline_import)

# --- 8. parser/room_export ---
print("\n[8] parser/room_export.py")
def t_room_export_import():
    from parser.room_export import rooms_to_json_dict, save_rooms_json
    assert callable(rooms_to_json_dict)
    assert callable(save_rooms_json)
test("room_export - import OK", t_room_export_import)

# --- 9. parser/export_ifc ---
print("\n[9] parser/export_ifc.py")
def t_export_ifc_import():
    from parser.export_ifc import build_ifc_from_meta
    assert callable(build_ifc_from_meta)
test("export_ifc - import OK (IfcOpenShell)", t_export_ifc_import)

# --- 10. core/engine ---
print("\n[10] core/engine.py")
def t_engine_import():
    from core.engine import PipelineEngine
    engine = PipelineEngine(project_id="unit_test")
    assert engine.project_id == "unit_test"
test("engine - PipelineEngine instantiation", t_engine_import)

# --- Summary ---
print("\n" + "=" * 60)
print("RESULTS SUMMARY")
print("=" * 60)
passed = sum(1 for _, s, _ in results if s == PASS)
failed = sum(1 for _, s, _ in results if s == FAIL)
total = len(results)
print("  Passed: {}/{}  |  Failed: {}/{}".format(passed, total, failed, total))
if failed > 0:
    print("\n  Failed items:")
    for name, status, err in results:
        if status == FAIL:
            print("    - {}: {}".format(name, err))
else:
    print("\n  ALL TESTS PASSED!")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
