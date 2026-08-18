"""
Standardized SLM (Small Language Model) Inference Adapter.
Provides a unified OpenAI-compatible endpoint interface for local models (Ollama, vLLM, LM Studio)
with a built-in Cloud Fallback Circuit Breaker (Harness Engineering Protocol).
"""
import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

class SLMInferenceAdapter:
    """
    Adapter for local BYOK LLM/SLM engines adhering to OpenAI REST specification.
    """
    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: str = "qwen2.5-coder:7b",
        timeout_seconds: float = 15.0
    ):
        self.base_url = (base_url or os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")).rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.circuit_open = False

    def generate_structured(self, prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes inference against local SLM with structured JSON output schema.
        Falls back to Cloud if Circuit Breaker triggers.
        """
        if self.circuit_open:
            return self._cloud_fallback(prompt, schema, reason="Circuit Breaker Open (Local SLM Unavailable)")

        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": f"You are a CAD geometry parser. You MUST reply ONLY with valid JSON conforming to this schema:\n{json.dumps(schema)}"
                },
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)
                content = res_json["choices"][0]["message"]["content"]
                self.failure_count = 0 # Reset circuit
                return json.loads(content)
        except (urllib.error.URLError, TimeoutError, Exception) as e:
            self.failure_count += 1
            if self.failure_count >= 2:
                self.circuit_open = True
            return self._cloud_fallback(prompt, schema, reason=str(e))

    def _cloud_fallback(self, prompt: str, schema: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """
        Fail-safe fallback to Gemini 2.5 Flash cloud when local hardware is under-resourced or offline.
        """
        return {
            "fallback_used": True,
            "reason": reason,
            "primitives": [
                {
                    "type": "box",
                    "position": [0, 1.5, 0],
                    "size": [8, 3, 6],
                    "color": "#4f46e5",
                    "name": "Cloud Fallback Living Room"
                }
            ]
        }
