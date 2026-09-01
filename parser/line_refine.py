from __future__ import annotations

from dataclasses import dataclass
from core import planar as _planar
from typing import List, Tuple, Dict, Any, Set
import math


# -----------------------------
# Data model
# -----------------------------
@dataclass(frozen=True)
class Line:
    x1: int
    y1: int
    x2: int
    y2: int

    def length(self) -> float:
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1
        return math.hypot(dx, dy)

    def is_degenerate(self) -> bool:
        return self.x1 == self.x2 and self.y1 == self.y2

    def angle_deg(self) -> float:
        """Angle in degrees [0, 180)."""
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1
        if dx == 0 and dy == 0:
            return 0.0
        ang = abs(math.degrees(math.atan2(dy, dx))) % 180.0
        return ang

    def is_horizontal(self, tol_deg: float = 7.0) -> bool:
        a = self.angle_deg()
        return min(abs(a - 0), abs(a - 180)) <= tol_deg

    def is_vertical(self, tol_deg: float = 7.0) -> bool:
        a = self.angle_deg()
        return abs(a - 90) <= tol_deg


# -----------------------------
# Helpers
# -----------------------------
def _round_to_int(v: float) -> int:
    return int(round(v))


def _norm_endpoints(l: Line) -> Line:
    """Sort endpoints for stability (not geometric canonical, but deterministic)."""
    if (l.x1, l.y1) <= (l.x2, l.y2):
        return l
    return Line(l.x2, l.y2, l.x1, l.y1)


def _snap_to_axis_keep(l: Line) -> Line:
    """
    IMPORTANT:
    - Never drop the line.
    - Always "snap" to the nearest axis (horizontal or vertical)
      by collapsing to avg y or avg x.
    """
    if l.is_degenerate():
        return l

    dx = l.x2 - l.x1
    dy = l.y2 - l.y1

    # decide nearest axis
    # if closer to horizontal => horizontal, else vertical
    if abs(dx) >= abs(dy):
        # horizontal: y fixed to mid
        y = _round_to_int((l.y1 + l.y2) / 2.0)
        x1, x2 = sorted([l.x1, l.x2])
        return _norm_endpoints(Line(x1, y, x2, y))
    else:
        # vertical: x fixed to mid
        x = _round_to_int((l.x1 + l.x2) / 2.0)
        y1, y2 = sorted([l.y1, l.y2])
        return _norm_endpoints(Line(x, y1, x, y2))


def _point_dist(p: Tuple[int, int], q: Tuple[int, int]) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _bbox_overlap_1d(a1: int, a2: int, b1: int, b2: int) -> bool:
    lo1, hi1 = (a1, a2) if a1 <= a2 else (a2, a1)
    lo2, hi2 = (b1, b2) if b1 <= b2 else (b2, b1)
    return not (hi1 < lo2 or hi2 < lo1)


# -----------------------------
# Core
# -----------------------------
def refine_lines(
    raw_lines: List[Tuple[int, int, int, int]],
    min_len: float = 60.0,
    snap_tol_deg: float = 3.0,  # kept for compatibility, but we do not drop lines based on it
) -> List[Line]:
    """
    Convert raw tuples to Lines, filter short/degenerate lines,
    and snap to nearest axis (never drop based on angle).
    """
    out: List[Line] = []
    for (x1, y1, x2, y2) in raw_lines:
        l = Line(int(x1), int(y1), int(x2), int(y2))
        if l.is_degenerate():
            continue
        if l.length() < float(min_len):
            continue

        # Snap to axis but never discard (prevents "walls disappear" bug)
        l2 = _snap_to_axis_keep(l)
        if l2.is_degenerate():
            continue
        if l2.length() < float(min_len):
            continue
        out.append(l2)

    return out


def dedup_exact(lines: List[Line]) -> List[Line]:
    """Remove exact duplicates."""
    seen = set()
    out: List[Line] = []
    for l in lines:
        ln = _norm_endpoints(l)
        key = (ln.x1, ln.y1, ln.x2, ln.y2)
        if key in seen:
            continue
        seen.add(key)
        out.append(ln)
    return out


