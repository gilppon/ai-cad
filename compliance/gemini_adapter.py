import os
import json
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from compliance.rag.retriever import retrieve_relevant_laws
from compliance.rag.prompts import build_slm_prompt

class GeminiComplianceReport(BaseModel):
    summary: str = Field(description="건축기준법 적합성 검증 의견 요약")
    action_items: List[str] = Field(description="위반 사항 해결을 위한 조치 및 권장 설계안 목록")

class GeminiAdapter:
    """
    Adapter for Gemini API.
    Integrates Japanese Building Law RAG.
    """
    def __init__(self):
        # API key from environment variable
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None
        
    def generate_compliance_reasoning(self, slm_prompt_context: str, geometry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes the deterministic rule failures and raw geometry, retrieves RAG context, 
        and produces human-readable reasoning and action items using Gemini.
        """
        # 1. RAG Retrieval - 검색 쿼리 고도화 (도로 사선 제한, 피난 규정 추가)
        # We extract keywords from the prompt_context or geometry data dynamically.
        # But for MVP, we include the new keywords for testing Phase 2.
        query_text = "거실 채광 환기 면적 피난계단 도로 사선 제한 높이 복도 폭 피난 규정"
        
        # You could also dynamically add context if specific failures occurred.
        if "사선" in slm_prompt_context or "도로" in slm_prompt_context:
            query_text += " 도로사선제한 건축물 높이"
        
        retrieved_laws = retrieve_relevant_laws(query_text=query_text, n_results=5)
        
        # 2. Build Prompt
        prompt = build_slm_prompt(geometry_data=geometry_data, retrieved_laws=retrieved_laws)
        
        system_instruction = "You are a helpful JSON-only compliance assistant. Always respond with raw JSON. Focus on Japanese Building Standards Act (建築基準法)."
        full_prompt = f"{system_instruction}\n\n{prompt}"
        
        # 3. Call Gemini API
        try:
            if not self.client:
                raise ValueError("GEMINI_API_KEY not set. Running in offline/fallback mode.")
                
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=1000,
                    response_mime_type="application/json",
                    response_schema=GeminiComplianceReport,
                )
            )
            
            result = json.loads(response.text.strip())
            return result
        except Exception as e:
            print(f"Gemini Adapter Error: {e}")
            return {
                "[LLM MOCK RESPONSE]": True,
                "summary": "[LLM MOCK RESPONSE] Gemini 2.5 Flash 연결 또는 추론에 실패했습니다. GEMINI_API_KEY 환경 변수를 확인하세요.",
                "action_items": []
            }

# Singleton instance
llm_adapter = GeminiAdapter()

