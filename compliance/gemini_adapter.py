import os
import json
from typing import Dict, Any
import google.generativeai as genai
from compliance.rag.retriever import retrieve_relevant_laws
from compliance.rag.prompts import build_slm_prompt

class GeminiAdapter:
    """
    Adapter for Gemini 1.5 Pro API.
    Integrates Japanese Building Law RAG.
    """
    def __init__(self):
        # API key from environment variable
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if api_key:
            genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        
    def generate_compliance_reasoning(self, slm_prompt_context: str, geometry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes the deterministic rule failures and raw geometry, retrieves RAG context, 
        and produces human-readable reasoning and action items using Gemini 1.5 Pro.
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
            response = self.model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=1000,
                )
            )
            
            content = response.text
            # Clean up potential markdown formatting around JSON
            if content.startswith("```json"):
                content = content.replace("```json", "", 1)
            elif content.startswith("```"):
                content = content.replace("```", "", 1)
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
                
            result = json.loads(content.strip())
            return result
        except Exception as e:
            print(f"Gemini Adapter Error: {e}")
            return {
                "[LLM MOCK RESPONSE]": True,
                "summary": "[LLM MOCK RESPONSE] Gemini 1.5 Pro 연결 또는 추론에 실패했습니다. GEMINI_API_KEY 환경 변수를 확인하세요.",
                "action_items": []
            }

# Singleton instance
llm_adapter = GeminiAdapter()
