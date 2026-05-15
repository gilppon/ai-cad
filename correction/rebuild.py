from typing import Dict, Any
from correction.patch import CorrectionSession

def rebuild_after_correction(payload: Dict[str, Any], session: CorrectionSession) -> Dict[str, Any]:
    """
    Apply correction session patches and rebuild downstream data (e.g. graph).
    Currently basic, assumes operations mutated payload inline.
    Future: full graph re-computation based on updated walls/rooms.
    """
    payload["refined"] = True
    payload["correction_applied"] = True
    payload["last_correction_session"] = session.session_id
    
    # In a full flow, we would trigger parser/rooms_pipeline.py STEP 5 (graph) here
    return payload
