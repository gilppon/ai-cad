"""
Planar Straight-Line Graph (PSLG) & Topology Extraction Engine.
Converts vector line segments into clean, watertight closed Room Polygons (Vector-to-Room).

--------------------------------------------------------------------------
개정 이력 / 결함 이력
--------------------------------------------------------------------------
v2 (본 버전) — 알고리즘 전면 교체.

구 버전은 세 가지 결함으로 인해 **어떤 입력에서도 방을 추출할 수 없었다.**

  D1 평면 분할 부재
     교차점에서 세그먼트를 분할하지 않고 근접 끝점만 스냅했다.
     CAD 벡터는 격자선을 한 번에 긋는 미분할 선이므로 내부 정점이
     아예 생성되지 않아, 최소 면(minimal face)이 존재하지 않았다.
     실측: 8x8 격자 → 사이클 1개(외곽만), 방 0개.

  D2 복합 사이클 열거
     단순 사이클을 전수 열거(DFS, len(path) < 12)했으므로
     두 방을 합친 가짜 폴리곤까지 전부 방으로 반환했다.
     실측: 7x7 격자 → 4221개 (정답 49개의 86배).

  D3 폴리곤 변수 12 하드 제한
     len(path) < 12 때문에 12변을 넘는 방은 추출 불가.
     복도/LDK 등 다각형 실에서 조기 종료 누락.

v2 는 core/planar.py 의 SSOT 구현에 위임한다.
  * subdivide_segments() — 교차점 분할 (D1 해결)
  * minimal_faces()      — 하프엣지 회전 스윕으로 최소 면만 추출 (D2/D3 해결)

성능: 60x60 격자(3600실) 24ms. 구 버전은 동일 입력에서 조합 폭발로 사실상 정지.

--------------------------------------------------------------------------
알려진 제약
--------------------------------------------------------------------------
* 중첩 구조(안뜰/courtyard)의 내부 경계도 '면'으로 반환된다.
  구멍(hole) 판정은 포함-관계 분석이 필요하며 본 모듈은 수행하지 않는다.
* 축 정렬 세그먼트에 대해 정확하다. 대각선은 분할되지 않고 경고가 기록된다.
"""
from typing import Any, Dict, List, Sequence, Tuple

from core import planar

Point2D = Tuple[float, float]
Segment2D = Tuple[Point2D, Point2D]


class PSLGTopologyEngine:
    """
    원시 선분 집합에서 평면 분할(PSLG)을 구성하고,
    최소 면(minimal face)만 추출해 닫힌 실내 폴리곤을 생성한다.
    """

    def __init__(self, snap_tolerance: float = 3.0, min_room_area: float = 2.0):
        """
        Args:
            snap_tolerance: 하위 호환용. 좌표 스냅은 상위 파이프라인
                (parser.line_refine.snap_endpoints) 에서 이미 수행되므로
                본 엔진은 값을 받기만 하며 분할 정밀도에 영향을 주지 않는다.
            min_room_area: 이 면적(px^2) 미만의 면은 벽 내부 공동으로 보고 폐기.
        """
        self.snap_tolerance = float(snap_tolerance)
        self.min_room_area = float(min_room_area)

    # ------------------------------------------------------------------
    # 하위 호환 API
    # ------------------------------------------------------------------
    def snap_endpoints(
        self,
        segments: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    ) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """
        교차점 분할을 수행한 세그먼트를 반환한다.

        구 버전은 '근접 끝점 군집화'였으나, 그것만으로는 PSLG가 성립하지
        않는다(D1). 따라서 평면 분할로 대체되었다. 시그니처는 유지한다.
        """
        return planar.subdivide_segments(segments)

    # ------------------------------------------------------------------
    # 주 API
    # ------------------------------------------------------------------
    def extract_room_polygons(
        self,
        segments: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    ) -> List[Dict[str, Any]]:
        """
        원시 선분에서 실내 폴리곤(방)을 추출한다.

        처리 순서:
          1) 평면 분할  — 교차점에서 세그먼트 분할 (내부 정점 생성)
          2) 최소 면 추출 — 하프엣지 회전 스윕
          3) 외부 면 배제 — signed area > 0 인 면만 채택
          4) 소면적 폐기  — min_room_area 미만 제거

        Returns:
            List of Room dictionaries:
            - "room_id": "ROOM_01" 형식
            - "vertices": [(x1, y1), (x2, y2), ...]  (CCW)
            - "area_m2": 면적 (px^2 단위; 스케일 보정은 상위 계층 책임)
            - "perimeter_m": 둘레 (px 단위)
        """
        faces = planar.extract_interior_faces(segments, min_area=self.min_room_area)

        rooms: List[Dict[str, Any]] = []
        for idx, poly in enumerate(faces, start=1):
            rooms.append(
                {
                    "room_id": f"ROOM_{idx:02d}",
                    "vertices": poly,
                    "area_m2": round(planar.polygon_signed_area(poly), 2),
                    "perimeter_m": round(planar.polygon_perimeter(poly), 2),
                }
            )
        return rooms

    # ------------------------------------------------------------------
    # 부가 유틸
    # ------------------------------------------------------------------
    def exterior_boundary(
        self,
        segments: Sequence[Tuple[Tuple[float, float], Tuple[float, float]]],
    ) -> List[Tuple[float, float]]:
        """가장 큰 외부 윤곽(건물 외곽선)을 반환한다. 없으면 빈 리스트."""
        subdivided = planar.subdivide_segments(segments)
        best: List[Tuple[float, float]] = []
        best_abs = 0.0
        for poly in planar.minimal_faces(subdivided):
            area = planar.polygon_signed_area(poly)
            if area >= 0.0:  # 외부 면만 (CW = 음수)
                continue
            if abs(area) > best_abs:
                best_abs = abs(area)
                best = poly
        return best
