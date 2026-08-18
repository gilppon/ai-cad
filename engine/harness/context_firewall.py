"""
Context Firewall & Prompt Injection Defense for CAD OCR & User Inputs.
Sanitizes raw OCR strings extracted from blueprints to prevent indirect prompt injection
from poisoning the Building Code LLM / Dual-Track RAG pipeline.
"""
import re
from typing import Dict, Any, List, Tuple

class ContextFirewall:
    """
    Harness Context Firewall: Token Sanitizer and Injection Guard.
    """
    # Malicious injection patterns commonly embedded in text/adversarial blueprints
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
        re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
        re.compile(r"(you\s+are\s+now\s+)?(in\s+)?dan\s+mode", re.IGNORECASE),
        re.compile(r"dan\s+mode", re.IGNORECASE),
        re.compile(r"bypass\s+(all\s+)?safety\s+guidelines?", re.IGNORECASE),
        re.compile(r"output\s+only\s+(true|pass|compliant)", re.IGNORECASE),
        re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"\{\{.*?\}\}|<\|.*?\|>", re.DOTALL),  # Template injection / Special tokens
        re.compile(r"exec\s*\(|eval\s*\(|__import__", re.IGNORECASE),
    ]

    # Whitelist regex for valid CAD textual entities (dimensions, room labels, notes)
    SAFE_CAD_CHARACTERS = re.compile(r"[^a-zA-Z0-9가-힣ぁ-んァ-ヶ一-龥\s\.,:\-_/\(\)㎡m²m³mmcm°%]")

    @classmethod
    def sanitize_ocr_text(cls, raw_text: str) -> Tuple[str, List[str]]:
        """
        Sanitizes raw text from CAD OCR:
        1. Detects and strips adversarial injection triggers.
        2. Strips unsafe binary/control characters.
        3. Returns (sanitized_text, list_of_detected_threats).
        """
        detected_threats = []
        clean_text = raw_text

        # 1. Detect Injection Patterns
        for pattern in cls.INJECTION_PATTERNS:
            matches = pattern.findall(clean_text)
            if matches:
                detected_threats.append(f"Blocked Pattern: {pattern.pattern}")
                clean_text = pattern.sub("[REDACTED_BY_FIREWALL]", clean_text)

        # 2. Strip non-whitelisted characters / control codes
        clean_text = cls.SAFE_CAD_CHARACTERS.sub("", clean_text)
        
        # 3. Collapse multiple whitespaces
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        return clean_text, detected_threats

    @classmethod
    def filter_prompt_payload(cls, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep-sanitizes all string fields within a prompt payload dictionary before sending to LLM.
        """
        sanitized_dict = {}
        all_threats = []

        for k, v in user_context.items():
            if isinstance(v, str):
                s_val, threats = cls.sanitize_ocr_text(v)
                sanitized_dict[k] = s_val
                all_threats.extend(threats)
            elif isinstance(v, list):
                s_list = []
                for item in v:
                    if isinstance(item, str):
                        s_item, threats = cls.sanitize_ocr_text(item)
                        s_list.append(s_item)
                        all_threats.extend(threats)
                    else:
                        s_list.append(item)
                sanitized_dict[k] = s_list
            else:
                sanitized_dict[k] = v

        sanitized_dict["_firewall_status"] = {
            "threats_detected": len(all_threats),
            "threat_log": all_threats
        }
        return sanitized_dict
