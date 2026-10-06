"""치수 스케일 보정 C9 (프로덕션 경로).

치수선(pixel 길이) ↔ 기재 치수(mm) 쌍에서 mm/px를 추정한다.
- 중앙값(median) + MAD 기반 강건 추정. 평균이 아니라 이상치에 강하다.
- 축별 스케일이 크게 다르면(스캔 왜곡·프레임 불일치) uncalibrated로 명시.
  가짜 스케일로 면적을 속이지 않는다 (SP1/L-2 계승).
- OCR 자동검출은 C9-b 후속. 본 모듈은 쌍(pair) → 스케일 추정기이며,
  쌍의 출처(벡터 텍스트층·수동 실측·OCR)는 호출자가 명시한다.

STATE C9 DoD: jp04(27.0mm/px, 축 일치) calibrated / jp02(프레임 불일치) 명시적 미보정.
"""
from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional


# 보정 판정 임계: 쌍 간 최대 괴리율이 이하면 calibrated
SPREAD_THRESHOLD_PCT = 25.0


def calibrate_from_pairs(
    pairs: List[Dict[str, Any]],
    spread_threshold_pct: float = SPREAD_THRESHOLD_PCT,
) -> Dict[str, Any]:
    """dimension_pairs → 스케일 판정.

    pair: {"pixel_length": float, "annotated_mm": float, "axis": "H"|"V"|...,
           "source": str} — source는 provenance용 (예: "outer-dimension-line").
    반환: {"mm_per_px", "spread_pct", "calibrated", "n_pairs", "method", "detail"}
    """
    factors: List[float] = []
    for p in pairs or []:
        try:
            px = float(p.get("pixel_length", 0))
            mm = float(p.get("annotated_mm", 0))
        except (TypeError, ValueError):
            continue
        if px > 0 and mm > 0:
            factors.append(mm / px)

    if not factors:
        return {
            "mm_per_px": None, "spread_pct": None, "calibrated": False,
            "n_pairs": 0, "method": "median",
            "detail": "치수 쌍 없음 — 스케일 미보정. 면적 절대비교 불가.",
        }

    med = statistics.median(factors)
    spread = (max(factors) - min(factors)) / med * 100.0 if med > 0 else float("inf")
    mad = statistics.median([abs(f - med) for f in factors])

    calibrated = len(factors) >= 1 and spread <= spread_threshold_pct
    return {
        "mm_per_px": round(med, 4),
        "spread_pct": round(spread, 2),
        "mad": round(mad, 4),
        "calibrated": calibrated,
        "n_pairs": len(factors),
        "method": "median",
        "detail": ("보정됨" if calibrated
                   else f"축별 괴리 {spread:.1f}%로 미보정 — 면적 절대비교 불가"),
    }


def apply_scale_to_payload(payload: Dict[str, Any],
                           calibration: Dict[str, Any]) -> Dict[str, Any]:
    """보정 결과를 geometry payload에 기록. 미보정 시 스케일을 속이지 않는다."""
    meta = payload.setdefault("metadata", {})
    meta["scale_calibration"] = {
        "calibrated": calibration["calibrated"],
        "mm_per_px": calibration["mm_per_px"],
        "spread_pct": calibration.get("spread_pct"),
        "n_pairs": calibration.get("n_pairs", 0),
        "method": calibration.get("method", "median"),
    }
    if calibration["calibrated"] and calibration["mm_per_px"]:
        payload.setdefault("scale", {})["pixel_to_mm"] = calibration["mm_per_px"]
        payload["scale"]["calibrated"] = True
    else:
        payload.setdefault("scale", {}).setdefault("calibrated", False)
    return payload
