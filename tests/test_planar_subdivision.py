# -*- coding: utf-8 -*-
"""평면 분할(Planar Subdivision) 및 PSLG 최소 면 추출 회귀 테스트.

방어 대상 결함:
  C10 - filter_structural_walls() 가 내부 벽을 전부 삭제 (8x8 격자 64실 -> 1실)
  D1  - PSLG 가 교차점 분할을 하지 않아 최소 면이 존재하지 않음
  D2  - 단순 사이클 전수 열거로 복합(가짜) 폴리곤 폭발 (7x7 -> 4221개)
  D3  - len(path) < 12 하드 제한으로 12변 초과 폴리곤 누락
"""
from __future__ import annotations

import math

import pytest

from core import planar
from engine.geometry.pslg_topology import PSLGTopologyEngine
from parser.line_refine import (
    Line,
    filter_structural_walls,
    subdivide_at_intersections,
)


# ---------------------------------------------------------------------------
# 픽스처 헬퍼
# ---------------------------------------------------------------------------
def grid_segments(cols: int, rows: int, cell: float = 100.0, ox: float = 0.0, oy: float = 0.0):
    """미분할 격자. 각 격자선이 통째로 1개 세그먼트 = 실CAD 벡터와 동일 형태."""
    segs = []
    for c in range(cols + 1):
        x = ox + c * cell
        segs.append(((x, oy), (x, oy + rows * cell)))
    for r in range(rows + 1):
        y = oy + r * cell
        segs.append(((ox, y), (ox + cols * cell, y)))
    return segs


def to_lines(segs) -> list:
    return [Line(int(x1), int(y1), int(x2), int(y2)) for (x1, y1), (x2, y2) in segs]


# ---------------------------------------------------------------------------
# 1) 평면 분할
# ---------------------------------------------------------------------------
class TestSubdivideSegments:
    def test_unsplit_grid_is_split_at_every_crossing(self):
        """D1 회귀: 미분할 격자가 교차점에서 분할되어야 한다."""
        segs = grid_segments(7, 7)
        assert len(segs) == 16  # 8 + 8 원시 선

        sub = planar.subdivide_segments(segs)
        # 8개 가로선 x 7조각 + 8개 세로선 x 7조각 = 112
        assert len(sub) == 112, f"기대 112, 실제 {len(sub)}"

    def test_subdivision_is_idempotent(self):
        """이미 분할된 입력에 재적용해도 결과가 불변이어야 한다."""
        segs = grid_segments(5, 5)
        once = planar.subdivide_segments(segs)
        twice = planar.subdivide_segments(once)
        assert sorted(once) == sorted(twice)

    def test_degenerate_segments_dropped(self):
        segs = [((0.0, 0.0), (0.0, 0.0)), ((0.0, 0.0), (100.0, 0.0))]
        sub = planar.subdivide_segments(segs)
        assert all(s[0] != s[1] for s in sub)

    def test_duplicate_segments_collapsed(self):
        segs = [((0.0, 0.0), (100.0, 0.0)), ((0.0, 0.0), (100.0, 0.0))]
        sub = planar.subdivide_segments(segs)
        assert len(sub) == 1

    def test_t_junction_creates_interior_vertex(self):
        """T 정션: 세로선이 가로선 중간에 닿으면 가로선이 둘로 쪼개져야 한다."""
        segs = [((0.0, 0.0), (200.0, 0.0)), ((100.0, 0.0), (100.0, 100.0))]
        sub = planar.subdivide_segments(segs)
        horizontals = sorted(s for s in sub if s[0][1] == s[1][1])
        assert len(horizontals) == 2, f"T정션 미분할: {horizontals}"
        assert horizontals[0] == ((0.0, 0.0), (100.0, 0.0))
        assert horizontals[1] == ((100.0, 0.0), (200.0, 0.0))

    def test_empty_input(self):
        assert planar.subdivide_segments([]) == []


