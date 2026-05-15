from dataclasses import dataclass, field
from typing import Dict, Any, List, Union
from datetime import datetime, timezone

def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

@dataclass
class CorrectionPatch:
    id: str
    operation: str
    target_id: Union[str, int]
    before: Dict[str, Any]
    after: Dict[str, Any]
    timestamp: str = ""
    author: str = "operator"

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now_iso()

@dataclass
class CorrectionSession:
    session_id: str
    case_id: str
    patches: List[CorrectionPatch] = field(default_factory=list)
    created_at: str = ""
    status: str = "draft"

    def __post_init__(self):
        if not self.created_at:
            self.created_at = _now_iso()
