"""벤치마크 무결성 게이트 (SP4/PMO).

verify_100_matrix의 '무조건 상수 점수 대입' 차단 로직을
테스트에서 안전하게 재사용할 수 있도록 독립 모듈로 분리했다.
(벤치마크 본문은 stdout 래핑 등 부수효과가 있어 직접 임포트 금지)
"""
from __future__ import annotations

import ast


def pmo_no_constant_scores(source_path: str) -> list:
    """
    scores[...] = <상수> 형태의 '측정과 무관한' 점수 부여만 차단한다.
    - 금지: 어떤 조건에도 들어있지 않은 순수 상수 리터럴 대입
      (예: scores["3.2_web_viewer_performance"] = 10)
    - 허용: if 분기 내 대입, 조건식(10 if ok else 0), 함수 호출/연산 결과 등
      측정값에 의존하는 모든 형태

    반환: [(lineno, expr_dump), ...] — 빈 리스트면 통과.
    """
    with open(source_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=source_path)

    violations = []

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.if_depth = 0

        def visit_If(self, node):
            self.if_depth += 1
            self.generic_visit(node)
            self.if_depth -= 1

        def visit_Assign(self, node):
            value_is_bare_constant = isinstance(node.value, ast.Constant)
            if value_is_bare_constant and self.if_depth == 0:
                for target in node.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "scores"
                    ):
                        violations.append((getattr(node, "lineno", "?"), ast.dump(node.value)[:40]))
            self.generic_visit(node)

    Visitor().visit(tree)
    return violations
