# 🎖️ 상용화 실사 및 출항 로드맵 v1.0

> **작성일:** 2026-08-29
> **작성:** 코다리 개발본부 (PMO 하네스)
> **대상:** `ai-cad` / Japanbuild-BIM3D Compliance SaaS
> **전제:** `code_remediation_plan_v1.0_20260826.md` (SP1~SP5 완수) 이후 잔여 리스크만 다룬다.
> **성격:** 낙관적 문서가 아니다. 모든 항목은 `파일:줄` 근거를 가진다.

---

## 0. 총평 (Executive Verdict)

### 한 줄 결론

> **엔진을 과하게 만든 것이 아니라, 만들어 둔 엔진을 제품에 연결하지 않았다.**
> 상용화 가능성은 **"있음"** 이나, 현재 상태로 출항하면 **안 됨**. 차단 결함 4건 해제 전까지 유료 결제 개통은 금지.

### 3축 판정

| 축 | 판정 | 근거 |
| :--- | :--- | :--- |
| **제품 완성도** | 🟡 B — 좁은 해피패스만 동작 | 파싱·적산·IFC는 실구현. 단 실측 코퍼스·스캔 도면 경로 미검증 |
| **상용 준비도** | 🔴 D — 출항 불가 | 멀티테넌시 격리 부재, 운영 UI가 Mock 폴백, 고객 도면 git 추적 |
| **엔지니어링 경제성** | 🟠 C — 오버스펙이 아니라 미연결 | `engine/` 18모듈 100% 데드코드, 100점 매트릭스가 그 데드코드를 인증 |

### 오버엔지니어링 질문에 대한 직접 답변

**"오버엔지니어링이 아닌가" → 절반은 맞고, 절반은 틀리다.**

- ❌ 틀린 부분: PSLG 토폴로지, 스케일 캘리브레이션, 실 ifcopenshell SSOT, Stripe 서명 검증, JWT fail-closed, 적산 包絡処理(중복 제거)는 **일본 BIM 규격 대응에 필수**다. 과잉이 아니다.
- ✅ 맞는 부분: 그 좋은 모듈들이 **`engine/` 패키지에 격리된 채 프로덕션에서 한 줄도 호출되지 않는다.** 동시에 제품은 `parser/`(OpenCV 컨투어) 기반 구형 경로로 돌아간다. 즉 **같은 기능을 두 벌 구현하고, 더 좋은 쪽을 버렸다.**
- 📌 진단명: **Over-built, Under-wired.** 설계를 줄일 게 아니라 **배선을 해야 한다.**

---

## 1. 🔴 CRITICAL — 출항 차단 결함 9건

> **진행 상황 (2026-08-30 갱신)**: C1 · C2 · C4 · C5 · C6 · C7 · **C10** 해결 완료.
> **미결: C3(`engine/` 미배선 — W0/W1 완료, 잔여 W2~W5) / C9 / C11.**
> 감사 당시 4건이었으나 Phase 0 중 결제 경로 3건(C5~C7)을 추가 발견했고,
> `engine/` 배선 실행 중 **프로덕션 코드 결함 2건(C10·C11)을 추가 확정**했다.
>
> **C10은 C1보다 심각하다.** C1은 "남의 데이터가 보인다"는 보안 결함이지만,
> C10은 **"제품의 핵심 기능(평면도에서 방 추출)이 성립하지 않는다"**는 기능 결함이다.
> 상세: `engine_wiring_audit_v1.0_20260830.md` §5.5

> 유료 결제 개통(`sk_live_*`) 전 전량 해제 필수. 미해결 시 법적·재무적 사고로 직결.

### C1. 멀티테넌시 격리 부재 ✅ 해결 — 전 고객 데이터 열람 가능 (IDOR)

**근거**

| 위치 | 내용 |
| :--- | :--- |
| `app/api/v1/endpoints.py` (1,685줄) | 프로젝트 접근 **전 구간**이 `.eq("id", project_id)` 단독 필터. 예: `:188` `:219` `:356` `:404` `:448` `:533` `:567` `:664` `:711` `:750` `:929` `:1027` `:1189` `:1508` |
| `grep -rn 'eq("user_id"' app/ correction/` | **결과 0건.** 사용자 스코프 필터가 코드베이스에 존재하지 않음 |
| `app/api/deps.py:27` | `create_client(SUPABASE_URL, SUPABASE_KEY)` — 정적 anon 키. 사용자 JWT를 PostgREST에 전달하지 않음 |
| `supabase/schema.sql:71-83` | RLS 정책이 `USING (auth.uid() = user_id)` |

**왜 치명적인가 — 이진 함정**

백엔드가 anon 키로 호출하므로 PostgREST 입장에서 `auth.uid()`는 항상 NULL이다.

- RLS가 **켜져 있으면** → 모든 `projects` 조회/수정이 빈 결과 → **제품이 전면 오동작**
- RLS를 **꺼두었거나 service_role이면** → 로그인한 누구나 UUID만 바꿔 **타 고객 프로젝트·IFC·도면 열람·수정·삭제 가능**

"동작하고 있다면" 후자 상태일 확률이 높다. **즉 현재 정상 동작은 취약점의 증상일 수 있다.**