# ---------------------------------------------------------------------------
# 2) 최소 면 추출
# ---------------------------------------------------------------------------
class TestMinimalFaces:
    @pytest.mark.parametrize(
        "cols,rows",
        [(1, 1), (2, 1), (3, 2), (7, 7), (8, 8)],
    )
    def test_grid_yields_exactly_one_face_per_cell(self, cols, rows):
        """D2 회귀: 복합 사이클이 섞이면 개수가 초과된다."""
        faces = planar.extract_interior_faces(grid_segments(cols, rows), min_area=1.0)
        assert len(faces) == cols * rows, (
            f"{cols}x{rows}: 기대 {cols * rows}실, 실제 {len(faces)} (복합 사이클 혼입?)"
        )

    @pytest.mark.parametrize("cols,rows", [(7, 7), (8, 8)])
    def test_every_face_has_unit_cell_area(self, cols, rows):
        """D2 회귀: 모든 면이 최소 면(=1칸)이어야 한다."""
        unit = 100.0 * 100.0
        faces = planar.extract_interior_faces(grid_segments(cols, rows), min_area=1.0)
        for poly in faces:
            assert abs(planar.polygon_signed_area(poly) - unit) < 1.0, (
                f"복합 사이클 검출: area={planar.polygon_signed_area(poly)} (기대 {unit})"
            )

    def test_exterior_face_is_discarded(self):
        """외곽선(CW, 음의 면적)은 방으로 반환되면 안 된다."""
        square = [
            ((0.0, 0.0), (100.0, 0.0)),
            ((100.0, 0.0), (100.0, 100.0)),
            ((100.0, 100.0), (0.0, 100.0)),
            ((0.0, 100.0), (0.0, 0.0)),
        ]
        assert len(planar.minimal_faces(planar.subdivide_segments(square))) == 2  # 내부 + 외부
        assert len(planar.extract_interior_faces(square, min_area=1.0)) == 1

    def test_polygons_with_more_than_12_vertices_are_extracted(self):
        """D3 회귀: 구 버전은 len(path) < 12 제한으로 이 폴리곤을 놓쳤다."""
        n = 20
        radius = 500.0
        # 20각형을 축 정렬 세그먼트로 근사
        poly = [
            (round(radius * math.cos(2 * math.pi * i / n), 3),
             round(radius * math.sin(2 * math.pi * i / n), 3))
            for i in range(n)
        ]
        # 축 정렬 스텝으로 연결 (계단형 근사)
        segs = []
        for i in range(n):
            ax, ay = poly[i]
            bx, by = poly[(i + 1) % n]
            mid = (round(bx, 3), round(ay, 3))
            segs.append(((ax, ay), mid))
            segs.append((mid, (bx, by)))

        faces = planar.extract_interior_faces(segs, min_area=1000.0)
        assert faces, "12변 초과 폴리곤이 추출되지 않음 (D3 재발)"
        largest = max(faces, key=planar.polygon_signed_area)
        assert len(largest) >= 4  # 근사된 계단형이므로 정확한 변수는 보장하지 않음

    def test_signed_area_sign_convention(self):
        """CCW = 양수, CW = 음수."""
        ccw = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        cw = list(reversed(ccw))
        assert planar.polygon_signed_area(ccw) > 0
        assert planar.polygon_signed_area(cw) < 0

    def test_no_faces_for_open_polyline(self):
        segs = [((0.0, 0.0), (100.0, 0.0)), ((100.0, 0.0), (100.0, 100.0))]
        assert planar.extract_interior_faces(segs, min_area=1.0) == []

    def test_perimeter(self):
        square = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
        assert planar.polygon_perimeter(square) == pytest.approx(400.0)


