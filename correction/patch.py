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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "operation": self.operation,
            "target_id": self.target_id,
            "before": self.before,
            "after": self.after,
            "timestamp": self.timestamp,
            "author": self.author,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CorrectionPatch":
        return cls(
            id=str(d["id"]),
            operation=str(d["operation"]),
            target_id=d["target_id"],
            before=dict(d.get("before", {})),
            after=dict(d.get("after", {})),
            timestamp=str(d.get("timestamp", "")),
            author=str(d.get("author", "operator")),
        )


@dataclass
class CorrectionSession:
    session_id: str
    case_id: str
    patches: List[CorrectionPatch] = field(default_factory=list)
    created_at: str = ""
    status: str = "draft"  # "draft", "applied", "reverted"

    def __post_init__(self):
        if not self.created_at:
            self.created_at = _now_iso()

    @property
    def patch_count(self) -> int:
        return len(self.patches)

    @property
    def operation_summary(self) -> Dict[str, int]:
        """각 연산 타입별 패치 수 집계"""
        summary: Dict[str, int] = {}
        for p in self.patches:
            summary[p.operation] = summary.get(p.operation, 0) + 1
        return summary

    @property
    def is_human_corrected(self) -> bool:
        """수동 보정 패치가 1개 이상 있으면 True"""
        return any(p.author != "auto" for p in self.patches)

    @property
    def correction_source(self) -> str:
        """auto, human, mixed 중 하나 반환"""
        authors = {p.author for p in self.patches}
        if not authors:
            return "none"
        if authors == {"auto"}:
            return "auto"
        if "auto" not in authors:
            return "human"
        return "mixed"

    def apply(self) -> None:
        """세션을 적용 상태로 변경"""
        self.status = "applied"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "case_id": self.case_id,
            "patches": [p.to_dict() for p in self.patches],
            "created_at": self.created_at,
            "status": self.status,
            "patch_count": self.patch_count,
            "operation_summary": self.operation_summary,
            "correction_source": self.correction_source,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CorrectionSession":
        session = cls(
            session_id=str(d["session_id"]),
            case_id=str(d["case_id"]),
            patches=[CorrectionPatch.from_dict(p) for p in d.get("patches", [])],
            created_at=str(d.get("created_at", "")),
            status=str(d.get("status", "draft")),
        )
        return session

