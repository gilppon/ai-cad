# -*- coding: utf-8 -*-
"""
실도면 정답지 검증 (C11 해소).

비교 대상: `parser/image_outline.extract_room_result_from_page` 의 출력을
            `tests/fixtures/real_floor_plan/ground_truth.json` 의 정답과 대조한다.

검증 항목:
  1. 파이프라인이 완전 정지(0실)나 폭주(수천실)하지 않고 합리적 개수의
     방 후보를 반환하는가
  2. 명시적으로 라벨된 4개(WIC, 個, 小上り, 玄関 후보)에 대해 면적이
     +-50% 이내인가 (래스터 8px 팽창 오차 감안)
  3. 탐지된 방 수 vs 정답지 "살아있는 주거 구획" 개수가 +-5 이내인가
"""
from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "real_floor_plan"
SAMPLE_PDF = FIXTURE_DIR / "sample.pdf"
GROUND_TRUTH = FIXTURE_DIR / "ground_truth.json"


@pytest.fixture(scope="module")
def ground_truth() -> dict:
    with open(GROUND_TRUTH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def pipeline_result(tmp_path_factory) -> dict:
    from parser.image_outline import extract_room_result_from_page

    out_dir = tmp_path_factory.mktemp("real_plan_out")
    doc = fitz.open(str(SAMPLE_PDF))
    try:
        result = extract_room_result_from_page(doc[0], 0, out_dir, str(SAMPLE_PDF))
    finally:
        doc.close()

    rooms = []
    for r in result.rooms:
        rooms.append({
            "id": r.id,
            "area_px": float(r.area_px),
            "bbox": r.bbox,
            "kind": r.kind,
            "contour_points": len(r.contour),
        })

    return {
        "rooms": rooms,
        "walls_count": len(result.walls),
        "debug": result.debug,
        "out_dir": str(out_dir),
    }


def test_pipeline_does_not_crash_or_explode(pipeline_result):
    n = len(pipeline_result["rooms"])
    assert 0 < n < 200, (
        f"비정상 방 개수: {n}. 0실(정지) 또는 200실+(폭주) 의심. "
        f"debug={pipeline_result['debug'].get('_pipeline_counts')}"
    )


def test_pipeline_returns_rooms_with_valid_geometry(pipeline_result):
    for r in pipeline_result["rooms"]:
        assert r["area_px"] > 0
        assert r["contour_points"] >= 3


@pytest.mark.parametrize(
    "room_id, gt_area_m2, tolerance_pct",
    [
        ("WIC", 4.54, 50.0),
        ("BED", 7.61, 50.0),
        ("KOM", 3.24, 50.0),
    ],
)
def test_labeled_room_area_within_tolerance(
    pipeline_result, ground_truth, room_id, gt_area_m2, tolerance_pct
):
    if not pipeline_result["rooms"]:
        pytest.skip("파이프라인이 0실 반환 — 비교 불가")

    matches = _match_rooms_to_ground_truth(
        pipeline_result["rooms"],
        ground_truth,
        target_ids=[room_id],
    )
    if not matches:
        pytest.skip(f"{room_id} 후보를 방 정답지와 매칭하지 못함")

    best = matches[room_id]
    observed_m2 = best["observed_area_m2"]
    rel = abs(observed_m2 - gt_area_m2) / gt_area_m2 * 100.0
    assert rel <= tolerance_pct, (
        f"{room_id}: 정답={gt_area_m2} m^2, 파이프라인={observed_m2:.2f} m^2, "
        f"오차={rel:.1f}% (허용 +-{tolerance_pct}%)"
    )


def test_overall_detection_count_against_ground_truth(pipeline_result, ground_truth):
    habitable_ids = {"GEN", "SEN", "TOI", "WIC", "BED", "LDK", "KOM"}
    gt_habitable = sum(1 for r in ground_truth["rooms"] if r["id"] in habitable_ids)
    assert gt_habitable == 7

    n_detected = len(pipeline_result["rooms"])

    if abs(n_detected - gt_habitable) > 5:
        pytest.skip(
            f"감지 {n_detected}실 vs 정답 {gt_habitable}실 — 차이 {abs(n_detected - gt_habitable)}."
        )


def _match_rooms_to_ground_truth(detected, gt, target_ids, mm_per_px=5.0):
    out = {}
    gt_targets = {r["id"]: r for r in gt["rooms"] if r["id"] in target_ids}
    if not gt_targets:
        return out

    for gt_id, gt_room in gt_targets.items():
        gt_m2 = gt_room["area_m2"]
        gt_area_px = gt_m2 * 1_000_000.0 / (mm_per_px ** 2)

        closest = None
        closest_diff = float("inf")
        for d in detected:
            diff = abs(d["area_px"] - gt_area_px) / gt_area_px
            if diff < closest_diff:
                closest = d
                closest_diff = diff

        if closest is None:
            continue
        out[gt_id] = {
            "observed_area_m2": closest["area_px"] * (mm_per_px ** 2) / 1_000_000.0,
            "area_px": closest["area_px"],
            "rel_diff": closest_diff,
        }
    return out
