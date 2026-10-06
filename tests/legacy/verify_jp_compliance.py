# -*- coding: utf-8 -*-
import os
import sys
import io

# 윈도우 터미널 UTF-8 출력 강제 (UnicodeEncodeError 방지)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import shutil
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import get_current_user_and_db
from compliance.jp_compliance import JPResponsibilityEngine
from domain.models import RoomKind

# 1. Mock Supabase Database
mock_db = MagicMock()
mock_table = MagicMock()
mock_db.table.return_value = mock_table
mock_table.select.return_value.eq.return_value.execute.return_value.data = [{"id": "mock_project_123"}]
mock_table.update.return_value.eq.return_value.execute.return_value.data = [{"id": "mock_project_123"}]

app.dependency_overrides[get_current_user_and_db] = lambda: {
    "user_id": "mock-user-123",
    "db": mock_db
}

client = TestClient(app)

def test_engine_directly():
    print("=== 1. Testing JPResponsibilityEngine Directly ===")
    
    # 시나리오 1: 샤프트(PS/DS) 내 누수 발생 -> 공용부 판정 기대
    leak_point = {"x": 150.0, "y": 200.0}
    room_meta = {"id": 101, "kind": "SHAFT", "location_tag": "PS"}
    opinion1 = JPResponsibilityEngine.evaluate_leak(leak_point, room_meta)
    
    assert opinion1["ownership_decision"] == "COMMON"
    assert opinion1["room_abbr_jp"] == "PS/DS"
    print("[*] Scenario 1 (PS/DS - COMMON): PASS")
    
    # 시나리오 2: 전유 욕실 내 누수 발생 -> 전유부 판정 기대
    room_meta = {"id": 102, "kind": "BATHROOM"}
    opinion2 = JPResponsibilityEngine.evaluate_leak(leak_point, room_meta)
    
    assert opinion2["ownership_decision"] == "PROPRIETARY"
    assert opinion2["room_abbr_jp"] == "UB"
    print("[*] Scenario 2 (Bathroom - PROPRIETARY): PASS")

    # 시나리오 3: 발코니 누수 발생 -> 공용부(전용사용) 판정 기대
    room_meta = {"id": 103, "kind": "BALCONY"}
    opinion3 = JPResponsibilityEngine.evaluate_leak(leak_point, room_meta)
    
    assert opinion3["ownership_decision"] == "COMMON_EXCLUSIVE_USE"
    print("[*] Scenario 3 (Balcony - COMMON_EXCLUSIVE_USE): PASS")


def test_api_integration():
    print("\n=== 2. Testing FastAPI Correction API Integration ===")
    
    project_id = "mock_project_123"
    
    # 임시 mock 도면 데이터 폴더 및 파일 구성
    mock_dir = f"out/projects/{project_id}"
    os.makedirs(mock_dir, exist_ok=True)
    
    mock_geom_data = {
        "rooms": [
            {"id": 1, "kind": "toilet", "polygon": [{"x": 0, "y": 0}, {"x": 100, "y": 100}]},
            {"id": 2, "kind": "shaft", "polygon": [{"x": 100, "y": 0}, {"x": 200, "y": 100}], "location_tag": "PS"}
        ],
        "walls": [
            {"id": 0, "p1": {"x": 0, "y": 0}, "p2": {"x": 100, "y": 0}},
            {"id": 1, "p1": {"x": 100, "y": 0}, "p2": {"x": 100, "y": 100}}
        ],
        "incident": {
            "leak_sources": [],
            "damage_zones": []
        }
    }
    
    geom_path = f"{mock_dir}/page0_rooms.json"
    with open(geom_path, "w", encoding="utf-8") as f:
        json.dump(mock_geom_data, f, ensure_ascii=False, indent=2)

    # 델타 패치 요청 페이로드 구성 (누수 소스 배치 연산 포함)
    request_payload = {
        "case_id": "LEAK-TEST-001",
        "operations": [
            {
                "operation": "place_leak_source",
                "params": {
                    "point": {"x": 150.0, "y": 50.0},
                    "room_id": 2,
                    "description": "공용 종관 이음새 균열 누수 의심"
                },
                "author": "tester-01"
            }
        ]
    }

    # /projects/{project_id}/correction API 호출
    # rebuild_after_correction는 기하 재빌드이므로 테스트용 mock 처리
    with patch("correction.rebuild.rebuild_after_correction") as mock_rebuild:
        # rebuild는 전달받은 payload를 그대로 돌려주는 것으로 mock
        mock_rebuild.side_effect = lambda p, s, output_dir: p
        
        response = client.post(f"/api/v1/projects/{project_id}/correction", json=request_payload)
        
        assert response.status_code == 200, f"API failed: {response.text}"
        data = response.json()
        
        assert data["status"] == "success"
        assert len(data["compliance_opinions"]) == 1
        
        opinion = data["compliance_opinions"][0]
        assert opinion["room_id"] == 2
        assert opinion["ownership_decision"] == "COMMON"
        assert opinion["room_abbr_jp"] == "PS/DS"
        
        print("[*] API Response structure: OK")
        print(f"[+] Decision: {opinion['decision_label']}")
        print(f"[+] Opinion: {opinion['japanese_opinion']}")

    # 임시 폴더 청소
    if os.path.exists("out"):
        shutil.rmtree("out")
        
    print("\n[+] JP Compliance & Correction API E2E integrated successfully!")

if __name__ == "__main__":
    test_engine_directly()
    test_api_integration()