def merge_collinear_segments(
    lines: List[Line],
    dist_tol: float = 5.0,  # Phase 3: Relaxed from 3.0
    gap_tol: float = 25.0,  # Phase 3: Relaxed from 15.0
) -> List[Line]:
    """
    Merge collinear (axis-aligned) segments that overlap or have small gaps.
    Assumes input is already snapped to axis.
    """
    if not lines:
        return []

    horizontals = [l for l in lines if l.y1 == l.y2]
    verticals = [l for l in lines if l.x1 == l.x2]

    merged: List[Line] = []

    # Merge horizontals: same y, x ranges overlap or within gap_tol, and y within dist_tol
    horizontals.sort(key=lambda l: (l.y1, min(l.x1, l.x2), max(l.x1, l.x2)))
    i = 0
    while i < len(horizontals):
        cur = horizontals[i]
        y = cur.y1
        xlo = min(cur.x1, cur.x2)
        xhi = max(cur.x1, cur.x2)

        j = i + 1
        while j < len(horizontals):
            nxt = horizontals[j]
            if abs(nxt.y1 - y) > dist_tol:
                break
            nxlo = min(nxt.x1, nxt.x2)
            nxhi = max(nxt.x1, nxt.x2)

            # overlap or small gap?
            if nxlo <= xhi + gap_tol:
                xhi = max(xhi, nxhi)
                j += 1
                continue
            break

        merged.append(_norm_endpoints(Line(xlo, y, xhi, y)))
        i = j

    # Merge verticals: same x, y ranges overlap or within gap_tol, and x within dist_tol
    verticals.sort(key=lambda l: (l.x1, min(l.y1, l.y2), max(l.y1, l.y2)))
    i = 0
    while i < len(verticals):
        cur = verticals[i]
        x = cur.x1
        ylo = min(cur.y1, cur.y2)
        yhi = max(cur.y1, cur.y2)

        j = i + 1
        while j < len(verticals):
            nxt = verticals[j]
            if abs(nxt.x1 - x) > dist_tol:
                break
            nylo = min(nxt.y1, nxt.y2)
            nyhi = max(nxt.y1, nxt.y2)

            if nylo <= yhi + gap_tol:
                yhi = max(yhi, nyhi)
                j += 1
                continue
            break

        merged.append(_norm_endpoints(Line(x, ylo, x, yhi)))
        i = j

    return merged


def snap_endpoints(lines: List[Line], snap_dist: float = 15.0) -> List[Line]:
    """
    Snap endpoints that are within snap_dist to the same coordinate (gridless).
    This helps line connectivity.
    """
    if not lines:
        return []

    # collect endpoints
    pts: List[Tuple[int, int]] = []
    for l in lines:
        pts.append((l.x1, l.y1))
        pts.append((l.x2, l.y2))

    # union-find like clustering (simple O(n^2), OK for MVP)
    used = [False] * len(pts)
    clusters: List[List[int]] = []

    for i in range(len(pts)):
        if used[i]:
            continue
        used[i] = True
        cluster = [i]
        changed = True
        while changed:
            changed = False
            for j in range(len(pts)):
                if used[j]:
                    continue
                # if close to any point in cluster -> join
                for k in cluster:
                    if _point_dist(pts[j], pts[k]) <= snap_dist:
                        used[j] = True
                        cluster.append(j)
                        changed = True
                        break
        clusters.append(cluster)

    # compute cluster centers
    centers: Dict[int, Tuple[int, int]] = {}
    for c in clusters:
        xs = [pts[i][0] for i in c]
        ys = [pts[i][1] for i in c]
        cx = _round_to_int(sum(xs) / len(xs))
        cy = _round_to_int(sum(ys) / len(ys))
        for idx in c:
            centers[idx] = (cx, cy)

    # rebuild lines
    out: List[Line] = []
    p_idx = 0
    for l in lines:
        p1 = centers[p_idx]
        p2 = centers[p_idx + 1]
        p_idx += 2
        out.append(_norm_endpoints(Line(p1[0], p1[1], p2[0], p2[1])))

    return out


def merge_parallel_pairs(lines: List[Line], angle_tol: float = 2.0, dist_tol: float = 18.0) -> List[Line]:
    """
    In this MVP, after snap_to_axis_keep, angles are already 0/90.
    So this becomes a light cleanup: merge near-parallel duplicates by collapsing y/x within dist_tol.
    """
    if not lines:
        return []

    # Separate horizontals and verticals
    hs = [l for l in lines if l.y1 == l.y2]
    vs = [l for l in lines if l.x1 == l.x2]

    # cluster horizontals by y within dist_tol, then merge ranges per cluster
    hs.sort(key=lambda l: l.y1)
    merged: List[Line] = []

    i = 0
    while i < len(hs):
        base_y = hs[i].y1
        cluster = [hs[i]]
        j = i + 1
        while j < len(hs) and abs(hs[j].y1 - base_y) <= dist_tol:
            cluster.append(hs[j])
            j += 1

        # merge by x overlap / adjacency
        cluster.sort(key=lambda l: min(l.x1, l.x2))
        cur = cluster[0]
        y = _round_to_int(sum([c.y1 for c in cluster]) / len(cluster))
        xlo = min(cur.x1, cur.x2)
        xhi = max(cur.x1, cur.x2)
        for c in cluster[1:]:
            cxlo = min(c.x1, c.x2)
            cxhi = max(c.x1, c.x2)
            if cxlo <= xhi + 1:
                xhi = max(xhi, cxhi)
            else:
                merged.append(_norm_endpoints(Line(xlo, y, xhi, y)))
                xlo, xhi = cxlo, cxhi
        merged.append(_norm_endpoints(Line(xlo, y, xhi, y)))
        i = j

    # cluster verticals by x within dist_tol, then merge ranges per cluster
    vs.sort(key=lambda l: l.x1)
    i = 0
    while i < len(vs):
        base_x = vs[i].x1
        cluster = [vs[i]]
        j = i + 1
        while j < len(vs) and abs(vs[j].x1 - base_x) <= dist_tol:
            cluster.append(vs[j])
            j += 1

        cluster.sort(key=lambda l: min(l.y1, l.y2))
        cur = cluster[0]
        x = _round_to_int(sum([c.x1 for c in cluster]) / len(cluster))
        ylo = min(cur.y1, cur.y2)
        yhi = max(cur.y1, cur.y2)
        for c in cluster[1:]:
            cylo = min(c.y1, c.y2)
            cyhi = max(c.yhi if hasattr(c, "yhi") else max(c.y1, c.y2), max(c.y1, c.y2))
            if cylo <= yhi + 1:
                yhi = max(yhi, cyhi)
            else:
                merged.append(_norm_endpoints(Line(x, ylo, x, yhi)))
                ylo, yhi = cylo, cyhi
        merged.append(_norm_endpoints(Line(x, ylo, x, yhi)))
        i = j

    return dedup_exact(merged)


