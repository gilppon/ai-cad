"""盛土·消防·조례 게이트 — e-Gov RAG에 없는 영역의 위장판정 방지.

- 盛土規制法 (法30条·35条, 2026-01-05 규제지역 지정 개시): 해당여부는 별도 확인 필요.
- 消防同意·지방조례·告示 연산: 본 도구 관할 밖.
- 세 영역 모두 "적합"으로 출력해서는 안 되며 "판정불가 — 별도확인 필요"로만 출력한다.

STATE Phase 2 P1-F6 / 출항게이트 G4의 네거티브 테스트 대상.
"""
from __future__ import annotations

from typing import Any, Dict

DISCLAIMER_JA = "本ツールは判定を確定しません。最終判断は有資格者・審査機関が行います。"


def check_morido_regulation(area_designated: Any = None) -> Dict[str, Any]:
    if area_designated is True:
        return {
            "status": "N/A",
            "item_ja": "盛土規制法適合性（法第30条・第35条）",
            "comment_ja": "規制区域内のため別途適合証明が必要。対照表(8)を添付し、県窓口に確認すること。" + DISCLAIMER_JA,
        }
    if area_designated is False:
        return {
            "status": "N/A",
            "item_ja": "盛土規制法適合性（法第30条・第35条）",
            "comment_ja": "規制区域外の申告であっても指定更新があり得るため、申請時点の区域図で再確認すること。" + DISCLAIMER_JA,
        }
    return {
        "status": "N/A",
        "item_ja": "盛土規制法適合性（法第30条・第35条）",
        "comment_ja": "規制区域該当の有無が未入力のため判定不能。対照表(8)＋区域図で確認すること。" + DISCLAIMER_JA,
    }


def check_fire_and_ordinance() -> Dict[str, Any]:
    return {
        "status": "N/A",
        "item_ja": "消防同意・条例・告示",
        "comment_ja": "消防同意・地方条例・告示の運用は本ツールの対象外のため判定不能。所轄消防・特定行政庁に別途確認すること。" + DISCLAIMER_JA,
    }
