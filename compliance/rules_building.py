"""建築基準法 新2号/新3号 분류 (旧4号특례 재편, 2025-04-01 시행).

- 新2号 = 목조 2층 + 목조 1층 200㎡초과 → 특례삭제, 구조서류 제출 필수.
- 新3号 = 목조 1층 200㎡이하 → 축소된 특례 유지.
- 비목조·확인불가는 판정불가(N/A)가 아니라 분류불가로 명시 (가짜適合 금지).

최종판단은 심사기관·유자격자가 하며 본 모듈은 프리체크용이다.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def classify_new_go(
    building_structure: str = "wooden",
    floors: int = 2,
    area_m2: Optional[float] = None,
) -> Dict[str, Any]:
    struct = str(building_structure or "").strip().lower()
    is_wooden = struct in ("wooden", "wood", "w", "木造", "もくぞう")
    try:
        f = int(floors)
    except (TypeError, ValueError):
        f = 2
    try:
        a = float(area_m2) if area_m2 is not None else None
    except (TypeError, ValueError):
        a = None

    if not is_wooden:
        return {
            "category": "non-wooden",
            "category_ja": "非木造（新2号・新3号の対象外）",
            "structural_docs_required": True,
            "basis_ja": "木造以外の建築物は階数・面積にかかわらず構造審査の対象。詳細は審査機関に確認。",
        }
    if f >= 2 or (a is not None and f == 1 and a > 200.0):
        return {
            "category": "new-2go",
            "category_ja": "新2号（木造2階建て等）",
            "structural_docs_required": True,
            "basis_ja": "2025年4月1日施行の旧4号特例見直しにより構造審査の対象。壁量計算等の構造書類が必要。",
        }
    if f <= 1 and a is not None and a <= 200.0:
        return {
            "category": "new-3go",
            "category_ja": "新3号（木造平家・200㎡以下）",
            "structural_docs_required": False,
            "basis_ja": "縮小された特例の範囲。ただし省エネ書類は別途必要（2025年4月〜原則全棟適合義務）。",
        }
    # 1층이나 면적 미입력 등 분류 불가 → 안전측(신2호 취급). 특례 추정은 fail-open이므로 금지.
    return {
        "category": "unknown",
        "category_ja": "分類不能（階数・面積の入力不足）",
        "structural_docs_required": True,
        "basis_ja": "階数・面積が未入力のため安全側（新2号扱い）で構造書類ありとして扱う。",
    }


def check_wall_quantity_requirement(category: str) -> Dict[str, Any]:
    if category == "new-2go":
        return {
            "required": True,
            "item_ja": "壁量計算書等の構造書類",
            "comment_ja": "新2号は確認申請時に壁量計算書等の提出が必要。抜けが差戻しの最大原因。",
        }
    if category == "new-3go":
        return {
            "required": False,
            "item_ja": "壁量計算書等の構造書類",
            "comment_ja": "新3号は特例範囲だが、省エネ書類の要否は別途確認すること。",
        }
    return {
        "required": True,
        "item_ja": "壁量計算書等の構造書類",
        "comment_ja": "分類不能のため安全側で要提出として扱う。審査機関に確認すること。",
    }
