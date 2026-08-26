"""bSJ(buildingSMART Japan) 적산용 분류체계 매핑 (SP3/Q-1).

BIM/CIM積算モデル作成ガイドライン의 부재 분류 개념에 준거한 경량 매핑이다.
정식 IfcClassificationReference 코드체계는 bSJ 공개 분류표 확정 시 교체한다.
"""
from __future__ import annotations

from typing import Dict

# 물리 수량 기준(basis) → 분류 (대분류.중분류 표기)
BASIS_CLASSIFICATION: Dict[str, str] = {
    "FLOOR-AREA": "7.仕上工.床",
    "CEIL-AREA": "7.仕上工.天井",
    "WALL-AREA": "7.仕上工.壁",
    "WALL-LENGTH": "2.解体工.壁",
    "ROOM-COUNT": "8.設備工.配管",
    "DOOR-COUNT": "6.建具工.扉",
    "WINDOW-COUNT": "6.建具工.窓",
}

DEFAULT_CLASSIFICATION = "9.その他.共通"


def classification_for_basis(basis: str) -> str:
    return BASIS_CLASSIFICATION.get(basis, DEFAULT_CLASSIFICATION)
