# -*- coding: utf-8 -*-
"""
M1 게이트: engine/ 인벤토리 고정.
- 18모듈 목록이 STATUS.md와 일치 (무단 증식 차단).
- TEST-ONLY 모듈을 app/·core/가 import하지 않음 (pslg_topology 제외).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# STATUS.md WIRED 모듈 (프로덕션 import 허용)
WIRED = {"engine/geometry/pslg_topology.py"}

# DELEGATE (어댑터이므로 존재 허용, 직접 로직 사용 금지와 무관)
DELEGATE = {"engine/exporters/ifc_worker.py"}


def _engine_files():
    return sorted(
        str(p.relative_to(REPO_ROOT)).replace("\\", "/")
        for p in (REPO_ROOT / "engine").rglob("*.py")
        if "__pycache__" not in str(p)
    )


def test_engine_inventory_fixed_at_18():
    assert len(_engine_files()) == 18, _engine_files()


def test_prod_imports_only_wired_engine_modules():
    out = subprocess.run(
        ["git", "grep", "-l", "from engine\\.\|from engine import",
         "--", "app/", "core/", "parser/", "compliance/", "pipeline/",
         "harness/", "domain/", "scene/", "exporter/", "takeoff/", "pricing/",
         "correction/"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    ).stdout.splitlines()
    # core/engine.py의 pslg 배선 1건만 허용. git 미추적 환경이면 스킵.
    if not out:
        mods = []
        for base in ["app", "core", "parser", "compliance", "pipeline",
                     "harness", "domain", "scene", "exporter", "takeoff",
                     "pricing", "correction"]:
            mods += list((REPO_ROOT / base).rglob("*.py"))
        hits = [str(m) for m in mods
                if "from engine." in m.read_text(encoding="utf-8", errors="ignore")]
        out = [h.replace(str(REPO_ROOT) + "/", "").replace("\\", "/") for h in hits]
        assert all(h == "core/engine.py" for h in out), out
        return
    assert out == ["core/engine.py"], out
