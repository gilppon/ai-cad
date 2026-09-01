"""평면 분할(Planar Subdivision) 및 최소 면(Minimal Face) 추출 SSOT.

--------------------------------------------------------------------------
왜 이 모듈이 존재하는가
--------------------------------------------------------------------------
CAD 벡터 도면은 교차점에서 쪼개지지 않은 '긴 선'으로 저장된다.
예) 7x7 격자의 가로선은 x=100..900 을 한 번에 긋는 세그먼트 1개.

이 상태로 위상 알고리즘을 실행하면 **내부 정점이 존재하지 않아** 전부 오작동한다.

  * 차수(degree) 기반 필터: 내부 벽의 끝점이 다른 선의 끝점과 멀어
    degree=0 → 내부 벽 전부 삭제. 실측 8x8 격자: 16선 → 외곽 4선만 생존.
  * PSLG 면 추출: 내부 정점이 없으므로 사이클이 외곽 1개만 산출.

따라서 `subdivide_segments()` 는 **모든 위상 연산보다 먼저** 수행되어야 하는
전제 단계다. `snap_endpoints()` 는 근접한 끝점만 뭉개므로 이 역할을 대신할 수 없다.

두 번째 함수 `minimal_faces()` 는 하프엣지 회전 스윕(rotational sweep)으로
평면의 **최소 면만** 추출한다. 단순 사이클 전수 열거는 방 49개짜리 격자에서
4221개(86배)를 뱉어내므로 사용할 수 없다.

--------------------------------------------------------------------------
좌표계 / 부호 규약
--------------------------------------------------------------------------
화면 좌표계(y 아래 방향)를 그대로 사용한다.
`polygon_signed_area()` 는 CCW(반시계방향)를 양수로 정의하며,
평면 분할에서 **유계인 내부 면은 CCW, 무계인 외부 면은 CW** 로 추출된다.
즉 signed area > 0 이면 실내(방), < 0 이면 외부 → 버린다.

--------------------------------------------------------------------------
제약
--------------------------------------------------------------------------
축 정렬(axis-aligned) 세그먼트에 대해 정확하다. 대각선 입력은
평면 분할 대상에서 제외되고 경고가 기록된다 (CAD 평면도는 walls 가
`refine_lines()` 에서 이미 축 정렬되므로 실사용 경로에서는 발생하지 않는다).
"""
from __future__ import annotations

import bisect
import logging
import math
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

Point = Tuple[float, float]
Segment = Tuple[Point, Point]
Polygon = List[Point]

_EPS = 1e-9


# ---------------------------------------------------------------------------
# 기하 유틸
# ---------------------------------------------------------------------------
def polygon_signed_area(poly: Sequence[Point]) -> float:
    """Shoelace. CCW(반시계방향) = 양수, CW = 음수."""
    n = len(poly)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += (x1 * y2) - (x2 * y1)
    return s / 2.0


def polygon_perimeter(poly: Sequence[Point], closed: bool = True) -> float:
    n = len(poly)
    if n < 2:
        return 0.0
    total = 0.0
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        total += math.hypot(x2 - x1, y2 - y1)
    return total


def _is_axis_aligned(seg: Segment) -> bool:
    (x1, y1), (x2, y2) = seg
    return abs(x1 - x2) <= _EPS or abs(y1 - y2) <= _EPS


def _norm_segment(seg: Segment) -> Optional[Segment]:
    """끝점 정규화 + 퇴화 세그먼트 제거."""
    (x1, y1), (x2, y2) = seg
    if abs(x1 - x2) <= _EPS and abs(y1 - y2) <= _EPS:
        return None
    a, b = (x1, y1), (x2, y2)
    return (a, b) if a <= b else (b, a)


