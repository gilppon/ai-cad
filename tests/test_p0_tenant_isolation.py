"""
P0-3: 타 테넌트 접근 차단 회귀 테스트 (C1 대응).

배경
----
`app/api/v1/endpoints.py` 의 프로젝트 접근은 과거 `.eq("id", project_id)` 단독
필터였고, 코드베이스 전체에 사용자 스코프 필터(`eq("user_id", ...)`)가 0건이었다.
그 결과 인증된 사용자라면 누구나 타인의 project_id 로 도면·IFC·인시던트를
열람·수정할 수 있었다 (IDOR).

이 테스트는 그 결함이 재발하지 않음을 보장하는 **출항 게이트**다.
이 파일의 테스트가 하나라도 실패하면 상용 배포를 진행하지 않는다.

실행
----
    pytest tests/test_p0_tenant_isolation.py -v
"""
import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app


# ---------------------------------------------------------------------------
# 가짜 Supabase (PostgREST 쿼리 빌더 최소 에뮬레이션)
# ---------------------------------------------------------------------------
class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    """`.table(t).select(c).eq(k, v)...execute()` 체인을 흉내낸다."""

    def __init__(self, store, table):
        self.store = store
        self.table = table
        self.filters = {}
        self._mode = None

    def select(self, *_args, **_kwargs):
        self._mode = "select"
        return self

    def insert(self, row):
        self._mode = "insert"
        self._row = row
        return self

    def update(self, row):
        self._mode = "update"
        self._row = row
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        rows = self.store.get(self.table, [])

        if self._mode == "select":
            matched = [
                r for r in rows
                if all(str(r.get(k)) == str(v) for k, v in self.filters.items())
            ]
            return FakeResult(matched)

        if self._mode == "update":
            matched = [
                r for r in rows
                if all(str(r.get(k)) == str(v) for k, v in self.filters.items())
            ]
            for r in matched:
                r.update(self._row)
            return FakeResult(matched)

        if self._mode == "insert":
            new_row = dict(self._row)
            new_row.setdefault("id", f"proj_{len(rows) + 1}")
            rows.append(new_row)
            return FakeResult([new_row])

        return FakeResult([])


class FakeSupabase:
    def __init__(self, tables=None):
        self.tables = tables or {}

    def table(self, name):
        self.tables.setdefault(name, [])
        return FakeQuery(self.tables, name)


class ExplodingSupabase(FakeSupabase):
    """DB 장애를 흉내낸다 — 과거에는 이 경우 인증 검사가 우회되었다."""

    def table(self, name):
        raise RuntimeError("simulated database outage")


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------
OWNER_ID = "11111111-1111-1111-1111-111111111111"
ATTACKER_ID = "22222222-2222-2222-2222-222222222222"
PROJECT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _override(user_id: str, db):
    async def _dep():
        return {"user_id": user_id, "db": db}
    return _dep


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------
def test_other_users_project_is_not_found(client):
    """B 사용자가 A 소유 프로젝트에 접근하면 404 여야 한다 (C1 핵심)."""
    db = FakeSupabase({
        "projects": [{
            "id": PROJECT_ID,
            "user_id": OWNER_ID,
            "original_filename": "owner.pdf",
            "status": "completed",
        }]
    })
    app.dependency_overrides[deps.get_current_user_and_db] = _override(ATTACKER_ID, db)

    res = client.get(f"/api/v1/projects/{PROJECT_ID}/geometry")

    # 403 이 아니라 404 인 이유: 타인 프로젝트의 존재 여부 자체를 노출하지 않기 위함
    assert res.status_code == 404, (
        f"타인 프로젝트가 노출되었습니다 (IDOR 재발). status={res.status_code}"
    )


def test_owner_can_access_own_project(client):
    """소유자는 자신의 프로젝트에 접근할 수 있어야 한다 (과수정 방지)."""
    db = FakeSupabase({
        "projects": [{
            "id": PROJECT_ID,
            "user_id": OWNER_ID,
            "original_filename": "owner.pdf",
            "status": "completed",
        }]
    })
    app.dependency_overrides[deps.get_current_user_and_db] = _override(OWNER_ID, db)

    # 소유권은 통과하고, geometry 파일이 없어 404 가 나온다.
    # 여기서 검증하는 것은 "소유권 검증을 통과했다" 는 사실이다.
    res = client.get(f"/api/v1/projects/{PROJECT_ID}/geometry")

    assert res.status_code == 404
    # 소유권 통과 시에는 디스크 상태에 따른 메시지가 반환된다.
    assert "Geometry data not available yet" in res.json()["detail"]


