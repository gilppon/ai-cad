# -*- coding: utf-8 -*-
"""
STATE G5 코퍼스 게이트: 매니페스트 고정 판본의 존재·무결성 + 스토어 부재 시 XML 폴백.
코퍼스가 없으면 매트릭스가 즉시 실패해야 하며, 가짜 판정을 내서는 안 된다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "data" / "laws" / "manifest.json"


def _manifest():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def test_manifest_files_exist_and_hash_match():
    m = _manifest()
    checked = 0
    for law in m.get("laws", []):
        fname = law.get("file")
        if not fname:
            pytest.fail(f"{law.get('law_id')}: file 미지정 — 코퍼스 불완전 상태로 출항 불가")
        p = REPO_ROOT / "data" / "laws" / fname
        assert p.exists(), f"매니페스트 고정 XML 부재: {fname}"
        if law.get("sha256"):
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            assert digest == law["sha256"], f"{fname}: 판본 해시 불일치 (재적재 필요)"
        checked += 1
    assert checked >= 3, "고정 법령 3건(기준법·시행령·省에네法) 미만"


def test_shoene_xml_present():
    # G5 DoD: 省에네法 file:null 해소
    m = _manifest()
    shoene = next(l for l in m["laws"] if l["law_id"] == "427AC0000000053")
    assert shoene["file"] == "427AC0000000053.xml"
    assert (REPO_ROOT / "data" / "laws" / shoene["file"]).stat().st_size > 100_000


def test_golden_hit_rate_without_chromadb():
    # fresh 환경(CI) 시뮬레이션: 스토어 없이도 XML 폴백으로 채점되어야 함
    import compliance.rag.corpus_search as cs
    cs._LEX_CACHE = None
    orig = cs._get_collection
    cs._get_collection = lambda: None
    try:
        cs._LEX_CACHE = None
        r = cs.golden_hit_rate()
    finally:
        cs._get_collection = orig
        cs._LEX_CACHE = None
    assert r["total"] == len(cs.GOLDEN_QUERIES)
    assert r["hit_rate"] >= 0.8, f"XML 폴백 적중률 미달: {r}"
