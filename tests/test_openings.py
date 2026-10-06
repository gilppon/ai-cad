# -*- coding: utf-8 -*-
"""
STATE C8 개구부 게이트: wall-gap 후보가 생산 경로에서 산출되는가.
- 단위: 빈 벽선 → [] (속이지 않음).
- 픽스처: 문이 보이는 4건 전부 후보 존재 + 폭주 상한 (<40).
  (실측 2026-10-06: jp01 5 / jp02 8 / jp03 7 / jp04 6)
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import fitz
import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "jp_samples"
IMAGES = ["jp01_heimenzu_1f.jpg", "jp02_nikai_arch.jpg",
          "jp03_handdrawn_jp.jpg", "jp04_nikai_tsubo.jpg"]


def test_derive_empty_is_empty():
    from parser.openings import derive_openings, summarize_openings
    assert derive_openings([]) == []
    assert derive_openings(None) == []
    assert summarize_openings([])["count"] == 0


def test_derive_accepts_dict_and_list():
    from parser.openings import derive_openings
    walls = [{"x1": 0, "y1": 0, "x2": 100, "y2": 0},
             {"x1": 150, "y1": 0, "x2": 250, "y2": 0}]
    r = derive_openings(walls)
    assert len(r) == 1 and abs(r[0]["gap_px"] - 50.0) < 1e-6


@pytest.fixture(scope="module", params=IMAGES)
def openings_case(request, tmp_path_factory):
    from parser.image_outline import extract_room_result_from_page
    out = tmp_path_factory.mktemp(f"{request.param}_op")
    doc = fitz.open(str(FIXTURE_DIR / request.param))
    try:
        res = extract_room_result_from_page(doc[0], 0, out, str(FIXTURE_DIR / request.param))
    finally:
        doc.close()
    import json as _json
    ops = _json.loads(res.debug.get("_openings", "{}"))
    return {"image": request.param, "summary": ops, "debug": res.debug}


def test_openings_detected_where_doors_exist(openings_case):
    n = openings_case["summary"].get("count", 0)
    assert n >= 3, f"{openings_case['image']}: 개구부 {n}건 — 문이 보이는 도면에서 미검출"


def test_openings_no_blowup(openings_case):
    n = openings_case["summary"].get("count", 0)
    assert n < 40, f"{openings_case['image']}: 개구부 {n}건 — 폭주 의심"


def test_openings_json_written(openings_case):
    p = Path(openings_case["debug"].get("_openings_json", ""))
    assert p.exists() and p.stat().st_size > 2
