import os
import json
from typing import Dict, Any
from openai import OpenAI
from compliance.rag.retriever import retrieve_relevant_laws
from compliance.rag.prompts import build_slm_prompt

import logging

logger = logging.getLogger(__name__)

class LMStudioSLMAdapter:
    """
    Adapter for a local SLM running on LM Studio via OpenAI-compatible API.
    Integrates Japanese Building Law RAG.
    """
    def __init__(self, base_url: str = "http://localhost:1234/v1", api_key: str = "lm-studio"):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        
    def generate_compliance_reasoning(self, slm_prompt_context: str, geometry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes the deterministic rule failures and raw geometry, retrieves RAG context, 
        and produces human-readable reasoning and action items.
        """
        
        # 1. RAG Retrieval
        # We query the ChromaDB using keywords from the geometry or deterministic failures
        query_text = "거실 채광 환기 면적 피난계단"
        retrieved_laws = retrieve_relevant_laws(query_text=query_text, n_results=3)
        
        # 2. Build SLM Prompt
        prompt = build_slm_prompt(geometry_data=geometry_data, retrieved_laws=retrieved_laws)
        
        # 3. Call LM Studio API
        try:
            response = self.client.chat.completions.create(
                model="local-model", # LM studio ignores this
                messages=[
                    {"role": "system", "content": "You are a helpful JSON-only compliance assistant. Always respond with raw JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )
            
            content = response.choices[0].message.content
            # Clean up potential markdown formatting around JSON
            if content.startswith("```json"):
                content = content.replace("```json", "", 1)
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
                
            result = json.loads(content.strip())
            return result
        except Exception as e:
            logger.error(f"SLM Adapter Error: {e}")
            return {
                "[SLM MOCK RESPONSE]": True,
                "summary": "[SLM MOCK RESPONSE] SLM(로컬 LLM) 연결 또는 추론에 실패했습니다. LM Studio가 포트 1234에서 실행 중인지 확인하세요.",
                "action_items": []
            }

# Singleton instance for the MVP
slm_adapter = LMStudioSLMAdapter()
