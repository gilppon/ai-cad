# -*- coding: utf-8 -*-
import os
import sys
import pytest
import json
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from test_japan_market_e2e import GLOBAL_MOCK_DB, get_mock_user_and_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_phase13_mocks():
    # FastAPI 의존성 오버라이드
    from app.api.deps import get_current_user_and_db
    app.dependency_overrides[get_current_user_and_db] = get_mock_user_and_db
    
    # 임시 프로젝트 디렉토리 준비
    from pipeline.paths import OUTPUT_ROOT
    project_dir = OUTPUT_ROOT / "projects" / "proj_999"
    os.makedirs(project_dir, exist_ok=True)
    
    # 기본 incident.json 준비 (초기 버전: 1)
    incident_path = project_dir / "incident.json"
    initial_incident = {
        "case_id": "case_abc123",
        "customer_name": "타나카 타로",
        "address": "도쿄도 시부야구",
        "incident_date": "2026-05-20",
        "description": "욕실 주변 미세 누수 의심",
        "version": 1,
        "created_at": "2026-05-20T00:00:00Z",
        "updated_at": "2026-05-20T00:00:00Z",
        "leak_sources": [],
        "damage_zones": [],
        "suspected_paths": [],
        "annotations": []
    }
    with open(incident_path, "w", encoding="utf-8") as f:
        json.dump(initial_incident, f, ensure_ascii=False, indent=2)

    # 기본 page0_rooms.json 준비 (이게 있어야 재빌드가 가능함)
    geom_path = project_dir / "page0_rooms.json"
    initial_geom = {
        "kind": "geometry_payload",
        "schema_version": "0.1.0",
        "page": 0,
        "page_index": 0,
        "canvas": {"width": 200, "height": 100},
        "rooms": [
            {
                "id": 0, "kind": "unknown", "area_m2": 25.0,
                "polygon": [
                    {"x": 0, "y": 0}, {"x": 100, "y": 0},
                    {"x": 100, "y": 100}, {"x": 0, "y": 100},
                ],
                "openings": [
                    {"id": 0, "p1": {"x": 40, "y": 0}, "p2": {"x": 60, "y": 0}, "kind": "door"},
                ],
                "metadata": {},
            },
            {
                "id": 1, "kind": "bedroom", "area_m2": 12.0,
                "polygon": [
                    {"x": 100, "y": 0}, {"x": 200, "y": 0},
                    {"x": 200, "y": 100}, {"x": 100, "y": 100},
                ],
                "openings": [],
                "metadata": {},
            },
        ],
        "rooms_count": 2,
        "walls": [
            {"id": 0, "p1": {"x": 0, "y": 0}, "p2": {"x": 100, "y": 0}},
            {"id": 1, "p1": {"x": 100, "y": 0}, "p2": {"x": 100, "y": 100}},
            {"id": 2, "p1": {"x": 100, "y": 100}, "p2": {"x": 0, "y": 100}},
        ],
        "walls_count": 3,
        "debug_files": {},
        "processing": {"stage": "test", "warnings": []},
        "incident": {},
    }
    with open(geom_path, "w", encoding="utf-8") as f:
        json.dump(initial_geom, f, ensure_ascii=False, indent=2)
        
    yield
    
    # 정리
    app.dependency_overrides.clear()
    if incident_path.exists():
        os.remove(incident_path)
    if geom_path.exists():
        os.remove(geom_path)


# ================================================================
# 1. 오프라인 델타 벌크 동기화정상 작동 테스트 (Version Bump 검증)
# ================================================================
def test_offline_delta_bulk_sync_success():
    """오프라인 중 수집한 델타 액션들을 순차적으로 서버에 전송했을 때 락이 통과되고 버전이 정상 증가하는지 검증"""
    payload = {
        "base_version": 1,
        "operations": [
            {
                "operation": "change_room_type",
                "params": {"room_id": 0, "new_kind": "ldk"},
                "author": "operator_offline"
            },
            {
                "operation": "place_leak_source",
                "params": {
                    "point": {"x": 55.0, "y": 45.0},
                    "room_id": 0,
                    "description": "오프라인 누수 의심 구역"
                },
                "author": "operator_offline"
            }
        ]
    }
    
    res = client.post("/api/v1/projects/proj_999/sync", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["patches_applied"] == 2
    assert data["current_version"] == 2  # 1 -> 2로 bump

    # 3D IFC 및 JSON 갱신 결과 실사 확인
    from pipeline.paths import OUTPUT_ROOT
    incident_path = OUTPUT_ROOT / "projects" / "proj_999" / "incident.json"
    with open(incident_path, "r", encoding="utf-8") as f:
        incident = json.load(f)
    
    assert incident["version"] == 2
    assert len(incident["leak_sources"]) == 1
    assert incident["leak_sources"][0]["description"] == "오프라인 누수 의심 구역"
    
    geom_path = OUTPUT_ROOT / "projects" / "proj_999" / "page0_rooms.json"
    with open(geom_path, "r", encoding="utf-8") as f:
        geom = json.load(f)
    
    assert geom["rooms"][0]["kind"] == "ldk"


# ================================================================
# 2. 낙관적 락(Optimistic Locking) 버전 불일치에 따른 충돌 회피 검증 (409 Conflict)
# ================================================================
def test_offline_delta_sync_optimistic_locking_conflict():
    """서버의 현재 버전과 클라이언트가 주장하는 base_version이 불일치할 때 정확히 409 Conflict를 내는지 검증"""
    # 서버 버전은 1인데, 클라이언트가 base_version을 2로 보내거나 0으로 보낼 때
    payload_mismatch = {
        "base_version": 2,  # 버전 불일치 발생!
        "operations": [
            {
                "operation": "change_room_type",
                "params": {"room_id": 0, "new_kind": "bathroom"},
                "author": "operator_offline"
            }
        ]
    }
    
    res = client.post("/api/v1/projects/proj_999/sync", json=payload_mismatch)
    assert res.status_code == 409
    data = res.json()
    assert "Conflict" in data["detail"]
    assert "Server version: 1" in data["detail"]
    assert "Client base version: 2" in data["detail"]

    # 서버의 파일 데이터에 변경이 가해지지 않았는지 확인
    from pipeline.paths import OUTPUT_ROOT
    incident_path = OUTPUT_ROOT / "projects" / "proj_999" / "incident.json"
    with open(incident_path, "r", encoding="utf-8") as f:
        incident = json.load(f)
        
    assert incident["version"] == 1  # 락 충돌로 인해 버전이 바뀌지 않음