# ---------------------------------------------------------------------------
# 1) 평면 분할
# ---------------------------------------------------------------------------
def subdivide_segments(
    segments: Iterable[Segment],
    min_piece: float = 1.0,
) -> List[Segment]:
    """모든 교차점에서 세그먼트를 분할해 진정한 PSLG를 구성한다.

    축 정렬 세그먼트는 x/y 인덱스 + 이분 탐색으로 O(n log n + k) 에 처리한다.
    대각선 세그먼트는 분할하지 않고 그대로 통과시킨다(경고 기록).

    Args:
        segments: ((x1,y1),(x2,y2)) 시퀀스
        min_piece: 이 길이 미만의 조각은 폐기 (sub-pixel 슬리버 방지)

    Returns:
        분할 + 중복 제거된 세그먼트 리스트
    """
    normed: List[Segment] = []
    for seg in segments:
        s = _norm_segment(seg)
        if s is not None:
            normed.append(s)

    if not normed:
        return []

    horizontals: List[Segment] = []
    verticals: List[Segment] = []
    diagonals: List[Segment] = []

    for seg in normed:
        (x1, y1), (x2, y2) = seg
        if abs(y1 - y2) <= _EPS:
            horizontals.append(seg)
        elif abs(x1 - x2) <= _EPS:
            verticals.append(seg)
        else:
            diagonals.append(seg)

    if diagonals:
        logger.warning(
            "[planar] 대각선 세그먼트 %d개는 평면 분할에서 제외됩니다. "
            "CAD 벽선은 refine_lines() 을 거치면 축 정렬됩니다.",
            len(diagonals),
        )

    vert_by_x: Dict[float, List[Segment]] = {}
    for v in verticals:
        vert_by_x.setdefault(v[0][0], []).append(v)

    horiz_by_y: Dict[float, List[Segment]] = {}
    for h in horizontals:
        horiz_by_y.setdefault(h[0][1], []).append(h)

    xs_sorted: List[float] = sorted(vert_by_x.keys())
    ys_sorted: List[float] = sorted(horiz_by_y.keys())

    out: List[Segment] = []

    # 가로선을 세로선과의 교차점에서 분할
    for h in horizontals:
        (x1, y), (x2, _) = h
        xlo, xhi = (x1, x2) if x1 <= x2 else (x2, x1)

        cuts: Set[float] = {xlo, xhi}
        if xs_sorted:
            lo = bisect.bisect_left(xs_sorted, xlo)
            hi = bisect.bisect_right(xs_sorted, xhi)
            for x in xs_sorted[lo:hi]:
                for v in vert_by_x[x]:
                    ylo, yhi = v[0][1], v[1][1]
                    if ylo > yhi:
                        ylo, yhi = yhi, ylo
                    if ylo - _EPS <= y <= yhi + _EPS:
                        cuts.add(x)
                        break

        pts = sorted(cuts)
        for a, b in zip(pts, pts[1:]):
            if (b - a) >= min_piece:
                out.append(((a, y), (b, y)))

    # 세로선을 가로선과의 교차점에서 분할
    for v in verticals:
        (x, y1), (_, y2) = v
        ylo, yhi = (y1, y2) if y1 <= y2 else (y2, y1)

        cuts = {ylo, yhi}
        if ys_sorted:
            lo = bisect.bisect_left(ys_sorted, ylo)
            hi = bisect.bisect_right(ys_sorted, yhi)
            for y in ys_sorted[lo:hi]:
                for h in horiz_by_y[y]:
                    xlo, xhi = h[0][0], h[1][0]
                    if xlo > xhi:
                        xlo, xhi = xhi, xlo
                    if xlo - _EPS <= x <= xhi + _EPS:
                        cuts.add(y)
                        break

        pts = sorted(cuts)
        for a, b in zip(pts, pts[1:]):
            if (b - a) >= min_piece:
                out.append(((x, a), (x, b)))

    out.extend(diagonals)

    # 중복 제거 (동일 선분이 여러 원본에서 유래할 수 있음)
    seen: Set[Segment] = set()
    uniq: List[Segment] = []
    for s in out:
        if s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    return uniq


# ---------------------------------------------------------------------------
# 2) 최소 면 추출 (하프엣지 회전 스윕)
# ---------------------------------------------------------------------------
def minimal_faces(segments: Iterable[Segment]) -> List[Polygon]:
    """평면 분할된 세그먼트 집합에서 최소 면만 추출한다.

    하프엣지 회전 스윕: 방향 간선 (u→v) 의 다음 간선은, v 를 중심으로
    v→u 방향에서 **시계방향으로 가장 가까운** 이웃 v→w 다.
    각 하프엣지는 정확히 하나의 면에 속하므로 전체 비용은 O(V + E).

    이 규칙에 의해 **내부 면은 CCW(양의 면적), 외부 면은 CW(음의 면적)** 로
    추출된다. 호출부는 양의 면적만 취하면 외곽선을 자동 배제할 수 있다.

    Returns:
        꼭짓점 리스트의 리스트. 외부 면도 포함되므로 호출부에서
        `polygon_signed_area(poly) > 0` 으로 걸러야 한다.
    """
    adj: Dict[Point, List[Point]] = {}
    for seg in segments:
        a, b = seg
        if a == b:
            continue
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    if not adj:
        return []

    # 각 정점의 이웃을 각도 오름차순으로 정렬 + 역방향 인덱스
    ring: Dict[Point, List[Point]] = {}
    rank: Dict[Point, Dict[Point, int]] = {}
    for v, nbrs in adj.items():
        uniq = sorted(set(nbrs), key=lambda w: math.atan2(w[1] - v[1], w[0] - v[0]))
        ring[v] = uniq
        rank[v] = {w: i for i, w in enumerate(uniq)}

    visited: Set[Tuple[Point, Point]] = set()
    faces: List[Polygon] = []

    for u0 in adj:
        for v0 in adj[u0]:
            if (u0, v0) in visited:
                continue

            face: List[Point] = []
            u, v = u0, v0
            while (u, v) not in visited:
                visited.add((u, v))
                face.append(u)

                nbrs = ring.get(v)
                idx = rank.get(v, {}).get(u)
                if nbrs is None or idx is None:
                    break
                # 각도 오름차순에서 u 의 직전 이웃 = u 에서 시계방향 최인접
                w = nbrs[(idx - 1) % len(nbrs)]
                u, v = v, w

            if len(face) >= 3:
                faces.append(face)

    return faces


def extract_interior_faces(
    segments: Iterable[Segment],
    min_area: float = 0.0,
) -> List[Polygon]:
    """평면 분할 → 최소 면 추출 → 외부 면/소면적 제거까지 한 번에 수행.

    Args:
        segments: 원시 세그먼트 (분할 전 상태여도 내부에서 처리한다)
        min_area: 이 면적 미만의 면은 폐기 (벽 두께로 생긴 슬리버 제거)

    Returns:
        실내 면(방 후보) 폴리곤 리스트. CCW 순서.
    """
    subdivided = subdivide_segments(segments)
    faces = minimal_faces(subdivided)

    out: List[Polygon] = []
    for poly in faces:
        area = polygon_signed_area(poly)
        if area <= 0.0:  # 외부 면(CW) 및 퇴화 면
            continue
        if area < min_area:
            continue
        out.append(poly)
    return out
