"""
Stage 3 Verification Test Suite.
Tests:
1. Hierarchical e-Gov XML Chunking & Dense/BM25 Hybrid RAG Search
2. Gemini Adapter JsonSchema Constraints & Legal Report Parsing Stability
"""
import sys
import os
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

from engine.compliance.rag.hierarchical_xml_rag import HierarchicalLegalRAGEngine
from engine.inference.gemini_adapter import GeminiAdapter

def test_stage3_hybrid_rag_engine():
    print("[STAGE 3 TEST 1] Testing Hierarchical XML Chunking & Hybrid RAG...")
    engine = HierarchicalLegalRAGEngine()

    # Query 1: 채광 (Daylight)
    results_daylight = engine.hybrid_search("居室の採光 7分の1", top_k=2)
    assert len(results_daylight) >= 1
    top_node = results_daylight[0]["node"]
    print(f"  -> Top Hit (Daylight): {top_node['article']} {top_node['paragraph']} (Score: {results_daylight[0]['score']})")
    assert "第28条" in top_node["article"]

    # Query 2: 피난 보행거리 (Evacuation distance)
    results_evac = engine.hybrid_search("直通階段 歩行距離 50m", top_k=2)
    assert len(results_evac) >= 1
    top_evac = results_evac[0]["node"]
    print(f"  -> Top Hit (Evac): {top_evac['article']} (Score: {results_evac[0]['score']})")
    assert "第120条" in top_evac["article"]

    print("  [PASS] Hierarchical Hybrid RAG OK!")

def test_stage3_gemini_adapter_jsonschema():
    print("[STAGE 3 TEST 2] Testing Gemini Adapter JsonSchema Constraints...")
    adapter = GeminiAdapter()
    schema = adapter.get_json_schema()
    assert "properties" in schema and "verdict" in schema["properties"]
    print("  -> JsonSchema Structure: OK")

    # Mock valid structured AI response
    valid_ai_response = json.dumps({
        "verdict": "VIOLATION_DETECTED",
        "reviewed_room_id": "ROOM_01",
        "evaluated_articles": ["第28条 第1項", "施行令 第120条"],
        "citations": [
            {
                "article_num": "第28条 第1項",
                "status": "FAIL",
                "snippet": "採光有効面積は床面積の7分の1以上",
                "calculated_value": 1.2,
                "required_threshold": 3.0
            }
        ],
        "remedy_notes": "창호 개구부 면적 1.8m² 추가 필요"
    })

    parsed = adapter.parse_and_validate_response(valid_ai_response)
    assert parsed["verdict"] == "VIOLATION_DETECTED"
    assert len(parsed["citations"]) == 1
    print(f"  -> Parsed Legal Report: {parsed['verdict']} for {parsed['reviewed_room_id']}")
    print("  [PASS] Gemini Adapter JsonSchema Parsing OK!")

if __name__ == "__main__":
    print("=" * 70)
    print("🎖️ [KODARI DEV LEGION] STAGE 3 VALIDATION GATE")
    print("=" * 70)
    test_stage3_hybrid_rag_engine()
    test_stage3_gemini_adapter_jsonschema()
    print("=" * 70)
    print("✅ [STAGE 3 COMPLETE] 3단계 RAG 및 어댑터 레이어 고도화 100% 무결점 완료!")
    print("=" * 70)
