"""包絡処理/勝ち負け処理 — 부재 겹침 제소자 (SP3/Q-1).

국토교통성 BIM 가이드라인이 요구하는 수량 중복 방지 처리의 MVP 구현:
  1. 중복 세그먼트 제거: 동일 선분(허용 오차 내)으로 정규화되는 벽은 1회만 계상
  2. 코너 보정(勝ち負け): 한 점을 공유하는 벽 끝단마다 자신 두께의 절반을 공제하여
     모서리 이중 계상을 제거

정밀한 부재 상호 관계(기둥 관입, 슬래브 관통 등)는 후속 고도화 대상이며,
본 모듈은 보수공사 견적의 실무 허용 오차(±2%) 수준을 목표로 한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

_COORD_TOL = 1e-6


@dataclass
class ResolvedWall:
    wall_id: int
    length_px: float          # 보정 후 순 길이(px)
    raw_length_px: float      # 보정 전 원시 길이(px)
    thickness_px: float
    corner_deductions_px: int  # 공제 적용 끝단 수


def _norm_endpoint(p: Dict[str, float]) -> Tuple[float, float]:
    return (round(float(p.get("x", 0.0)), 6), round(float(p.get("y", 0.0)), 6))


def resolve_wall_overlaps(walls: List[Dict]) -> List[ResolvedWall]:
    """
    벽 리스트에서 (1) 중복 세그먼트를 제거하고 (2) 교차점 코너 공제를 적용한다.

    walls 요소 형식: {"id": int, "p1": {"x","y"}, "p2": {"x","y"}, "thickness_px": float?}
    """
    # --- 1. 중복 세그먼트 제거 ---
    seen: set = set()
    unique_walls = []
    for w in walls:
        a = _norm_endpoint(w.get("p1", {}))
        b = _norm_endpoint(w.get("p2", {}))
        key = tuple(sorted([a, b]))
        if key in seen:
            logger.debug(f"[OverlapResolver] Duplicate segment removed: wall id={w.get('id')}")
            continue
        seen.add(key)
        unique_walls.append(w)

    # --- 2. 엔드포인트 공유 지수 작성 ---
    endpoint_use_count: Dict[Tuple[float, float], int] = {}
    for w in unique_walls:
        endpoint_use_count[_norm_endpoint(w.get("p1", {}))] = (
            endpoint_use_count.get(_norm_endpoint(w.get("p1", {})), 0) + 1)
        endpoint_use_count[_norm_endpoint(w.get("p2", {}))] = (
            endpoint_use_count.get(_norm_endpoint(w.get("p2", {})), 0) + 1)

    resolved: List[ResolvedWall] = []
    for w in unique_walls:
        raw_len = (
            (_norm_endpoint(w["p2"])[0] - _norm_endpoint(w["p1"])[0]) ** 2
            + (_norm_endpoint(w["p2"])[1] - _norm_endpoint(w["p1"])[1]) ** 2
        ) ** 0.5
        thickness = float(w.get("thickness_px", 0.0) or 0.0)

        deductions = 0
        net_len = raw_len
        if thickness > 0:
            for end in ("p1", "p2"):
                pt = _norm_endpoint(w[end])
                if endpoint_use_count.get(pt, 0) > 1:
                    # 다른 벽과 맞닿는 끝단 → 두께 절반 공제 (勝ち負け処理)
                    net_len -= thickness / 2.0
                    deductions += 1
        net_len = max(net_len, 0.0)

        resolved.append(ResolvedWall(
            wall_id=int(w.get("id", -1)),
            length_px=net_len,
            raw_length_px=raw_len,
            thickness_px=thickness,
            corner_deductions_px=deductions,
        ))

    total_raw = sum(r.raw_length_px for r in resolved)
    total_net = sum(r.length_px for r in resolved)
    if total_raw > 0 and total_raw != total_net:
        logger.info(
            f"[OverlapResolver] 包絡処理 applied: raw {total_raw:.1f}px -> net {total_net:.1f}px "
            f"(-{(total_raw - total_net) / total_raw * 100:.2f}%)"
        )
    return resolved
