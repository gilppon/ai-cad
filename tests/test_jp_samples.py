# -*- coding: utf-8 -*-
"""
JP 실도면 픽스처 검증 (G1 해소 2차, 2026-10-06).

대상: tests/fixtures/jp_samples/ jp01~jp04 (전건 래스터 JPG).
kr01_debug_apt.jpg는 일본 검증 제외·과소분할 디버그 전용이므로 수집하지 않는다.

게이트 (test_real_floor_plan.py와 동일 규격):
  1. 정지(0실)·폭주(200실+) 금지 — hard assert
  2. 기하 유효성 (area>0, contour>=3) — hard assert
  3. 방수 vs 정답지 (파일별 tolerance) — hard assert
  4. 면적 절대비교 — skip (px 스케일 미보정, C9 완료 후 활성화). skip 메시지에 현 격차를 기록한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "jp_samples"

SPECS = [
    "jp01",
    "jp02",
    "jp03",
    "jp04",
]


def _load_spec(name: str) -> dict:
    with open(FIXTURE_DIR / f"ground_truth_{name}.json", encoding="utf-8") as f:
        return json.load(f)


def _run_pipeline(image: str, tmp_path_factory) -> dict:
    from parser.image_outline import extract_room_result_from_page

    out_dir = tmp_path_factory.mktemp(f"{image}_out")
    path = FIXTURE_DIR / image
    doc = fitz.open(str(path))
    try:
        result = extract_room_result_from_page(doc[0], 0, out_dir, str(path))
    finally:
        doc.close()
    rooms = [
        {"area_px": float(r.area_px), "bbox": r.bbox,
         "kind": r.kind, "contour_points": len(r.contour)}
        for r in result.rooms
    ]
    return {"rooms": rooms, "walls_count": len(result.walls),
            "debug": result.debug}


@pytest.fixture(scope="module", params=SPECS)
def case(request, tmp_path_factory) -> dict:
    spec = _load_spec(request.param)
    res = _run_pipeline(spec["image"], tmp_path_factory)
    return {"name": request.param, "spec": spec, "result": res}


def test_no_crash_or_explode(case):
    n = len(case["result"]["rooms"])
    assert 0 < n < 200, f"{case['name']}: 비정상 방 개수 {n}"


def test_valid_geometry(case):
    for r in case["result"]["rooms"]:
        assert r["area_px"] > 0, f"{case['name']}: 면적 0 방 존재"
        assert r["contour_points"] >= 3, f"{case['name']}: contour 파손"


def test_count_within_tolerance(case):
    truth = int(case["spec"]["truth_count"])
    tol = int(case["spec"]["count_tolerance"])
    n = len(case["result"]["rooms"])
    assert abs(n - truth) <= tol, (
        f"{case['name']}: 감지 {n}실 vs 정답 {truth}실 (허용 ±{tol})"
    )


def test_area_absolute_where_scale_and_jo_known(case):
    """실스케일 보정 + 帖 확정실에 한해 면적 절대비교 (hard assert).
    jp04 8실 전부 ±50% 이내 (실측 2026-10-06: 최대 NOK 25.6%).
    스케일 미보정·帖 미표기실은 비교 불가 → skip (C9·대표님검증 대기)."""
    from parser.scale_calibrate import calibrate_from_pairs

    spec = case["spec"]
    cal = calibrate_from_pairs(spec.get("scale_pairs", []))
    if not cal["calibrated"]:
        pytest.skip(f"{case['name']}: 스케일 미보정 — 면적 절대비교 불가")
    jo_rooms = [r for r in spec["rooms"] if r.get("jo")]
    if not jo_rooms:
        pytest.skip(f"{case['name']}: 帖 확정실 없음 — 면적 절대비교 불가")

    mm = cal["mm_per_px"]
    det = sorted(float(r["area_px"]) * mm * mm / 1e6 for r in case["result"]["rooms"])
    assert det, f"{case['name']}: 검출실 없음"
    for room in jo_rooms:
        gt = float(room["area_m2"])
        best = min(det, key=lambda d: abs(d - gt) / gt)
        rel = abs(best - gt) / gt * 100.0
        assert rel <= 50.0, (
            f"{case['name']} {room['id']}: 정답 {gt}m² vs {best:.2f}m² (오차 {rel:.1f}%)"
        )