**해결 (3층 방어)**

1. `deps.py` — 사용자 JWT를 PostgREST로 위임하는 인증 클라이언트 생성
   ```python
   def get_user_db(credentials=Depends(security)) -> Client:
       return create_client(SUPABASE_URL, SUPABASE_ANON_KEY,
                            options=ClientOptions(headers={"Authorization": f"Bearer {credentials.credentials}"}))
   ```
2. 애플리케이션 레벨 명시 필터 — **모든** `.table("projects")` 호출에 `.eq("user_id", user_id)` 부착 (13개소 + incidents 경로)
3. 회귀 테스트 — A유저 토큰으로 B유저 project_id 접근 시 403/404 검증. 이 테스트 없이는 완료로 인정하지 않는다.

**적용 결과 (2026-08-29)**

- `require_project(db, project_id, user_id, select=...)` 헬퍼를 신설하고 15개소에 부착. DB 오류는 503(fail-closed), 미소유/미존재는 구분 없이 404(타인 프로젝트 존재 여부 열람 차단).
- 3곳에 남아 있던 **fail-open 블록을 제거**했다 — 조회 실패를 로그만 남기고 인증 검사를 건너뛰던 코드(`get_project_geometry`, 미디어 업로드, 인시던트 핀).
- 그 과정에서 **네 번째 우회 경로**를 추가 발견했다:

```python
# app/api/v1/endpoints.py (compliance-checksheet, 수정 전)
try:
    project = require_project(db, project_id, auth_data["user_id"], select="*")
except Exception:
    project = {"id": project_id, "original_filename": f"Project_{project_id}"}
```

소유권 검증이 던진 404/503을 삼키고 가짜 프로젝트를 조립해 계속 진행하므로, **자신이 소유하지 않은 `project_id`로도 로컬 산출물을 읽어 적합性 체크시트를 발급**할 수 있었다. 소유권 필터를 부착해도 예외를 삼키면 무력화된다는 교훈이다 → `try/except` 제거, 실패 전파.

---

### C2. 운영 UI가 조용히 가짜 데이터로 폴백 ✅ 해결 — 컴플라이언스 제품 최악의 결함

**근거**

| 위치 | 내용 |
| :--- | :--- |
| `web/src/app/dashboard/editor/page.tsx:52` | `searchParams.get("project_id") \|\| "mock_project_123"` |
| `web/src/app/dashboard/editor/page.tsx:93` | `// Fallback Mock Data (개발용 시각적 완성도 보장)` |
| `web/src/app/dashboard/page.tsx:76` | `result.project_id \|\| "mock_project_123"` |
| `web/src/app/dashboard/reports/page.tsx:24,33` | `id: "mock_project_123"`, `id: "mock_project_456"` 하드코딩 |
| `web/src/app/dashboard/page.tsx:443` | `ACTIVE SCENE: TOKYO-AOYAMA-MOCK-201` 렌더링 |

**왜 치명적인가**

API 실패 시 **결제한 고객에게 실존하지 않는 도쿄 아오야마 데모 건물이 실제 분석 결과로 표시된다.** 이 제품은 법규 적합 판정 도구다. 오판정 결과를 근거로 시공사가 착공하면 **손해배상 청구의 근거가 된다.** "우아한 폴백"이 아니라 **문서 위조**다.

SP1에서 "문서 위조 폴백 소거"를 완료했다고 기록되어 있으나, **프론트엔드 폴백은 손대지 않았다.**

**해결**

- 모든 `mock_*` 식별자·하드코딩 제거
- `NODE_ENV === "production"` 또는 `NEXT_PUBLIC_ALLOW_MOCK=1` 아닌 경우 Mock 분기 자체를 빌드에서 제외
- API 실패 시 3D 씬을 비우고 **명시적 오류 배너 + 재시도** 노출. 빈 화면은 불편하지만, 가짜 화면은 사고다.
- 실패 주입 테스트: 백엔드 500 응답 시 UI가 오류 상태를 표시하는지 E2E 검증

---

### C3. 100점 매트릭스가 인증하는 코드가 제품 코드가 아니다

**근거**

```
$ grep -rln "from engine\.\|import engine\." --include="*.py" .
→ 9건: engine/pipeline/contracts.py, tests/test_sp2_reliability.py,
       test_stage1_models_rules.py, test_stage2_geometry_pool.py,
       test_stage3_rag_adapter.py, test_stage4_viewer_ifc_sync.py,
       verify_100_matrix.py, verify_cad_engine.py, verify_security_suite.py
```

```
$ grep -rno "from (parser|compliance|takeoff|pricing|exporter|engine|correction|scene|pipeline|...)"
     app/api/v1/endpoints.py
→ compliance.*, correction.*, domain.*, exporter.*, pipeline.paths, scene.*
→ engine.* : 0건
```

**프로덕션 실제 경로**
```
app/main.py → app/api/v1/endpoints.py → app/worker/tasks.py
            → core/engine.py → { domain, pipeline, harness, parser, compliance, scene }
```

