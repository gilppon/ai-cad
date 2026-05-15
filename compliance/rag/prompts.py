from typing import Dict, Any, List
import json

def build_slm_prompt(geometry_data: Dict[str, Any], retrieved_laws: List[Dict[str, Any]]) -> str:
    """
    SLM에 주입할 프롬프트를 구성합니다.
    """
    # Create a simplified version of geometry_data to save context window
    simple_geo = []
    for room in geometry_data.get('rooms', []):
        simple_geo.append({
            "id": room.get("id"),
            "kind": room.get("kind"),
            "area_m2": room.get("area_m2"),
            "height_mm": room.get("height_mm"),
            "openings": room.get("openings", [])
        })

    prompt = "당신은 일본 건축기준법을 깊이 있게 이해하고 있는 건축 법규 전문가(Compliance Reviewer) 에이전트입니다.\n"
    prompt += "다음은 도면에서 추출된 요약 기하학적 데이터(방의 용도, 면적, 층고, 개구부 등)입니다:\n"
    prompt += f"{json.dumps(simple_geo, ensure_ascii=False)}\n\n"
    
    prompt += "다음은 RAG 검색을 통해 추출된 도면 관련 일본 건축기준법 조항 내용입니다:\n"
    if not retrieved_laws:
        prompt += "검색된 관련 법규가 없습니다.\n"
    else:
        for law in retrieved_laws:
            prompt += f"- [{law['title']}] {law['content']}\n"
            
    prompt += "\n위의 도면 데이터와 법규를 바탕으로, 도면에 위법 사항이나 피난/채광/환기 관점에서의 잠재적 위험성 및 개선 필요성이 있는지 종합적으로 평가해주세요.\n"
    prompt += "특히 거실(LDK, BEDROOM)의 채광/환기 확보 여부 및 피난 동선(개구부, 문)의 적절성을 중점적으로 검토하세요.\n"
    prompt += "응답은 반드시 아래의 JSON 형식으로만 출력해야 합니다. 추가적인 마크다운이나 설명은 붙이지 마세요.\n"
    prompt += '{"summary": "종합 평가 코멘트...", "action_items": ["개선사항1", "개선사항2"]}'
    
    return prompt
