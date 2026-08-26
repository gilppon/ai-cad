# -*- coding: utf-8 -*-
"""
SP4 위생·거버넌스 회귀 테스트 (code_remediation_plan_v1.0 §4 H-1~H-5, §5 게이트 규칙)
"""
import ast
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PROD_DIRS = ["parser", "compliance", "core", "harness", "takeoff", "pricing", "exporter", "app"]


def _py_files():
    for d in PROD_DIRS:
        base = REPO / d
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            rel = p.relative_to(REPO).as_posix()
            if "__pycache__" in rel or p.name.startswith(("test_", "verify_")):
                continue
            yield p


# ================================================================
# H-1: 운영 모듈 print( ) 0건 grep 게이트
# ================================================================
def test_h1_no_print_in_production_modules():
    offenders = []
    for p in _py_files():
        src = p.read_text(encoding="utf-8")
        for lineno, line in enumerate(src.splitlines(), 1):
            stripped = line.strip()
            if re_print(stripped):
                # __main__ 진단 블록과 주석은 허용하지 않는다 (운영 원칙 일관)
                offenders.append(f"{p.relative_to(REPO)}:{lineno}: {stripped[:60]}")
    assert not offenders, "print() in production modules:\n" + "\n".join(offenders[:10])


def re_print(line: str) -> bool:
    import re
    return bool(re.match(r"^print\(", line)) or bool(re.search(r"[^.\w]print\(", line))


# ================================================================
# H-2: bare except / except-pass 금지 (app 계층)
# ================================================================
def test_h2_no_bare_or_silent_except_in_app_layer():
    offenders = []
    app_dir = REPO / "app"
    for p in app_dir.rglob("*.py"):
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                offenders.append(f"{p.relative_to(REPO)}:{node.lineno} bare except")
            elif isinstance(node, ast.ExceptHandler):
                body_is_pass = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
                only_docstring = (
                    len(node.body) == 1
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                )
                if body_is_pass or only_docstring:
                    offenders.append(f"{p.relative_to(REPO)}:{node.lineno} silent except")
    assert not offenders, "silent exception handlers:\n" + "\n".join(offenders[:10])


# ================================================================
# H-3: CORS 메서드 화이트리스트화 + ALLOWED_ORIGINS 후크 존재
# ================================================================
def test_h3_cors_hardened():
    src = (REPO / "app" / "main.py").read_text(encoding="utf-8")
    assert 'allow_methods=["GET", "POST", "PATCH", "OPTIONS"]' in src
    assert "ALLOWED_ORIGINS" in src
    # credentials=True 상태에서 와일드카드 오리진 병용 금지 유지
    assert '"*"' not in src.split("allow_origins=")[1].split("]")[0]


# ================================================================
# H-5: 스케일 폴백 상수 SSOT - core/units 단일 정의
# ================================================================
def test_h5_default_scale_defined_once():
    definition_sites = []
    for p in _py_files():
        rel = p.relative_to(REPO).as_posix()
        if rel.replace("\\", "/") == "core/units.py":
            continue
        src = p.read_text(encoding="utf-8")
        for lineno, line in enumerate(src.splitlines(), 1):
            if line.strip().startswith("DEFAULT_PX_TO_M") and "=" in line and "import" not in line:
                definition_sites.append(f"{rel}:{lineno}")
    assert not definition_sites, f"DEFAULT_PX_TO_M must be defined only in core/units.py: {definition_sites}"


# ================================================================
# PMO: 매트릭스 무결성 게이트 자체 검증
# ================================================================
def test_pmo_gate_catches_constant_scoring(tmp_path):
    from harness.bench_integrity import pmo_no_constant_scores

    bad = tmp_path / "bad_bench.py"
    bad.write_text(
        "scores = {}\n"
        "scores['x_indicator'] = 10\n"
        "if True:\n"
        "    scores['y_indicator'] = 5\n",
        encoding="utf-8",
    )
    violations = pmo_no_constant_scores(str(bad))
    assert len(violations) == 1  # x_indicator만 위반

    good = tmp_path / "good_bench.py"
    good.write_text("scores = {}\nscores['z'] = 10 if measured else 0\n", encoding="utf-8")
    assert pmo_no_constant_scores(str(good)) == []


# ================================================================
# D2.2 지표 하네스: 실코퍼스 골든셋 Hit@3 기준선 유지
# ================================================================
def test_corpus_golden_hit_rate_baseline():
    from compliance.rag.corpus_search import golden_hit_rate

    result = golden_hit_rate()
    assert result["total"] >= 5
    # 벡터스토어 이관(SP2/A-3) 및 렉시컬 전환(SP4) 후의 실측 기준선: 80% 이상
    assert result["hit_rate"] >= 0.8, f"golden hit rate degraded: {result}"
