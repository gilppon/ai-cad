# -*- coding: utf-8 -*-
"""
STATE C9 치수 스케일 보정 게이트.

- 추정기 단위: 중앙값·스프레드·calibrated 판정 (빈 쌍·괴리율 초과 → 미보정 명시).
- 픽스처 실측: jp04 축일치(27.0) 보정 / jp01 보정(괴리 19%) / jp02 프레임불일치 미보정 / jp03 쌍없음 미보정.
- 엔진 훅: dimension_pairs → payload scale 기록. 미보정 시 스케일을 속이지 않음.
"""
from __future__ import annotations

import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "jp_samples"


def _pairs(name: str):
    with open(FIXTURE_DIR / f"ground_truth_{name}.json", encoding="utf-8") as f:
        return json.load(f).get("scale_pairs", [])


def test_estimator_empty_is_uncalibrated():
    from parser.scale_calibrate import calibrate_from_pairs
    r = calibrate_from_pairs([])
    assert r["calibrated"] is False and r["mm_per_px"] is None


def test_estimator_rejects_outliers_by_spread():
    from parser.scale_calibrate import calibrate_from_pairs
    r = calibrate_from_pairs([
        {"pixel_length": 616, "annotated_mm": 10010},
        {"pixel_length": 1022, "annotated_mm": 9100},
    ])
    assert r["calibrated"] is False
    assert r["spread_pct"] > 25.0


def test_jp04_axis_aligned_calibrated():
    from parser.scale_calibrate import calibrate_from_pairs
    r = calibrate_from_pairs(_pairs("jp04"))
    assert r["calibrated"] is True
    assert abs(r["mm_per_px"] - 27.0) / 27.0 <= 0.05, r
    assert r["spread_pct"] <= 5.0, r


def test_jp01_calibrated_with_spread():
    from parser.scale_calibrate import calibrate_from_pairs
    r = calibrate_from_pairs(_pairs("jp01"))
    assert r["calibrated"] is True
    assert abs(r["mm_per_px"] - 26.5) / 26.5 <= 0.10, r


def test_jp02_frame_mismatch_uncalibrated():
    from parser.scale_calibrate import calibrate_from_pairs
    r = calibrate_from_pairs(_pairs("jp02"))
    assert r["calibrated"] is False, r


def test_jp03_no_pairs_uncalibrated():
    assert _pairs("jp03") == []


def test_engine_hook_records_calibration():
    from parser.scale_calibrate import calibrate_from_pairs, apply_scale_to_payload
    payload = {"rooms": [], "dimension_pairs": _pairs("jp04")}
    apply_scale_to_payload(payload, calibrate_from_pairs(payload["dimension_pairs"]))
    assert payload["scale"]["calibrated"] is True
    assert payload["metadata"]["scale_calibration"]["calibrated"] is True

    payload2 = {"rooms": []}
    apply_scale_to_payload(
        payload2, {"calibrated": False, "mm_per_px": None,
                   "spread_pct": None, "n_pairs": 0, "method": "median"})
    assert payload2["scale"].get("calibrated") is False
    assert "pixel_to_mm" not in payload2["scale"]