**즉:** `engine/` 18개 모듈(PSLG 토폴로지, 스케일 캘리브레이션, JapanBuildingCodeRules, e-Gov RAG, Gemini/SLM 어댑터, SandboxExporterRunner, ExporterWorkerPool, IdempotentTaskPipeline, ContextFirewall)은 **테스트와 벤치마크만을 위해 존재한다.**

**100/100 점수의 진짜 의미:** *"제품이 사용하지 않는 코드는 우수하다."*
실제로 고객에게 서비스되는 `parser/`(OpenCV 컨투어 기반) 경로는 **100점 매트릭스의 평가 대상에 아예 없다.**

**해결 — 선택지 2가지, 결정 필요**

| 안 | 내용 | 비용 | 리스크 |
| :-- | :--- | :--- | :--- |
| **A안 (권장) — 배선** | `core/engine.py`가 `engine.*`를 호출하도록 전환. 구 `parser/` 경로 폐기 | 3~4주 | 회귀 폭발. E2E 골든셋 필수 |
| **B안 — 폐기** | `engine/` 삭제, `parser/` 경로에 스케일 캘리브레이션·토폴로지만 이식 | 1~2주 | 이미 만든 자산 매몰 |

👉 **A안 권고.** 단, 착수 전 `tests/` 골든셋을 프로덕션 경로 기준으로 재작성하는 것이 선행 조건이다. 지금 골든셋은 데드코드 기준이라 전환 시 회귀를 잡아내지 못한다.

---

### C4. 고객 도면 5건이 git 저장소에 추적 중 ✅ 해결 — 일본 APPI 위험

**근거**

```
$ git ls-files | grep uploads
uploads/17d473dc-9a39-445e-bc6a-9e9849000af0.pdf
uploads/2896049a-010e-4fa3-b662-4d60c294d6e6.pdf
uploads/4a5bac21-ae24-41d8-bbd8-85ce649b4c64.pdf
uploads/8d31de7c-ffdc-4998-9952-5e8175580c52.pdf
uploads/eaa65d3c-fb38-4361-a0c0-bbcc17d44f4c.pdf
$ git ls-files | grep chroma
vector_store/chromadb/chroma.sqlite3
```

`.gitignore:31`에 `uploads/`가 있으나 **이미 추적된 파일은 무시 규칙이 적용되지 않는다.** 이력 전체에 남아 있으며, 저장소가 public이거나 협력사에 공유되는 순간 **실제 발주처 도면 유출**이다.

**해결**

1. `git rm --cached uploads/ vector_store/ sessions/ tsconfig.tsbuildinfo`
2. `.gitignore`에 `vector_store/`, `sessions/`, `*.tsbuildinfo` 추가
3. 도면에 실제 발주처 정보가 포함되어 있다면 **히스토리 정리(`git filter-repo`) 필요** — 되돌릴 수 없는 작업이므로 사전 확인 필수
4. 업로드 경로를 컨테이너 외부 볼륨/오브젝트 스토리지로 분리

**상태: ✅ 해결 완료 (2026-08-29)** — 추적 해제 및 `.gitignore` 강화 적용. 잔여 과제는 히스토리 정리 필요 여부 판단(파일 5건은 동일 바이너리의 합성 테스트 픽스처로 확인되어 실고객 데이터는 아님).

---

### C5. 결제 경로가 실패를 가짜 결제로 흡수 — 매출 누수 + 우량오인

**근거** (`app/services/payment.py` 수정 전)

```python
# create_checkout_session() — Stripe 실패 시 예외를 삼키고 mock 으로 분기
except Exception as e:
    logger.error(f"Stripe Integration failed: {str(e)}")
    cls._handle_failure()
    # API 실패 시 바로 아래 Mock Fallback으로 스무스하게 분기
...
mock_checkout_url = f"https://mock-stripe.japanbuild.com/checkout/{mock_session_id}"
```

- Stripe 키 미설정 또는 API 장애 시 **존재하지 않는 결제 URL**을 고객에게 반환한다. 고객은 결제 화면으로 안내되지만 실제 결제 수단은 없고, 시스템은 정상 응답으로 기록한다.
- 클래스 독스트링에 `비즈니스 가용성을 100% 보장합니다`라고 명시되어 있다. **검증 불가능한 성능 표현**이며, 일본 景品表示法상 우량오인(優良誤認) 소지가 있다. 실패를 감추는 구조를 장점으로 광고하고 있다.

**해결** ✅ 적용 완료

1. `create_checkout_session()` — Stripe 실패를 mock으로 흡수하지 않고 예외 전파 (fail-closed)
2. mock 발급 조건을 **화이트리스트**로 변경: `PAYMENT_ALLOW_MOCK_WEBHOOK=1` **그리고** `ENV ∈ {local, development, dev, test, testing, staging}`. 과거 `ENV != "production"`는 ENV 미설정(기본값) 시 항상 참이 되어 운영 배포에서 ENV를 빼먹으면 mock이 열렸다.
3. 독스트링의 미검증 수치 표현 전량 제거
4. 체크아웃 500 응답에 내부 예외 메시지를 노출하지 않도록 변경(정보 유출 방지)

---

### C6. 결제 멱등성·원자성 부재 — 중복 지급 및 잔액 음수

