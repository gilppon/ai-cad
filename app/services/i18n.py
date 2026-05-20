# -*- coding: utf-8 -*-
from typing import Dict, Any

class JPTranslationEngine:
    """
    일본 주택 도면 공간 시맨틱스 번역 및 다국어(i18n) 통합 엔진.
    영문 방 명칭을 일본 현지 표준 명칭(LDK, 洋室, トイレ 등)으로 매핑하여
    공용부/전유부 판정 및 PDF 리포트의 가독성을 극대화합니다.
    """
    
    # 1. 영문 방 타입 -> 일본 현지 표준 명칭 및 약어 매핑 테이블
    ROOM_MAP: Dict[str, Dict[str, str]] = {
        "living": {"name": "居間 (LDK)", "abbr": "LDK"},
        "living_room": {"name": "居間 (LDK)", "abbr": "LDK"},
        "ldk": {"name": "LDK", "abbr": "LDK"},
        "bedroom": {"name": "洋室", "abbr": "洋室"},
        "bed_room": {"name": "洋室", "abbr": "洋室"},
        "room": {"name": "洋室", "abbr": "洋室"},
        "tatami": {"name": "和室", "abbr": "和室"},
        "japanese_room": {"name": "和室", "abbr": "和室"},
        "kitchen": {"name": "台所 (K)", "abbr": "K"},
        "dining": {"name": "食堂 (D)", "abbr": "D"},
        "toilet": {"name": "トイレ (WC)", "abbr": "WC"},
        "wc": {"name": "トイレ (WC)", "abbr": "WC"},
        "restroom": {"name": "トイレ (WC)", "abbr": "WC"},
        "bathroom": {"name": "浴室 (UB)", "abbr": "UB"},
        "bath": {"name": "浴室 (UB)", "abbr": "UB"},
        "utility": {"name": "ユーティリティ (UT)", "abbr": "UT"},
        "ut": {"name": "ユーティリティ (UT)", "abbr": "UT"},
        "closet": {"name": "クローゼット (CL)", "abbr": "CL"},
        "cl": {"name": "クローゼット (CL)", "abbr": "CL"},
        "entrance": {"name": "玄関", "abbr": "玄関"},
        "corridor": {"name": "廊下", "abbr": "廊下"},
        "hallway": {"name": "廊下", "abbr": "廊下"},
        "balcony": {"name": "バルコニー", "abbr": "バルコニー"},
        "pipe_space": {"name": "パイプスペース (PS)", "abbr": "PS"},
        "ps": {"name": "パイプスペース (PS)", "abbr": "PS"},
        "duct_space": {"name": "ダクトスペース (DS)", "abbr": "DS"},
        "ds": {"name": "ダクトスペース (DS)", "abbr": "DS"},
        "meter_box": {"name": "メーターボックス (MB)", "abbr": "MB"},
        "mb": {"name": "メーターボックス (MB)", "abbr": "MB"},
    }
    
    # 2. 일반 UI 다국어 사전 (i18n 용도)
    UI_DICTIONARY: Dict[str, Dict[str, str]] = {
        "title": {
            "en": "Leakage 3D Diagnosis System",
            "ja": "漏水3D診断システム (Japanbuild-Leak3D)"
        },
        "report_header": {
            "en": "Leakage Diagnosis Report",
            "ja": "漏水診断報告書"
        },
        "inspector": {
            "en": "Diagnostic Engineer",
            "ja": "診断技術者"
        },
        "proprietary": {
            "en": "Proprietary Area",
            "ja": "専有部分"
        },
        "common": {
            "en": "Common Area",
            "ja": "共用部分"
        },
        "common_exclusive": {
            "en": "Common Area (Exclusive Use)",
            "ja": "共用部分 (専用使用権付き)"
        },
        "opinion_required": {
            "en": "Detailed Investigation Required",
            "ja": "要精密調査"
        }
    }

    @classmethod
    def translate_room(cls, room_type_eng: str) -> Dict[str, str]:
        """
        영문 방 명칭을 일본 현지 표준 명칭과 공식 약어로 정형 변환합니다.
        """
        if not room_type_eng:
            return {"name": "用途不明", "abbr": "不明"}
            
        key_lower = room_type_eng.lower().strip()
        
        # 1차 정확히 일치하는 맵핑 탐색
        if key_lower in cls.ROOM_MAP:
            return cls.ROOM_MAP[key_lower]
            
        # 2차 부분 단어 탐색
        for k, val in cls.ROOM_MAP.items():
            if k in key_lower:
                return val
                
        # 기본 fallback
        return {"name": f"洋室 ({room_type_eng})", "abbr": room_type_eng}

    @classmethod
    def translate_text(cls, key: str, lang: str = "ja") -> str:
        """
        일반 UI 텍스트를 대상 언어에 맞춰 번역합니다.
        """
        if key in cls.UI_DICTIONARY:
            return cls.UI_DICTIONARY[key].get(lang, cls.UI_DICTIONARY[key].get("ja"))
        return key