def test_database_outage_fails_closed(client):
    """
    DB 장애 시 인증을 우회하지 않고 503 으로 실패해야 한다.

    과거: `except Exception: logger.warning("bypassing check")` 로 인증 검사를
          건너뛰고 진행했다. DB 가 불안정한 순간이 곧 전면 공개 상태였다.
    """
    app.dependency_overrides[deps.get_current_user_and_db] = _override(
        ATTACKER_ID, ExplodingSupabase()
    )

    res = client.get(f"/api/v1/projects/{PROJECT_ID}/geometry")

    assert res.status_code == 503, (
        f"DB 장애 시 인증이 우회되었습니다 (fail-open 재발). status={res.status_code}"
    )


def test_project_list_returns_only_own_projects(client):
    """목록 조회도 소유권으로 필터링되어야 한다."""
    db = FakeSupabase({
        "projects": [
            {"id": "proj_owner", "user_id": OWNER_ID, "original_filename": "a.pdf",
             "status": "completed", "created_at": "2026-01-01", "updated_at": "2026-01-01"},
            {"id": "proj_other", "user_id": ATTACKER_ID, "original_filename": "b.pdf",
             "status": "completed", "created_at": "2026-01-02", "updated_at": "2026-01-02"},
        ]
    })
    app.dependency_overrides[deps.get_current_user_and_db] = _override(OWNER_ID, db)

    res = client.get("/api/v1/projects")

    assert res.status_code == 200
    ids = [p["id"] for p in res.json()["projects"]]
    assert ids == ["proj_owner"], f"타인 프로젝트가 목록에 노출되었습니다: {ids}"


def test_require_project_enforces_ownership_directly():
    """require_project 헬퍼 자체의 소유권 강제를 검증한다."""
    from fastapi import HTTPException

    db = FakeSupabase({
        "projects": [{"id": PROJECT_ID, "user_id": OWNER_ID}]
    })

    # 소유자: 정상 조회
    row = deps.require_project(db, PROJECT_ID, OWNER_ID)
    assert row["id"] == PROJECT_ID

    # 비소유자: 404
    with pytest.raises(HTTPException) as exc:
        deps.require_project(db, PROJECT_ID, ATTACKER_ID)
    assert exc.value.status_code == 404


def test_no_unscoped_project_queries_remain():
    """
    정적 회귀 게이트: endpoints.py 에 소유자 필터 없는 projects 조회가 남아있으면 실패.

    require_project(...) 를 경유하지 않고 `db.table("projects")` 를 직접
    select/update 하는 코드가 생기면 이 테스트가 잡아낸다.
    """
    import re
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "endpoints.py"
    text = src.read_text(encoding="utf-8")

    offenders = []

    # PostgREST 체인은 여러 줄에 걸쳐 작성되므로 줄 단위로 자르면 오탐한다.
    # (실제 사례: list_projects 의 .select(...)\n.eq("user_id", ...) 가
    #  .select 줄만 잘려 "소유권 필터 없음" 으로 오진되었다.)
    # 체인 시작점부터 다음 db.table( 또는 600자까지를 하나의 문장으로 본다.
    chain_re = re.compile(
        r'db\.table\("projects"\)\s*\.(?:select|update)\b'
        r'(?P<chain>.*?)'                 # DOTALL: 개행 포함
        r'(?=db\.table\(|\Z)',
        re.DOTALL,
    )

    for match in chain_re.finditer(text):
        chain = match.group("chain")
        # 과도하게 긴 체인은 다른 문장까지 삼켰을 가능성이 있어 잘라낸다
        snippet = chain[:600]
        if "user_id" not in snippet:
            offenders.append(
                (match.group(0)[:200]).replace("\n", " \\n ")
            )

    assert not offenders, (
        "소유권 필터 없는 projects 조회가 발견되었습니다 (IDOR 재발):\n"
        + "\n".join(offenders)
    )