**근거**

- **웹훅 멱등성 없음**: Stripe는 at-least-once 전달이므로 동일 `checkout.session.completed` 재전달마다 크레딧이 누적 지급된다. `event.id`를 수신하지만 저장·검사하지 않았다.
- **차감 경쟁 상태**: `deduct_credit()`이 `SELECT credits` → `UPDATE credits = 읽은값 - n` 구조다. 잔액 1 상태에서 동시 2요청이 모두 통과해 **잔액이 음수**가 되거나 무료 사용이 발생한다 (`profiles.credits`에 `CHECK (credits >= 0)`가 있어 후속 요청이 전부 500으로 번진다).
- **실패를 성공으로 위장**: 프로필 갱신 실패 시 `{"status": "fallback_success"}`를 반환했다. 결제는 완료됐는데 크레딧은 미지급되고 로그에는 성공으로 남는다.

**해결** ✅ 적용 완료

1. `supabase/schema.sql`에 `processed_payment_events` 테이블 추가 (PK = `event_id`, RLS 활성화 + 정책 없음 → service_role 전용). 웹훅 선점(claim) 방식으로 중복 차단.
2. 동일 파일에 `public.deduct_credits()` RPC 추가 — `FOR UPDATE` 행 잠금 단일 트랜잭션. 호출 주체 검사(`auth.uid() <> p_user_id` 차단)로 타인 크레딧 소진 공격 방지. `service_role`에만 EXECUTE 부여.
3. `deduct_credit()` — RPC 우선, 미배포 환경 대비 CAS(`.eq("credits", 읽은값)`, 3회 재시도) 폴백. 어느 쪽도 확정되지 않으면 `False`(무료 사용 차단).
4. 프로필 갱신 실패 시 `retryable=True` 오류 반환 + 이벤트 선점 해제 → Stripe 재전달로 복구. 웹훅 엔드포인트는 `retryable`에 따라 503/400 분리.
5. 회귀 테스트 `tests/test_p0_payment_integrity.py` 17종 추가

---

### C7. `get_payment_status`에 정의되지 않은 변수 참조 — 500 유발

**근거** (`app/api/v1/endpoints.py` 수정 전)

```python
except Exception as e:
    # DB 테이블 부재 시 Fallback
    logger.warning(f"Project media list fallback for {project_id}: {e}")
```

이 함수에는 `project_id`가 존재하지 않는다(복사-붙여넣기 잔재). DB 조회가 실패하면 정상 응답 대신 `NameError`가 발생해 500으로 번진다. 주석은 "Fallback"이라지만 폴백 로직 자체가 없다.

**해결** ✅ 적용 완료 — 오류 기록 후 보수적 기본값(`free` / 크레딧 0) 유지.

---

### C10. 벡터 정제 파이프라인이 내부 벽을 전부 삭제 ✅ 해결 — **핵심 기능 부재**

> 2026-08-30 추가 확정. `engine/` 배선(W1) 실행 중 발견. **`engine/`이 아니라
> 이미 운영 중인 `parser/` 경로의 결함**이며, 심각도는 C1~C9를 모두 상회한다.

**근거** (`parser/line_refine.py:384-398` 수정 전)

```python
def near(p, q, tol=join_tol) -> bool:
    return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol
# a의 양 끝점이 b의 양 끝점과 가까운지만 본다. 교차는 보지 않는다.
```

CAD 벡터 도면은 교차점에서 쪼개지지 않은 긴 선으로 저장된다(7x7 격자의 가로선은
x=100..900을 한 번에 긋는 세그먼트 1개). 따라서 내부 벽의 끝점은 다른 선의
끝점과 멀리 떨어져 **degree = 0 → 전부 삭제**된다.

**실측** (`uploads/` 실업로드 PDF, 8x8 격자):

| 단계 | 세그먼트 수 | 판정 |
| :--- | ---: | :--- |
| 1~4. refine / merge / snap / parallel | 16 | 정상 |
| **5. `filter_structural_walls`** | **4** | **내부 벽 12개 소실** |
| 최종 방 탐지 | **1개** | **정답 64실** |

살아남은 4개는 우연히 끝점이 일치하는 **외곽 테두리뿐**이다.
**벡터 PDF 평면도에서 방을 추출하는 핵심 기능이 성립하지 않았다.**

**근본 원인**: 평면 분할(Planar Subdivision) 부재. 차수 계산이든 면 추출이든
모든 위상 알고리즘은 입력이 "교차점에서 분할된 세그먼트 집합(PSLG)"일 것을 전제한다.
`engine/geometry/pslg_topology.py`의 결함(D1~D3)과 **동일 근본 원인**이다.

**해결** ✅ 적용 완료
- 신규 SSOT `core/planar.py` — 교차점 분할 `O(n log n + k)` + 하프엣지 회전 스윕 `O(V+E)`
- `parser/pdf_vector.py` 4단계와 5단계 사이에 `subdivide_at_intersections()` 배선
- `engine/geometry/pslg_topology.py` 전면 재작성 (D1·D2·D3 해소, 공개 API 유지)
- `tests/test_planar_subdivision.py` 27건 신규 → 전체 **200 passed / 7 skipped / 0 failed**

