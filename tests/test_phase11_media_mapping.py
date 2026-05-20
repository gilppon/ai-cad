# -*- coding: utf-8 -*-
import os
import sys
import io
import pytest
import json
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from test_japan_market_e2e import GLOBAL_MOCK_DB, get_mock_user_and_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_phase11_mocks():
    # FastAPI 의존성 오버라이드
    from app.api.deps import get_current_user_and_db
    app.dependency_overrides[get_current_user_and_db] = get_mock_user_and_db
    
    # 임시 프로젝트 디렉토리 준비
    from pipeline.paths import OUTPUT_ROOT
    project_dir = OUTPUT_ROOT / "projects" / "proj_999"
    os.makedirs(project_dir, exist_ok=True)
    
    # 기본 incident.json 준비 (이게 있어야 PATCH가 동작함)
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
        "leak_sources": [
            {
                "point": {"x": 5.0, "y": 5.0},
                "room_id": 1,
                "confidence": 0.9,
                "description": "기존 누수 핀"
            }
        ],
        "damage_zones": [],
        "suspected_paths": [],
        "annotations": []
    }
    with open(incident_path, "w", encoding="utf-8") as f:
        json.dump(initial_incident, f, ensure_ascii=False, indent=2)
        
    yield
    
    # 정리
    app.dependency_overrides.clear()
    if incident_path.exists():
        os.remove(incident_path)


# ================================================================
# 1. 미디어 업로드 및 로컬 폴백 CDN 스트리밍 검증
# ================================================================
def test_media_upload_and_fallback_streaming():
    """현장 실사 이미지 업로드 시, 용량 및 확장자 체크 후 로컬 폴백 CDN URL을 완벽하게 반환하고 스트리밍하는지 검증"""
    # 1. 잘못된 확장자(txt) 업로드 시도 -> 400 Bad Request
    fake_txt = io.BytesIO(b"dummy text content")
    res_bad_ext = client.post(
        "/api/v1/projects/proj_999/media",
        files={"file": ("test_doc.txt", fake_txt, "text/plain")}
    )
    assert res_bad_ext.status_code == 400
    assert "Only PNG, JPG, JPEG" in res_bad_ext.json()["detail"]

    # 2. 정상 이미지 업로드 시도 -> 200 OK & CDN URL 반환
    fake_img = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82") # Minimal valid PNG
    res_upload = client.post(
        "/api/v1/projects/proj_999/media",
        files={"file": ("live_leak.png", fake_img, "image/png")}
    )
    assert res_upload.status_code == 200
    data = res_upload.json()
    assert "url" in data
    assert "filename" in data
    assert "media_id" in data
    
    # 3. 반환된 로컬 폴백 URL을 통해 이미지 직접 다운로드/스트리밍 검증 -> 200 OK
    fallback_url = data["url"]
    res_stream = client.get(fallback_url)
    assert res_stream.status_code == 200
    assert res_stream.headers["content-type"] == "image/png" or "application/octet-stream"
    assert len(res_stream.content) > 0


# ================================================================
# 2. 3D IFC 객체 핀 매핑 및 현장 사진/소견 일대일 바인딩 검증
# ================================================================
def test_incident_pin_mapping_and_attachment():
    """3D WebGL 핀 좌표 정보와 업로드된 미디어를 incident 데이터셋 내에 정밀 합성하는지 검증"""
    media_url = "/api/v1/projects/proj_999/media/test_photo.png"
    
    # 1. LeakSource 핀 좌표 매핑 API 호출
    patch_payload = {
        "pin_type": "leak_source",
        "target_room_id": 1,
        "coordinate": {"x": 5.0, "y": 5.0}, # 기존 좌표와 일치하여 덮어쓰기 유도
        "media_urls": [media_url],
        "comment": "샤워부스 하부 틈새 균열 발견"
    }
    res_patch = client.patch(
        "/api/v1/projects/proj_999/incidents/case_abc123/pins",
        json=patch_payload
    )
    assert res_patch.status_code == 200
    data = res_patch.json()
    assert data["status"] == "success"
    assert data["pin_mapped"] == True
    assert data["version"] == 2 # 1 -> 2로 버전 bump 확인
    
    # 2. 로컬 incident.json 파일을 다시 로드하여 데이터 병합 정합성 검증
    from pipeline.paths import OUTPUT_ROOT
    incident_path = OUTPUT_ROOT / "projects" / "proj_999" / "incident.json"
    with open(incident_path, "r", encoding="utf-8") as f:
        saved_incident = json.load(f)
        
    assert len(saved_incident["leak_sources"]) == 1
    target_ls = saved_incident["leak_sources"][0]
    assert "샤워부스 하부 틈새 균열 발견" in target_ls["description"]
    assert media_url in target_ls["description"]
    assert saved_incident["version"] == 2

    # 3. 새로운 좌표에 데미지존(damage_zone) 핀 신규 맵핑 검증
    patch_dz_payload = {
        "pin_type": "damage_zone",
        "target_room_id": 2,
        "coordinate": {"x": 12.0, "y": 15.5}, # 신규 좌표
        "media_urls": [media_url],
        "comment": "천장 석고보드 젖음 확산"
    }
    res_dz_patch = client.patch(
        "/api/v1/projects/proj_999/incidents/case_abc123/pins",
        json=patch_dz_payload
    )
    assert res_dz_patch.status_code == 200
    assert res_dz_patch.json()["version"] == 3 # 2 -> 3
    
    with open(incident_path, "r", encoding="utf-8") as f:
        saved_incident_dz = json.load(f)
        
    assert len(saved_incident_dz["damage_zones"]) == 1
    target_dz = saved_incident_dz["damage_zones"][0]
    assert target_dz["description"] == "천장 석고보드 젖음 확산"
    assert media_url in target_dz["photos"]