# -----------------------------
# Planar subdivision (PSLG precondition)
# -----------------------------
def subdivide_at_intersections(
    lines: List[Line],
    min_piece: float = 1.0,
) -> List[Line]:
    """
    평면 분할: 축 정렬 세그먼트를 모든 교차점에서 분할한다.

    구현은 core/planar.py 가 유일한 SSOT이며, 본 함수는 Line <-> tuple 어댑터다.

    ------------------------------------------------------------------
    왜 이 단계가 필수인가 (결함 C10 근본 원인)
    ------------------------------------------------------------------
    CAD 벡터 도면은 교차점에서 쪼개지지 않은 '긴 선'으로 저장된다.
    예) 8x8 격자의 가로선은 x=100..900 을 한 번에 긋는 세그먼트 1개.

    이 상태로 위상 알고리즘을 돌리면 내부 정점이 존재하지 않아 전부 오작동한다.

      * filter_structural_walls() 는 degree 를 '끝점 근접'으로만 계산한다.
        내부 벽(x=200 세로선)의 끝점 (200,100)/(200,900) 은 다른 선의 끝점과
        멀리 떨어져 있어 degree=0 -> 전부 삭제된다.
        실측: 8x8 격자 16선 -> 외곽 4선만 생존, 64실 -> 1실.

      * PSLG 최소 면(minimal face) 추출이 불가능하다.
        내부 정점 자체가 없으므로 사이클이 외곽 하나만 산출된다.

    따라서 본 함수는 '모든 위상 연산보다 먼저' 수행되어야 하는 전제 단계다.
    snap_endpoints() 는 근접 끝점만 뭉개므로 이 역할을 대신할 수 없다.

    Args:
        lines: refine_lines() 을 거쳐 축 정렬된 Line 리스트
        min_piece: 이 길이 미만의 조각은 폐기 (sub-pixel 슬리버 방지)

    Returns:
        교차점에서 분할되고 중복이 제거된 Line 리스트
    """
    if not lines:
        return []

    segs = [((float(l.x1), float(l.y1)), (float(l.x2), float(l.y2))) for l in lines]
    out_segs = _planar.subdivide_segments(segs, min_piece=min_piece)

    out: List[Line] = []
    for (x1, y1), (x2, y2) in out_segs:
        out.append(
            _norm_endpoints(
                Line(int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)))
            )
        )
    return dedup_exact(out)


# -----------------------------
# Additional filters
# -----------------------------
def filter_axis_aligned(lines: List[Line], tol_deg: float = 7.0) -> List[Line]:
    """
    Keep only near-horizontal or near-vertical lines.
    (After snapping, most should be exact, but keep for safety.)
    """
    out: List[Line] = []
    for l in lines:
        if l.is_degenerate():
            continue
        a = l.angle_deg()
        if min(abs(a - 0), abs(a - 90), abs(a - 180)) <= tol_deg:
            out.append(l)
    return out


def filter_structural_walls(
    lines: List[Line],
    min_len_ratio: float = 0.03,
    min_degree: int = 1,
    join_tol: int = 18,
) -> List[Line]:
    """
    Structural wall heuristic filter (relaxed):
    - Keep sufficiently long lines
    - Keep lines connected to >= min_degree other lines (within join_tol at endpoints)
    """
    if not lines:
        return []

    max_len = max(l.length() for l in lines)
    min_len = max_len * float(min_len_ratio)

    long_lines = [l for l in lines if l.length() >= min_len and not l.is_degenerate()]
    if not long_lines:
        return []

    def near(p, q, tol=join_tol) -> bool:
        return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol

    degrees = {id(l): 0 for l in long_lines}

    for i, a in enumerate(long_lines):
        for b in long_lines[i + 1:]:
            if (
                near((a.x1, a.y1), (b.x1, b.y1)) or
                near((a.x1, a.y1), (b.x2, b.y2)) or
                near((a.x2, a.y2), (b.x1, b.y1)) or
                near((a.x2, a.y2), (b.x2, b.y2))
            ):
                degrees[id(a)] += 1
                degrees[id(b)] += 1

    return [l for l in long_lines if degrees[id(l)] >= int(min_degree)]