| 지표 | 수정 전 | 수정 후 |
| :--- | ---: | ---: |
| refined walls (8x8 격자) | 4 | **112** |
| 탐지된 방 | 1 | **49** (7x7 정답) |
| PSLG 7x7 방 추출 | 4,221 | **49** |
| 60x60 격자(3,600실) 소요 | 조합 폭발 | **24ms** |

---

### C11. 실도면 검증 데이터 0건 — 정확도 주장 불가 ⛔ **대표님 조치 필요**

> 2026-08-30 추가 확정. 코다리 개발 군단이 **직접 만들 수 없는 자산**이다.

`uploads/` PDF 5건 전수 조사 결과:

```
md5 전부 동일: 2d08c819b2e88b8c712fa42a4301075d
크기 2,647B / 페이지 1000x1000 / paths 16 / 텍스트 0건
```

- 5건 전부 **동일한 합성 픽스처** (동일 파일 5회 업로드)
- **텍스트 0건** → 치수 주석 추출 불가 = **C9를 해결할 입력이 존재하지 않음**
- 개구부 마스크 산출 흔적 없음 = **C8 재확인**
- `tests/` E2E 7건이 `sample.pdf` / `vector_test.pdf` / `multi_page_test.pdf`
  부재로 **skip** — 실도면 회귀 테스트 0건

**결론: 제품은 실제 평면도로 한 번도 검증된 적이 없다.**
C3(100점 벤치마크가 조작 입력으로 통과)와 정확히 같은 구조의 문제가
E2E 경로에도 존재한다.

**요청 사항**
1. **실제 일본 평면도 PDF 3~5건** (마스킹 후) — 텍스트 레이어(치수 주석) 필수
2. **정답지(ground truth)**: 각 도면의 실 목록·면적(m²)
   — 없으면 "49개 방을 찾았다"가 맞는지 검증할 방법이 없다
3. 확보 후 `tests/fixtures/` 편입 + skip 중인 E2E 7건 활성화

C10 수정으로 "내부 벽을 지우는 버그"는 고쳤으나,
**"실제 도면에서 몇 % 맞는지"는 여전히 미측정**이다.

---

## 2. 🟠 HIGH — 출항 전 정비 (4건 + 2건)

### H1. `SOP_commercial_launch.md`는 실행 불가한 허구 문서

| SOP 기술 내용 | 실제 상태 |
| :--- | :--- |
| §1.1 `ALTER TABLE projects/incidents/compliance_checksheets ENABLE RLS` | `supabase/schema.sql`(102줄)에 **테이블은 `profiles`, `projects` 2개뿐.** `incidents`, `compliance_checksheets` 부재 |
| §1.2 `tenant_id = (auth.jwt()...)` 기반 RLS | 스키마에 **`tenant_id` 컬럼 자체가 없음.** 실제는 `auth.uid() = user_id` |
| §2.1 `wrangler pages deploy ./web/dist` | Next.js 산출물은 `.next`. `./web/dist`는 **존재하지 않는 경로** |
| §2.2 `celery -A core.celery_app` | 실제 모듈은 `app.worker.celery_app` (`docker-compose.yml` 기준) |
| §4 `version` 정수 기반 409 충돌 프로토콜 | `projects` 테이블에 `version` 컬럼 없음 |
| §5 "MLIT BIM 의무화 법령 기준 정확히 만족" | 검증 근거 없음. 자기선언 |

**판정:** 이 문서는 **런북이 아니라 작문**이다. "1시간 내 무중단 셋업"은 검증된 사실이 아니다.
**조치:** 실제 배포 1회를 스크린캐스트로 기록하며 문서를 **재집필**한다. 또는 폐기하고 `README` + `docker-compose`로 대체.

### H2. 프론트엔드 2벌 / Next.js 메이저 2벌

| | 루트 | `web/` |
| :--- | :--- | :--- |
| Next | `15.4.9` | `16.2.6` |
| 용도 | 마케팅 + `app/api/generate-3d/route.ts` | 제품(대시보드/에디터/로그인) |
| lucide-react | `0.553.0` | `1.16.0` |
| three | `0.173.0` | `0.184.0` |

루트 `app/`은 Next App Router + `app/api/**` + Python `app/` 디렉터리가 **같은 경로에 섞여 있는** 상태로, `app/main.py`(FastAPI)와 `app/layout.tsx`(Next)가 공존한다. 빌드 혼선 및 신규 인원 온보딩 시 치명적 혼란.

**조치:** 루트는 **정적 마케팅 사이트**로 한정(또는 `site/`로 분리), 제품은 `web/` 단일화. 루트 `app/api/generate-3d`는 폐기 또는 `web/`로 이전.

### H3. 프론트엔드 CI 게이트 없음

`.github/workflows/ci.yml:38` — `# TypeScript 프론트 게이트는 web/ 의존성 설치 구조 정리 후 추가 예정 (부록 C 후속-4)`

**1,284줄의 TS/TSX가 무검증 상태로 main에 머지된다.** C2(Mock 폴백) 같은 결함이 CI에서 잡히지 않은 직접 원인.

