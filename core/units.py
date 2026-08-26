"""단위 환산 SSOT (SP2/H-5 → SP4 완성).

프로젝트 전역의 px↔mm↔m 환산 상수·함수를 여기로 수렴시킨다.
법규 판정(compliance)과 수량산출(takeoff)이 서로 다른 기본 스케일을
참조해 판정 오차를 낸 사례(SP1/L-1)의 재발을 차단한다.
"""
from __future__ import annotations

# 레거시 기본 스케일: 100px = 1m.
# 스케일 정보가 없는 페이로드에 한한 최후 폴백이며, 프로젝트에서 유일한 정의다.
DEFAULT_PX_TO_M = 0.01

# 파이프라인 래스터 경로의 선언 스케일 (core/engine.py save_rooms_json)
RASTER_PIXEL_TO_MM = 5.0


def px_to_m(px: float, pixel_to_mm: float | None = None) -> float:
    """px 길이를 미터로. pixel_to_mm 미지정 시 레거시 폴백(0.01 m/px) 사용."""
    if pixel_to_mm and pixel_to_mm > 0:
        return float(px) * float(pixel_to_mm) / 1000.0
    return float(px) * DEFAULT_PX_TO_M


def pixel_to_mm_to_px_to_m(pixel_to_mm: float) -> float:
    """pixel_to_mm 스케일을 m/px 계수로 변환."""
    if not pixel_to_mm or pixel_to_mm <= 0:
        return DEFAULT_PX_TO_M
    return float(pixel_to_mm) / 1000.0


def mm_to_m(x_mm: float) -> float:
    return float(x_mm) / 1000.0


def m2_from_px2(area_px2: float, px_to_m_factor: float) -> float:
    """px² 면적을 m²로. px_to_m_factor는 m/px 계수."""
    return float(area_px2) * (float(px_to_m_factor) ** 2)
