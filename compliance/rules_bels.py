"""BELS 별점 (2024-04 개정区分) — BEI→★ 매핑.

- BEI小 → 고성능. 재에네無 주택은 최대 4성, 재에네有 주택·비주거는 5~6성까지.
- 본 모듈은 계산이 아니라 표시용 매핑이다. BEI 값은 Web프로그램 산출값을 입력받는다.
- LLM이 BEI를 추정·생성해서는 안 된다 (STATE §4.1).
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def rate_bels_stars(
    bei: Optional[float],
    is_residential: bool = True,
    has_renewables: bool = False,
) -> Dict[str, Any]:
    if bei is None:
        return {
            "stars": None,
            "label_ja": "判定不能",
            "comment_ja": "BEI未入力のためBELS評価不可。Webプログラムの算出結果を登録してください。",
        }
    try:
        b = float(bei)
    except (TypeError, ValueError):
        return {
            "stars": None,
            "label_ja": "判定不能",
            "comment_ja": "BEI値が数値ではないためBELS評価不可。",
        }
    if b <= 0.5:
        stars = 6
    elif b <= 0.6:
        stars = 5
    elif b <= 0.7:
        stars = 4
    elif b <= 0.8:
        stars = 3
    elif b <= 0.9:
        stars = 2
    elif b <= 1.0:
        stars = 1
    else:
        stars = 0
    # 재에네無 주택 상한 4성 규칙
    capped = False
    if is_residential and not has_renewables and stars > 4:
        stars = 4
        capped = True
    label = f"★{stars}" if stars > 0 else "★なし（基準超過）"
    comment = f"BELS評価（2024年4月区分）：BEI={b:.2f} → {label}。"
    if capped:
        comment += "再エネ設備なし住宅のため上限4つ星を適用。"
    comment += "最終評価は登録評価機関が行います。"
    return {"stars": stars, "label_ja": label, "comment_ja": comment, "bei": round(b, 4)}