**조치:** `web/` 워크플로 추가 — `tsc --noEmit`, `next lint`, `next build` 3단 게이트.

### H4. 법령 코퍼스 불완전 — BEI 판정의 근거가 없다

```
data/laws/manifest.json  → 법령 3건 명시 (건축기준법 / 시행령 / 省エネ法 427AC0000000053)
실제 존재 XML           → 2건 (325AC0000000201.xml, 325CO0000000338.xml)
```

- **省エネ法(427AC0000000053) XML이 디스크에 없다.** 그런데 SP5에서 BEI 규칙을 구현했고, `verify_100_matrix.py`는 "e-Gov 실코퍼스 926청크 Hit@3"을 채점한다.
- `sample_laws.json`(2.8KB)·`japanese_building_code_vol2.pdf`(1.9KB)는 **표본/자리표시자**다. 실법령이 아니다.
- SP2 기록에 "이관된 ChromaDB는 구 저장소 산물로 동일 판본인지 미검증" — **재적재(re-ingest) 미완료 상태로 방치됨.**

**조치:** 省エネ法 XML 확보 → `compliance/rag/ingest.py` 재실행 → 코퍼스 판본 해시를 `manifest.json`에 기록 → 매트릭스가 코퍼스 존재를 **선검증**(없으면 즉시 실패)하도록 게이트 추가.

### H5. Docker 이미지 비운영급

`Dockerfile` — `python:3.10-slim`(CI는 3.11 → **버전 불일치**), 단일 스테이지, root 실행, `chmod 777`, `COPY . .`(전체 복사), 헬스체크 없음, `.dockerignore` 부재.

### H6. 의존성 미고정 + 과중량

`requirements.txt` 전 항목 `>=` — **재현 빌드 불가.** `opencv-python` + `ifcopenshell` + `chromadb` + `celery` + `redis`가 하나의 이미지에 전부. dev/test/prod 미분리.
`requirements.txt`에 `pytest`, `pytest-asyncio`가 prod 이미지에 포함된다.

---

## 3. 🟡 MEDIUM — 위생 및 구조

| ID | 항목 | 근거 | 조치 |
| :-- | :--- | :--- | :--- |
| M1 | **이중 구현 5쌍** | `parser/room_detect.py`(351줄, OpenCV, **LIVE**) ↔ `engine/geometry/room_detect.py`(101줄, 벡터 토폴로지, **DEAD**) / `compliance/rules.py`(109, LIVE) ↔ `engine/compliance/rules.py`(224, DEAD) / `correction/patch.py`(113) ↔ `engine/correction/patch.py`(61) / `pipeline/contracts.py`(173) ↔ `engine/pipeline/contracts.py`(26) / `harness/`(89) ↔ `engine/harness/`(85) | C3 결정에 따라 일괄 통폐합 |
| M2 | 데드코드 잔존 | `core/engine.py:241` `_get_dummy_room_result()` | 삭제 |
| M3 | CORS 헤더 와일드카드 | `app/main.py:34,37` `allow_credentials=True` + `allow_headers=["*"]` | 화이트리스트로 축소 |
| M4 | fail-open 기본값 | `app/api/deps.py:14-16` `"https://your-project-url.supabase.co"`, `"your-jwt-secret"` | 기본값 제거, 미설정 시 기동 거부(JWT는 이미 production에서 거부 중 — URL도 동일하게) |
| M5 | 루트 스크립트 오염 | `verify_*.py` 15개 + `test_stage*.py` 4개가 저장소 루트에 산재. CI는 `tests/`만 실행 → **19개 중 다수가 미실행** | `tests/legacy/`로 이동 또는 삭제. 실행되지 않는 검증은 검증이 아니다 |
| M6 | 런타임 3벌 | Next 15(루트) + Next 16(web) + FastAPI/Celery/Redis | H2 해소로 2벌로 축소 |

---

## 4. 📊 상용 준비도 스코어카드

| 영역 | 점수 | 판단 근거 |
| :--- | :---: | :--- |
| 인증 (AuthN) | 🟢 8/10 | `app/api/deps.py:42-44` fail-closed — production에서 기본 시크릿이면 기동 거부. 우회는 명시 플래그+비운영 한정. **잘 됨** |
| 인가/테넌시 격리 | 🔴 1/10 | C1. 필터 0건 + JWT 미위임 |
| 결제 | 🟢 8/10 | `app/services/payment.py:139-183` 서명 검증 fail-closed, Mock 웹훅은 명시 플래그+비운영 한정. **잘 됨** |
| 데이터 무결성 | 🟠 5/10 | 실 ifcopenshell SSOT 전환(SP2)은 훌륭. 코퍼스 불완전(H4)이 감점 |
| 프론트 신뢰성 | 🔴 2/10 | C2 Mock 폴백 + CI 부재(H3) |
| 코드 구조 | 🟠 4/10 | 이중 구현 5쌍(M1) + 데드 패키지(C3) |
| 테스트 | 🟠 6/10 | 23파일 / assert 276건(충실). 단 대상이 데드코드(C3), 프론트 0건(H3) |
| 문서 | 🔴 2/10 | H1. SOP 실행 불가. README는 AI Studio 보일러플레이트 |
| 배포/운영 | 🟠 4/10 | H5, H6 |
| 법규 데이터 | 🟠 4/10 | H4 |
| **종합** | **🟠 44/100** | **출항 불가. C1~C4 해제 시 약 75점** |

