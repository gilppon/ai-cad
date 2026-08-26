import pytest
from pathlib import Path
from compliance.rag.parser import LawXMLParser
from compliance.rag.retriever import retrieve_relevant_laws, DB_PATH
from compliance.rag.prompts import build_slm_prompt

# SP2/A-3: 구 저장소(e:/project/cad_saas_mvp) 경로 제거 - 저장소 내부 data/laws 사용
from pipeline.paths import PROJECT_ROOT
LAWS_DIR = PROJECT_ROOT / "data" / "laws"

def test_xml_parsing_uniqueness():
    """
    e-Gov 법률 XML 파일을 파싱했을 때, 생성된 모든 청크의 ID가 고유한지 검증합니다.
    """
    xml_files = list(LAWS_DIR.glob("*.xml"))
    assert len(xml_files) > 0, "테스트용 법률 XML 파일이 존재해야 합니다."
    
    for xml_path in xml_files:
        parser = LawXMLParser(xml_path)
        chunks = parser.parse_articles()
        
        chunk_ids = [chunk["id"] for chunk in chunks]
        unique_ids = set(chunk_ids)
        
        # 중복이 없는지 검증 (중복 회피 로직 동작 확인)
        assert len(chunk_ids) == len(unique_ids), f"{xml_path.name} 파싱 결과 중복된 ID가 존재합니다!"

def test_retrieval_and_metadata_mapping():
    """
    ChromaDB에서 법규를 성공적으로 검색하고, 반환된 메타데이터 'title'이
    올바른 포맷('[법률명] 조항명')으로 매핑되는지 검증합니다.
    """
    # 일본 건축기준법에서 자주 나오는 핵심 키워드로 검색 테스트
    query = "居室 採光"  # 거실 채광
    results = retrieve_relevant_laws(query, n_results=3)
    
    assert len(results) > 0, "검색 결과가 최소 1개 이상 존재해야 합니다."
    
    for law in results:
        assert "id" in law
        assert "title" in law
        assert "content" in law
        
        # title 필드가 비어있지 않은지 검증
        assert law["title"] != "", "title 메타데이터 필드가 비어있습니다!"
        
        # 포맷 검증 ([법률명] 형태로 시작하는지 확인)
        assert law["title"].startswith("["), f"title 필드가 올바른 포맷([법률명])이 아닙니다: {law['title']}"
        assert "]" in law["title"], f"title 필드에 닫는 대괄호(']')가 없습니다: {law['title']}"

def test_slm_prompt_building():
    """
    RAG 검색 결과와 기하학 데이터를 활용하여 SLM 프롬프트가 정상적으로 조립되는지 검증합니다.
    """
    mock_geometry = {
        "rooms": [
            {
                "id": "room_1",
                "kind": "LDK",
                "area_m2": 24.5,
                "height_mm": 2400,
                "openings": [{"kind": "WINDOW", "width_mm": 1800}]
            }
        ]
    }
    
    mock_retrieved = [
        {
            "id": "325AC0000000201_art_28",
            "title": "[建築基準法] 第二十八条",
            "content": "居室には、採光のための窓その他の開口部를 마련해야 한다."
        }
    ]
    
    prompt = build_slm_prompt(mock_geometry, mock_retrieved)
    
    # 필수 컨텐츠가 프롬프트 내에 포함되어 있는지 확인
    assert "LDK" in prompt
    assert "24.5" in prompt
    assert "[建築基準法] 第二十八条" in prompt
    assert "居室" in prompt
    assert "採光" in prompt
    assert "summary" in prompt
    assert "action_items" in prompt
