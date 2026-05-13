from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "out"


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    if PROJECT_ROOT not in candidate.parents and candidate != PROJECT_ROOT:
        raise ValueError(f"Path escapes project root: {candidate}")
    return candidate


def resolve_output_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    if OUTPUT_ROOT not in candidate.parents and candidate != OUTPUT_ROOT:
        raise ValueError(f"Output path escapes output root: {candidate}")
    return candidate