---

## 5. 🗺️ 출항 로드맵

> 1스프린트 = 1주. 총 **8~10주**. C구간 완료 전까지 `sk_live_*` 개통 금지.

### Phase 0 — 출항 차단 해제 (2주) ⛔ 필수

| # | 작업 | 산출물 / DoD |
| :- | :--- | :--- |
| 0.1 | 사용자 JWT 위임 클라이언트 (`deps.py`) | `get_user_db()` 신설, anon 클라이언트 사용처 전량 교체 |
| 0.2 | `projects` 접근 13개소에 `.eq("user_id", ...)` 부착 | `grep -c 'eq("user_id"' app/` ≥ 13 |
| 0.3 | 타 테넌트 접근 차단 회귀 테스트 | A토큰→B프로젝트 403/404 검증. **통과가 완료 조건** |
| 0.4 | 프론트 `mock_*` 전량 제거 | `grep -r "mock_" web/src` = 0 |
| 0.5 | API 실패 시 오류 배너 노출 (폴백 금지) | 실패 주입 E2E 통과 |
| 0.6 | `engine/` 배선(A안) 또는 폐기(B안) **결정** | 결정 문서화. A안이면 Phase 1로 |
| 0.7 | 업로드 도면 git 추적 해제 + 히스토리 정리 여부 판단 | `git ls-files \| grep uploads` = 0 |

**게이트:** 0.3, 0.4, 0.7 완료 + 0.6 결정. 미충족 시 Phase 1 진입 불가.

#### Phase 0 진행 상황 (2026-08-29 종료 시점)

| # | 작업 | 상태 | 검증 |
| :- | :--- | :--- | :--- |
| 0.1 | 사용자 JWT 위임 클라이언트 | ✅ | `deps.py` `_build_client()` + `postgrest.auth(token)` |
| 0.2 | `projects` 접근 소유권 필터 | ✅ | `require_project()` 15개소 + `.eq("user_id")` 4개소 |
| 0.3 | 타 테넌트 접근 차단 회귀 테스트 | ✅ | `test_p0_tenant_isolation.py` 6종 통과 |
| 0.4 | 프론트 `mock_*` 전량 제거 | ✅ | `grep -r "mock_" web/src` = **0** |
| 0.5 | API 실패 시 오류 배너 (폴백 금지) | ✅ | 뷰어 상태 오버레이 + 재시도 버튼 |
| 0.6 | `engine/` 배선(A) vs 폐기(B) 결정 | ⛔ **미결** | 대표님 결정 대기 |
| 0.7 | 도면 git 추적 해제 | ✅ | `git ls-files` 검증 0건 |
| + | 결제 경로 C5~C7 해결 | ✅ | `test_p0_payment_integrity.py` 19종 통과 |

**통합 검증 결과**

```
$ pytest tests/            → 173 passed, 7 skipped, 0 failed
$ cd web && tsc --noEmit   → 무오류
$ grep -r "mock_" web/src  → 0건
```

**0.6 미결로 Phase 1 진입 불가.** 나머지 Phase 0 항목은 전부 완료되었다.

> **작업 중 추가로 드러난 사실**: 소유권 검증을 부착하자 **기존 테스트 4건이 결함 동작을 정답으로
> 검증하고 있던 것이 확인**되었다(미소유 프로젝트로 200 응답, `user_id` 없는 픽스처 등).
> 즉 기존 테스트 스위트는 취약점을 통과시키는 방향으로 작성되어 있었다.
> 이는 "테스트 23파일이 있다"는 사실이 품질을 보증하지 못한다는 C3의 지적을 다시 확인시킨다.

### Phase 1 — 단일 진실 공급원 (3주)

| # | 작업 |
| :- | :--- |
| 1.1 | 프로덕션 경로 기준 **골든셋 재작성** (현재 골든셋은 데드코드 기준) |
| 1.2 | A안: `core/engine.py` → `engine.*` 전환. 스케일 캘리브레이션·PSLG 토폴로지를 실경로에 연결 |
| 1.3 | 중복 모듈 5쌍 폐기 (`parser/room_detect.py` vs `engine/geometry/room_detect.py` 등) |
| 1.4 | `verify_100_matrix.py`가 **프로덕션 import 경로**를 검증하도록 개편 (미연결 모듈 채점 금지) |
| 1.5 | 프론트엔드 단일화 — 루트 Next 15 정적 마케팅 only, 제품은 `web/` |

**게이트:** `grep -rn "engine\." app/` 결과 1건 이상 (연결 증명) + 기존 pytest 116 전량 통과.

### Phase 2 — 품질 게이트 및 코퍼스 (2주)