# ---------------------------------------------------------------------------
# 3) PSLG 엔진 (공개 API 호환성 + 결함 회귀)
# ---------------------------------------------------------------------------
class TestPSLGTopologyEngine:
    def test_extracts_all_rooms_from_unsplit_grid(self):
        """D1 회귀: 구 버전은 여기서 1개(외곽만)를 반환했다."""
        eng = PSLGTopologyEngine(snap_tolerance=3.0, min_room_area=100.0)
        rooms = eng.extract_room_polygons(grid_segments(7, 7))
        assert len(rooms) == 49, f"기대 49실, 실제 {len(rooms)}"

    def test_no_composite_cycles(self):
        """D2 회귀: 구 버전은 4221개를 반환했다."""
        eng = PSLGTopologyEngine(snap_tolerance=3.0, min_room_area=100.0)
        rooms = eng.extract_room_polygons(grid_segments(7, 7))
        unit = 100.0 * 100.0
        for r in rooms:
            assert abs(r["area_m2"] - unit) < 1.0, (
                f"복합 사이클: room={r['room_id']} area={r['area_m2']}"
            )

    def test_returned_schema(self):
        eng = PSLGTopologyEngine(min_room_area=100.0)
        rooms = eng.extract_room_polygons(grid_segments(2, 1))
        assert len(rooms) == 2
        for i, r in enumerate(rooms, start=1):
            assert set(r.keys()) == {"room_id", "vertices", "area_m2", "perimeter_m"}
            assert r["room_id"] == f"ROOM_{i:02d}"
            assert len(r["vertices"]) == 4
            assert r["area_m2"] == pytest.approx(10000.0)
            assert r["perimeter_m"] == pytest.approx(400.0)

    def test_min_room_area_filters_wall_cavities(self):
        eng = PSLGTopologyEngine(min_room_area=20000.0)
        rooms = eng.extract_room_polygons(grid_segments(7, 7))
        assert rooms == []  # 모든 칸이 10000 < 20000

    def test_snap_endpoints_returns_subdivided_segments(self):
        """하위 호환 시그니처 유지 + D1 해결 동작."""
        eng = PSLGTopologyEngine()
        out = eng.snap_endpoints(grid_segments(3, 3))
        assert len(out) == 24  # 4x3 + 4x3

    def test_exterior_boundary(self):
        eng = PSLGTopologyEngine(min_room_area=1.0)
        poly = eng.exterior_boundary(grid_segments(7, 7))
        assert poly, "외곽선을 찾지 못함"
        # grid_segments(7, 7) 은 (0,0)~(700,700) 범위
        assert abs(planar.polygon_signed_area(poly)) == pytest.approx(700.0 * 700.0, rel=1e-6)


# ---------------------------------------------------------------------------
# 4) C10: filter_structural_walls 내부 벽 삭제 회귀
# ---------------------------------------------------------------------------
class TestStructuralWallFilterRegression:
    def test_interior_walls_survive_after_subdivision(self):
        """C10 회귀: 분할 없이 필터를 돌리면 내부 벽이 전부 삭제된다."""
        lines = to_lines(grid_segments(7, 7))
        assert len(lines) == 16

        # 분할 없이 → 내부 벽 전부 소실 (결함 재현)
        broken = filter_structural_walls(lines, min_len_ratio=0.01, min_degree=1, join_tol=15)
        assert len(broken) == 4, "결함 재현 실패: 내부 벽이 이미 살아있음"

        # 분할 후 → 전부 생존
        subdivided = subdivide_at_intersections(lines, min_piece=1.0)
        fixed = filter_structural_walls(
            subdivided, min_len_ratio=0.01, min_degree=1, join_tol=15
        )
        assert len(fixed) == 112, f"기대 112, 실제 {len(fixed)}"

    def test_isolated_decorative_line_still_removed(self):
        """분할을 넣어도 본래 목적(고립 장식선 제거)은 유지되어야 한다."""
        segs = grid_segments(3, 3)
        segs.append(((2000.0, 2000.0), (2150.0, 2000.0)))  # 완전 고립선
        subdivided = subdivide_at_intersections(to_lines(segs), min_piece=1.0)
        kept = filter_structural_walls(subdivided, min_len_ratio=0.01, min_degree=1, join_tol=15)

        isolated = [l for l in kept if l.y1 == 2000 and l.x1 >= 2000]
        assert not isolated, "고립 장식선이 제거되지 않음"


# ---------------------------------------------------------------------------
# 5) 벡터 파이프라인 End-to-End
# ---------------------------------------------------------------------------
class TestVectorPipelineEndToEnd:
    def test_extract_vector_geometry_detects_all_grid_rooms(self, tmp_path):
        """업로드된 픽스처와 동일한 7x7 격자 PDF를 생성해 전체 경로를 검증한다."""
        fitz = pytest.importorskip("fitz")

        # 8개 격자선(100..800) x 8개 = 7x7 = 49실.
        # 선분 길이를 격자 범위와 정확히 일치시켜야 오버행이 생기지 않는다.
        pdf_path = tmp_path / "grid.pdf"
        doc = fitz.open()
        page = doc.new_page(width=1000, height=1000)
        for i in range(8):
            v = 100 + i * 100
            page.draw_line(fitz.Point(100, v), fitz.Point(800, v))
            page.draw_line(fitz.Point(v, 100), fitz.Point(v, 800))
        doc.save(str(pdf_path))
        doc.close()

        from parser.pdf_vector import extract_vector_geometry

        payload = extract_vector_geometry(str(pdf_path), 0)

        assert payload["walls_count"] == 112, f"walls={payload['walls_count']} (기대 112)"
        assert len(payload["rooms"]) == 49, f"rooms={len(payload['rooms'])} (기대 49)"
