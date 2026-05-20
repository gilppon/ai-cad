# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional, List
from domain.models import RoomKind, Point

# 일본 현지 건축 도면 및 현장 약어 사전 (i18n & 시맨틱 맵)
JAPANESE_ROOM_MAP = {
    RoomKind.LDK: {"jp_name": "LDK (居間・食事室・台所)", "abbr": "LDK", "is_wet": True},
    RoomKind.BEDROOM: {"jp_name": "洋室 (寝室)", "abbr": "洋室", "is_wet": False},
    RoomKind.CORRIDOR: {"jp_name": "廊下", "abbr": "廊下", "is_wet": False},
    RoomKind.BATHROOM: {"jp_name": "浴室 (バスルーム)", "abbr": "UB", "is_wet": True},
    RoomKind.TOILET: {"jp_name": "お手洗い (トイレ)", "abbr": "WC", "is_wet": True},
    RoomKind.KITCHEN: {"jp_name": "台所 (キッチン)", "abbr": "K", "is_wet": True},
    RoomKind.BALCONY: {"jp_name": "バルコニー (ベランダ)", "abbr": "バルコニー", "is_wet": True}, # 외부 빗물 유입 가능
    RoomKind.SHAFT: {"jp_name": "パイプスペース (PS) / ダクトスペース (DS)", "abbr": "PS/DS", "is_wet": True},
    RoomKind.CLOSET: {"jp_name": "収納 (クローゼット)", "abbr": "CL", "is_wet": False},
    RoomKind.ENTRANCE: {"jp_name": "玄関", "abbr": "玄関", "is_wet": False},
    RoomKind.WET: {"jp_name": "ユーティリティ (洗濯機置場等)", "abbr": "UT", "is_wet": True},
    RoomKind.STORAGE: {"jp_name": "納戸 (サービスルーム)", "abbr": "SR", "is_wet": False},
    RoomKind.ROOM: {"jp_name": "和室 / 居室", "abbr": "和室", "is_wet": False},
    RoomKind.UNKNOWN: {"jp_name": "用途不明", "abbr": "不明", "is_wet": False}
}

class JPResponsibilityEngine:
    """
    일본 맨션(공동주택)의 구분소유법 및 표준관리규약(標準管理規約)에 근거한
    공용부분(共有部分) vs 전유부분(専有部分) 누수 책임 소재 판정 엔진
    """

    @staticmethod
    def check_ownership_zone(room_kind: RoomKind, location_tag: str = "") -> Dict[str, Any]:
        """
        방의 종류 및 위치 특성을 바탕으로 공용부/전유부 판정 기준과 표준 약관 조항 도출
        """
        # 1. PS/DS/Shaft 구역은 100% 공용부분
        if room_kind == RoomKind.SHAFT or "PS" in location_tag or "DS" in location_tag or "MB" in location_tag:
            return {
                "ownership": "COMMON",
                "japanese_label": "共用部分 (パイプスペース等)",
                "confidence": 1.0,
                "legal_basis": "区分所有法第4条・マンション標準管理規約第7条 (別表第2)",
                "description": "배관 샤프트실(PS/DS) 및 메터 박스(MB) 내의 공용 종관(縱管) 누수는 구분소유자 개인이 아닌 관리조합의 책임(장기수선충당금 처리 대상)입니다."
            }
            
        # 2. 발코니는 공용부분이나 전용사용권(専用使用権) 인정 구역
        elif room_kind == RoomKind.BALCONY:
            return {
                "ownership": "COMMON_EXCLUSIVE_USE",
                "japanese_label": "共用部分 (専用使用権・バルコニー)",
                "confidence": 0.9,
                "legal_basis": "マンション標準管理規約第14조 및 제21조",
                "description": "발코니는 기본적으로 공용부분이나 세대주에게 전용 사용권이 부여됩니다. 방수층 노후화로 인한 누수는 관리조합 책임이나, 세대주의 사용상 과실(배수구 막힘 방치 등)이 입증될 경우 세대주 부담이 될 수 있습니다."
            }
            
        # 3. 전형적인 세대 전유 젖은 구역 (욕실, 부엌, 화장실 등의 지관 배관)
        elif room_kind in [RoomKind.BATHROOM, RoomKind.KITCHEN, RoomKind.TOILET, RoomKind.WET]:
            return {
                "ownership": "PROPRIETARY",
                "japanese_label": "専有部分 (住戸内枝管・防水層)",
                "confidence": 0.85,
                "legal_basis": "マンション標準管理規약第7条第1項 (別表第3)",
                "description": "세대 내 전유 세대 전용 배관(지관) 및 욕실 방수층 불량으로 인한 누수는 해당 구분소유자(세대주)의 개인 책임(자부담 또는 일상생활배상책임보험 처리)입니다."
            }
            
        # 4. 기타 거실 등 건조 구역
        elif room_kind in [RoomKind.LDK, RoomKind.BEDROOM, RoomKind.ROOM, RoomKind.CORRIDOR]:
            return {
                "ownership": "PROPRIETARY",
                "japanese_label": "専有部分 (住戸内)",
                "confidence": 0.8,
                "legal_basis": "区分所有法第2条第3項",
                "description": "세대 내 거실 또는 침실 천장/바닥의 누수 현상 자체는 윗세대의 배관 결함 또는 외벽 균열(공용부)로부터 확산된 2차 피해 구역입니다. 누수원 자체를 파악하여 책임 주체를 가려야 합니다."
            }
            
        # 5. 불분명한 구역
        else:
            return {
                "ownership": "UNCERTAIN",
                "japanese_label": "要精密調査 (境界部分)",
                "confidence": 0.5,
                "legal_basis": "区分所有法第9条 (建物の設置又は保存の瑕疵の推定)",
                "description": "경계 벽체 내부 배관 또는 콘크리트 슬래브 매립 배관의 경우, 공용 종관의 하자 혹은 전유부 관의 하자인지 확인하기 위해 내시경 카메라 진단 및 가압 테스트 등 전문 업자의 조사가 요구됩니다."
            }

    @classmethod
    def evaluate_leak(cls, leak_source_point: Dict[str, float], room_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        누수원 좌표와 방의 메타데이터를 기반으로 종합 하자 판단 리포트 반환
        """
        room_kind_str = room_metadata.get("kind", "UNKNOWN").upper()
        
        # RoomKind Enum 매칭
        try:
            room_kind = RoomKind[room_kind_str]
        except KeyError:
            room_kind = RoomKind.UNKNOWN

        location_tag = room_metadata.get("location_tag", "")
        analysis = cls.check_ownership_zone(room_kind, location_tag)
        
        jp_info = JAPANESE_ROOM_MAP.get(room_kind, {"jp_name": "用途不明", "abbr": "不明", "is_wet": False})
        
        return {
            "status": "success",
            "leak_point": leak_source_point,
            "room_id": room_metadata.get("id"),
            "room_type_en": room_kind.value,
            "room_type_jp": jp_info["jp_name"],
            "room_abbr_jp": jp_info["abbr"],
            "is_wet_area": jp_info["is_wet"],
            "ownership_decision": analysis["ownership"],
            "decision_label": analysis["japanese_label"],
            "confidence": analysis["confidence"],
            "legal_basis": analysis["legal_basis"],
            "japanese_opinion": analysis["description"]
        }