| # | 작업 |
| :- | :--- |
| 2.1 | `web/` CI 게이트 (`tsc --noEmit` + `next lint` + `next build`) |
| 2.2 | 省エネ法 XML 확보 → RAG 재적재 → 코퍼스 판본 해시 기록 |
| 2.3 | 매트릭스에 "코퍼스 존재 선검증" 게이트 추가 (없으면 즉시 실패) |
| 2.4 | 루트 `verify_*.py` / `test_stage*.py` 19개 → `tests/legacy/` 이동 후 실행 or 삭제 |
| 2.5 | 실 스캔 도면(벡터 없는 PDF) 10건 E2E — OCR/이미지 경로 실측 |

**게이트:** CI 전 구간 녹색 + 스캔 도면 10건 중 8건 이상 의미 있는 결과.

### Phase 3 — 운영 준비 (2~3주)

| # | 작업 |
| :- | :--- |
| 3.1 | Dockerfile 다중 스테이지, non-root, 헬스체크, `.dockerignore`, Python 3.11 통일 |
| 3.2 | 의존성 핀 고정 + prod/dev 분리 (`requirements-prod.txt`) |
| 3.3 | CORS 헤더 화이트리스트, `SUPABASE_URL` 기본값 제거 |
| 3.4 | 구조화 로깅 + 요청 ID + `/health` + 외부 호출 타임아웃 전면 부여 |
| 3.5 | SOP **재집필** (실제 배포 1회 기록 기반) 또는 폐기 |
| 3.6 | 실제 배포 1회 (스테이징) — 문서와 현실의 일치 확인 |

---

## 6. 🚫 하지 말 것 (명시적 스코프 컷)

상용화까지 아래는 **만들지 않는다.** 현재 병목은 기능 부족이 아니라 배선·신뢰성이다.

| 항목 | 이유 |
| :--- | :--- |
| 오프라인 델타 동기화 / 409 충돌 병합 UI | `version` 컬럼 자체가 없음(H1). 실수요 검증 전 과잉 |
| 다국어(i18n) 엔진 확장 | 초기 시장은 일본 단일. JP 외 번역층은 순수 부채 |
| Celery 워커 도쿄/오사카 2리전 분산 | 트래픽 실측 전 과잉. 단일 리전 + 오토스케일로 충분 |
| SLM + Gemini 듀얼 어댑터 유지 | 운영 복잡도 2배. **Gemini 단일**로收斂 후 필요 시 분리 |
| e-Gov 법령 자동 갱신 파이프라인 | 분기별 수동 갱신 + 해시 검증으로 충분 |
| `incidents` / `compliance_checksheets` 신규 테이블 | 엔티티 모델 확정 전 스키마 증설 금지 |
| 신규 마케팅 페이지 추가 | 루트/`web/` 분리(H2) 전 증설 금지 |

---

## 7. ✅ 최종 출항 게이트 (Go/No-Go)

전부 충족 시에만 `sk_live_*` 개통.

- [ ] **C1** 타 테넌트 접근 차단 회귀 테스트 통과
- [ ] **C2** `grep -r "mock_" web/src` = 0, 실패 주입 E2E 통과
- [ ] **C3** `engine/` 배선 완료 또는 폐기 완료, pytest 116 전량 통과
- [ ] **C4** `git ls-files \| grep -E "uploads/\|vector_store/\|sessions/"` = 0
- [ ] **H3** 프론트 CI 게이트 녹색
- [ ] **H4** 省エネ法 코퍼스 확보 + 재적재 + 판본 해시 기록
- [ ] 실 도면(벡터 5 / 스캔 5) E2E 10건 중 8건 이상 유효 결과
- [ ] 보안 재감사 통과 (인가·업로드 검증·CORS 중심)
- [ ] 스테이징 실배포 1회 완료 및 SOP 재집필

---

## 8. 권고 의사결정 사항 (대표님 확인 요청)

| # | 쟁점 | 권고 |
| :- | :--- | :--- |
| 1 | `engine/` 배선(A) vs 폐기(B) | **A안.** 단 골든셋 재작성(1.1) 선행 필수 |
| 2 | 업로드 도면 git 히스토리 정리 | 도면에 실 발주처 정보 포함 여부 확인后 결정. 포함 시 `filter-repo` 필요(되돌릴 수 없음) |
| 3 | SOP 재집필 vs 폐기 | **재집필.** 단 실제 배포 1회 이후, 스크린캐스트 근거 기반 |
| 4 | 루트 Next 앱 처리 | 정적 마케팅 사이트로 축소 후 `site/` 분리 권고 |
| 5 | 출항 시점 | Phase 2 완료(약 7주) 이후 스테이징 실배포까지. **8주 미만 단축 비권고** |

---

> **코다리 개발본부 보고:**
> 본 프로젝트의 엔지니어링 역량은 실제합니다. 인증 fail-closed, 결제 서명 검증, 실 ifcopenshell SSOT, 적산 包絡処理, 벤치마크 자기기만 방지 AST 게이트는 동급 스타트업 상위권입니다.
> 그러나 **좋은 부품이 조립되지 않은 상태로 포장만 완료되어 있습니다.** 현재 100/100 인증서는 제품이 아닌 창고 재고에 대한 것입니다.
> **권고: 출항 연기. Phase 0(2주) 착수를 요청드립니다.**

---

*문서 버전: 1.0.0 | 분류: 내부 기밀*
