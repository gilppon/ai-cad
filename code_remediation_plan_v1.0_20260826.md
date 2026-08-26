# 🎖️ 코다리 개발 군단 — 코드 보수 계획서 v1.0

| 항목 | 내용 |
|---|---|
| 문서명 | 일본 시장 BIM 규격 견적서 대응 및 밸리데이션 100점(진위 검증형) 코드 보수 계획서 |
| 작성일 | 2026-08-26 |
| 작성 | 코다리 부장 (CTO 아키텍트 총괄 / 보안·QA·DBA·성능·인프라 군단 합동 감사) |
| 대상 저장소 | `ai-cad` (Python FastAPI 엔진 + Next.js 15/16 이중 프론트) |
| 상위 문서 | `implementation_plan_v2.0_20260702_1522.md`, `SOP_commercial_launch.md` |

---

## 0. 요약 (Executive Summary)

**직언(Direct Candor): 현재 `verify_100_matrix.py`의 "100점"은 가짜다.**

1. **견적서 기능이 코드베이스에 존재하지 않는다.** `見積`(견적)·`積算`(적산/수량산출)·`単価`(단가)·`内訳`(내역)·quantity·takeoff 키워드가 전체 소스에서 **0건** 발견. 일본 시장 견적서가 BIM 규격에 맞아야 한다는 요구는 현재 구현량 기준으로 **신규 모듈 설계가 선행**되어야 한다.
2. **BIM 내보내기가 위장되어 있다.** 벤치마크(`verify_100_matrix.py:112-142`)는 손으로 작성된 가짜 IFC 텍스트 스텁(`engine/exporters/export_ifc.py`)을 채점하고, 뷰어 성능 10점은 **하드코딩**(L141). 실제 ifcopenshell 경로(`parser/export_ifc.py`)는 채점 대상조차 아니다.
3. **법규 판정값이 수학적으로 틀려 있다.** 래스터 파이프라인은 `pixel_to_mm=5.0`(`core/engine.py:92`)인데 법규 체커는 `px_to_m=0.01` 하드코딩(`compliance/extractor.py:91,104`) → 채광 1/7 등 면적 판정이 **약 2배 오차**. 잘못된 「適合」 문서를 발행할 수 있는 수준.
4. **보안 결함이 과금 체계를 무력화한다.** 만료 JWT 자동 우회(`app/api/deps.py:46-63`), 프론트 하드코딩 토큰(`web/src/app/dashboard/page.tsx:38`), DB 오류 시 접근 게이트 fail-open(`app/services/payment.py:253-288`).

본 계획서는 (A) 법규·표준 조사 결과, (B) 결함 진단, (C) BIM 적산·견적 신규 설계, (D) 보수 항목(P0~P2), (E) **진위 검증형 밸리데이션 매트릭스 재설계**, (F) 실행 로드맵을 담는다.

---

## 1. 조사 결과 — 일본 법규·BIM 표준 최신 동향 (2026-08 기준)

### 1.1 건축 관련 법령 현행화

| 법령 | 시점 | 내용 | 본 프로젝트 영향 |
|---|---|---|---|
| 建築物省エネ法(건축물 채에네기야법) | **2025-04 전면시행** | 신축 주택·건축물 **전체**에 채에네기준 적합 의무화, 4호특례 폐지, 목조 벽량계산(壁量計算) 심사 재검토 | 현재 코드에 채에네/BEI 규칙 0건 → 신규 규칙 세트 필요 |
| 동법 중규모 비주거 강화 | **2026-04 시행** | 연면적 300㎡~2,000㎡ 비주거, 1차 에너지소비량(BEI) 기준 인상 | 체크시트에 BEI 항목 추가 대응 필요 |
| 建築基準法・施行令 | repo 보유 e-Gov XML (`data/laws/325AC0000000201.xml`, `325CO0000000338.xml`) | 채광 1/7(법28조), 환기 1/20, 배연 1/50(令126の2), 계단폭(令23), 피난동선 등 | 판본(개정연월) 메타데이터 확인 후 골든셋 고정 |
| 適格請求書発行事業者(인보이스 제도) | 시행 중 | 견적·청구서에 등록번호 T+13자리 필수 | PDF 헤더에 **가짜 번호 하드코딩 금지** (`exporter/pdf_generator.py:152` `T1234567890123`) — 실제 등록번호 주입 구조로 변경 |

### 1.2 BIM 규격 (견적서가 맞추어야 할 표준)

| 표준 | 핵심 | 본 프로젝트 적용 |
|---|---|---|
| **IFC (ISO 16739)** — IFC4/IFC4.3 | 공간·부재·속성의 개방형 교환 포맷 | `parser/export_ifc.py`가 실제 경로. IfcSpace/IfcWall에 **수량 산출용 속성세트(Pset)** 부착 필요 |
| **ISO 19650 (JIS A 1981~)** | 정보관리: EIR(발주자 정보요건)/BEP(실행계획서), CDE | 산출물 명명·메타데이터 규격에 반영 |
| **국토교통성 BIM/CIM 적산(積算)** + buildingSMART Japan 「BIM/CIM積算のためのモデル作成ガイドライン」 | 적산용 속성정보 표준, **数量取合書**(수량취합서: 발주자-수급인 수량 정합 확인), 부재 분류체계 | 견적 모듈의 데이터 모델 근거 (§3) |
| 국토교통성 BIM 표준 가이드라인 / LOD | 단계별 모델 상세도(LOD) 정의, **包絡処理·勝ち負け処리**(부재 겹침 제거 — 수량 중복 방지) | takeoff 엔진의 겹침 해소 로직 필수 |
| 建築積算 규준 (공사비내역 구조) | 직공공사비 = [공사종류별 내역서] + [처별 내역서] + [품목별 내역서] + 공사일반공사비 + 경비 | 견적 PDF/JSON 스키마 설계 근거 (§3.3) |

> **결론**: "일본 시장 견적서 = BIM 규격"은 ①IFC에서 **검증 가능한 수량**을 뽑고 ②数量取合書 호환 내역 구조로 집계하며 ③인보이스 등록번호·소비세(10%)를 갖춘 見積書를 출력하는 3층 구조를 의미한다. 현 코드는 3층 모두 부재.

---

## 2. 진단 — 프로젝트 파일 고도화 문제점 (군단 합동 감사)

### 2.1 Top 10 치명 결함 (심각도 순, 원본 교차검증 완료)

| # | 심각도 | 결함 | 위치 | 증상 |
|---|---|---|---|---|
| 1 | 🔴 P0 | **인증 우회 체인**: 만료/무효 JWT를 `user_123`으로 승격 (ENV≠production 또는 기본 시크릿일 때) + mock 토큰 화이트리스트 | `app/api/deps.py:28-33, 46-47, 54-55, 61-63` | 유료 게이트 전면 무력화 |
| 2 | 🔴 P0 | **프론트 하드코딩 베어러 토큰** | `web/src/app/dashboard/page.tsx:38` | 운영 배포 시 타인 신분 도용 |
| 3 | 🔴 P0 | **결제 게이트 fail-open**: 회로 OPEN→무료접근, DB 예외→접근 승인/크레딧 미차감 반환 | `app/services/payment.py:231-233, 253-256, 286-288` | 매출 누수 |
| 4 | 🔴 P0 | **법규 스케일 버그**: 파이프라인 `pixel_to_mm=5.0` vs 컴플라이언스 `px_to_m=0.01` 하드코딩 → 면적 ~2배 왜곡 | `core/engine.py:92` vs `compliance/extractor.py:91,104` | **잘못된 適合/不適合 판정 발행** |
| 5 | 🔴 P0 | **미디어 서빙 경로 순회**: URL 세그먼트를 그대로 파일경로 조립, traversal 가드 없음 | `app/api/v1/endpoints.py:930-939` | 임의 파일 읽기 |
| 6 | 🔴 P0 | **웹훅 서명 검증 ENV 의존**: 서명 없고 ENV≠production면 통과 | `app/services/payment.py:136-155` | 임의 plan_type(99999 크레딧) 주입 |
| 7 | 🟠 P1 | **가짜 BIM 익스포터 + 채점 조작**: 손작성 IFC 스텁, 뷰어 성능 10점 하드코딩 | `engine/exporters/export_ifc.py`, `engine/exporters/export_step.py`, `verify_100_matrix.py:133,141` | 100점이 실력과 무관 |
| 8 | 🟠 P1 | **회로차단기 영구 잠금**: `recovery_timeout` 무시, 반납 로직 없음, `process_document` 전면 래핑 | `harness/circuit_breaker.py:34-39` (+`core/engine.py:25`) | 일시 장애 3회 → 변환 전면 불가(재시작까지) |
| 9 | 🟠 P1 | **죽은 RAG·깨진 STEP 경로**: 구 저장소 절대경로 하드코딩, FreeCAD 경로+부재 스크립트 참조 | `compliance/rag/retriever.py:5`, `compliance/rag/ingest.py:8-9`, `parser/room_export.py:18-19` | 기능 무음 no-op |
| 10 | 🟠 P1 | **체크시트 값 조립이 한국어 문자열 regex 파싱** + 실패 시 **가짜「適合」목데이터 폴백** | `endpoints.py:1171-1228, 1247-1265` | 공식 문서 위조 리스크 |

### 2.2 구조적·위생 결함 (보수 대상)

- **이중 모듈 트리**: `compliance/` vs `engine/compliance/`, `correction/` vs `engine/correction/`, 실제 vs 스텁 익스포터 — 벤치마크가 스텁을 채점하는 원인. SSOT(단일 진실원) 확정 필요.
- **의존성 누락**: `requirements.txt`에 `reportlab`, `google-genai` 미기재 → `from google import genai`(`compliance/gemini_adapter.py:5`)는 **앱 시작 시 ImportError** 가능.
- **스키마 드리프트**: `supabase/schema.sql`에 `profiles.plan_type/credits/stripe_subscription_id`, `projects.metadata` 컬럼 부재 — 런타임 사용 컬럼과 불일치, 예외 흡수로 은폐됨.
- **예외 흡수**: bare `except:`(`app/worker/tasks.py:58`), `except Exception: pass` 12곳(`endpoints.py` 7, `parser/export_step.py` 4 등).
- **print() 127건** (parser/compliance/core) — logging 미전환.
- **단위환산 산재**: mm/cm/m·px↔m 환산이 10여 개 파일에 흩어져 있고 기본값이 서로 충돌(#4의 근원).
- **테스트 인프라**: pytest 17파일/~91함수 존재하나 `conftest.py`·CI 설정 부재, 루트의 verify_*.py 11개는 CI 미편입.
- **CORS 완화**: `allow_methods=["*"]` + `allow_credentials=True`(`app/main.py:27-33`).

---

## 3. 신규 설계 — BIM 규격 견적서 모듈 (현재 전무)

### 3.1 디렉터리 (신설)

```
takeoff/
  __init__.py
  quantities.py      # IFC/룸 지오메트리 → 수량 (면적·연장·체적)
  overlap_resolver.py# 包絡処理/勝ち負け処理 — 부재 겹침 제거(수량 중복 방지)
  classification.py  # bSJ 적산용 분류체계 매핑 (IfcClassificationReference)
pricing/
  __init__.py
  unit_price_book.py # 단가 마스터 로더 (data/pricing/*.json)
  breakdown.py       # 公事費内訳書 빌더: 직공공사비/공사일반공사비/경비
exporter/
  quotation_pdf.py   # 見積書 PDF (ReportLab, 인보이스 등록번호 주입)
  quotation_json.py  # 数量取合書 호환 JSON
data/pricing/
  unit_prices_jp.json# 품목·공정·단위·단가(¥)·유효일 (버전관리 대상)
```

### 3.2 수량 산출 규칙 (quantities.py)

- 원천: `parser/export_ifc.py`가 생성한 IfcSpace(바닥면적)/IfcWallStandardCase(연장×두께×높이)/IfcOpeningElement.
- 산출 항목: `{item_code, name_ja, unit(m²/m³/m/式), quantity, source_entity(IFC GUID)}` — **모든 수량은 IFC 엔티티 역추적 가능**해야 함(数量取合書 정신).
- 검증: 수량 합계 vs 룸 면적 합계 편차 > 1% 시 WARN.

### 3.3 내역서 구조 (breakdown.py) — 일본 적산 관행 준수

```
総工事費
 ├─ 直接工事費
 │   ├─ 工種別内訳書 (철거/방수/타일… × 수량×단가)
 │   ├─ 部位別内訳書 (UB/PK/MB/발코니…)   ← JPResponsibilityEngine의 RoomKind와 연계
 │   └─ 品目別内訳書
 ├─ 共通仮設費 / 工事原価
 └─ 経費 (一般管理費 등) + 消費税 10%
```

### 3.4 IFC 속성 보강 (기존 parser/export_ifc.py 수정)

- IfcWall/IfcSpace에 `IfcPropertySet`: `Quantity_Area`, `Quantity_Volume`, `Finish`, `UnitPriceRef(item_code)` 부착 → **BIM 모델 자체가 견적서의 원장**이 되게 함(ISO 19650 정보 일관성).
- `IfcProject`에 `IfcClassificationReference`(bSJ 적산 분류) 연결.

### 3.5 API

```
POST /api/v1/projects/{id}/quotation        # takeoff+pricing → 견적 JSON (크레딧 차감)
GET  /api/v1/projects/{id}/quotation.pdf    # 見積書 PDF
```

---

## 4. 코드 보수 항목 (P0 → P2, 파일별 DoD)

### P0 — 보안·법규 정합성 (출항 전 필수)

| ID | 보수 내용 | 위치 | DoD(완료기준) |
|---|---|---|---|
| S-1 | mock 토큰 화이트리스트·무효JWT user_123 승격 제거. 로컬 전용 플래그(`ALLOW_AUTH_BYPASS=1` 명시 설정 시만) | `app/api/deps.py` | 유효하지 않은 토큰 → 항상 401. 테스트는 fixture로 주입 |
| S-2 | 프론트 하드코딩 토큰 제거 → Supabase 세션 토큰 사용 | `web/src/app/dashboard/page.tsx:38` | 소스에 JWT 문자열 0건 (grep 게이트) |
| S-3 | 결제 게이트 fail-open → fail-closed. DB 예외 시 403 반환, 크레딧 차감은 트랜잭션 처리 | `app/services/payment.py:231-288` | 예외 시 접근 거부 테스트 추가 |
| S-4 | 웹훅 서명 미검증 제거 — ENV 무관 서명 필수 | `app/services/payment.py:136-155` | 무서명 페이로드 400 테스트 |
| S-5 | 미디어 서빙에 `pipeline/paths.resolve_output_path` 가드 적용 | `endpoints.py:930-939` | `../` traversal 404/400 테스트 |
| L-1 | **스케일 SSOT**: `ScaleCalibrator` 결과를 compliance 체인에 전달, `px_to_m=0.01` 하드코딩 삭제 | `compliance/extractor.py:91,104`, `core/engine.py:92` | 골든 도면에서 채광면적 오차 <0.5% 테스트 |
| L-2 | 체크시트 목데이터「適合」폴백 삭제 → 판정 불가 시 `判定不能` 명시 | `endpoints.py:1247-1265` | 폴백 경로 유닛테스트로 금지 |
| L-3 | 규칙↔리포트 문자열 regex 결합 제거: rules가 구조화 `structured_facts` dict를 반환, PDF가 그것을 소비 | `compliance/rules.py`, `engine/compliance/rules.py`, `endpoints.py:1171-1228` | 메시지 문구 변경 시 테스트 깨지지 않음 |
| L-4 | 법령 판본 고정: e-Gov XML 개정연월을 `data/laws/manifest.json`으로 기록, 체크시트에 「根拠法令・施行日」 표기 | `data/laws/`, `exporter/pdf_generator.py` | 판본 표기 출력 확인 |
| D-1 | 가짜 등록번호 하드코딩 제거 → env/config 주입, 미설정 시 문서에 「(未登録)」 표기 | `exporter/pdf_generator.py:152`, `endpoints.py:1091-1092` | grep `T1234567890123` 0건 |

### P1 — 아키텍처·견적 모듈

| ID | 보수 내용 | 위치 | DoD |
|---|---|---|---|
| A-1 | 회로차단기 recovery_timeout 구현(half-open 재시도), `recovery_timeout` 파라미터 실사용 | `harness/circuit_breaker.py` | 60s 후 half-open 전환 테스트 |
| A-2 | 스텁 익스포터 삭제, `engine/exporters/*` → `parser/export_ifc.py`(ifcopenshell) 단일화(SSOT) | `engine/exporters/` | 스텁 파일 0건 |
| A-3 | RAG 경로 수정: 절대경로 → `<repo>/vector_store/chromadb` 상대 구성 | `compliance/rag/retriever.py:5`, `ingest.py:8-9` | ingest→retrieve 왕복 통합테스트 |
| A-4 | requirements.txt에 `reportlab`, `google-genai` 추가(+버전 핀) | `requirements.txt` | 클린 venv에서 앱 기동 성공 |
| Q-1 | §3 takeoff/pricing/quotation 모듈 신설 + 단가 JSON 스키마 | §3.1 | 견적 E2E 테스트(IFC→JSON→PDF) |
| Q-2 | IFC 속성세트(Pset 수량·단가참조·분류) 부착 | `parser/export_ifc.py` | ifcopenshell 재파싱으로 속성 조회 확인 |
| A-5 | Supabase 마이그레이션: 누락 컬럼 추가(`plan_type`,`credits`,`stripe_subscription_id`,`projects.metadata`) | `supabase/schema.sql` | 마이그레이션 스크립트 + 스키마 드리프트 테스트 |
| A-6 | FreeCAD STEP 경로 config화 + 부재 스크립트 복구 or 기능 제거 | `parser/room_export.py:18-19` | 경로 미설정 시 명확한 에러 |

### P2 — 위생·운영

| ID | 보수 내용 | 위치 | DoD |
|---|---|---|---|
| H-1 | print→logging 전환 (127건, 모듈별 logger 명명) | parser/, compliance/, core/ | print( ) 0건 grep 게이트 |
| H-2 | 예외 흡수 제거: bare except/except-pass → 로깅+명시적 처리 | `tasks.py:58`, endpoints 7곳 등 | ruff/flake8 규칙 통과 |
| H-3 | CORS 화이트리스트화 | `app/main.py` | 와일드카드+credentials 조합 제거 |
| H-4 | CI 편입: pytest 17파일 + verify_100_matrix v2를 GitHub Actions에서 실행 | `.github/workflows/` | PR마다 100점 게이트 |
| H-5 | 단위환산 유틸 통합(`units.py` 하나로 수렴) | 신설 `core/units.py` | 환산 상수 중복 정의 0건 |

---

## 5. 밸리데이션 100점 재설계 — "진위 검증형" 매트릭스 v2

현행 매트릭스의 조작 지점을 제거하고, **실제 경로만 채점**한다.

| 도메인 | 배점 | 현행 문제 → v2 채점 방식 |
|---|---|---|
| D1 CAD 파싱 (20) | 20 | 유지(PSLG+스케일 캘리브레이션 실측) |
| D2 일본 법규 (25) | 25 | ①결정론 규칙 15: **골든셋**(합격/불합격 도면 각 N개, 기대판정 고정) 일치율 ②RAG 10: **e-Gov XML 실코퍼스 질의** 적중률(자기 노드 자기검색 폐지). 스케일 오차 ±0.5% 이내 전제 |
| D3 BIM/견적 (25) | 25 | ①IFC 유효성 10: **실 ifcopenshell 생성물을 ifcopenshell로 재파싱** — 스키마 검증 + Pset 수량 vs 기하 재계산 편차<1% ②**견적서 10**: IFC→수량→내역 JSON→PDF 파이프라인 E2E, 数量取合書 필수키 존재 ③DXF/뷰어 5: 성능 **실측**(p95 프레임시간) |
| D4 신뢰성 (15) | 15 | 유지 + 회로차단기 half-open 회복 테스트 포함 |
| D5 보안/하네스 (15) | 15 | 유지 + **fail-closed 게이트 테스트**(결제 예외→403), traversal 차단 테스트 추가 |

**게이트 규칙**: 총점 100 달성 + 각 도메인 60% 미달 시 전체 실패 처리. 하드코딩 점수 문법(`scores[...] = 10` 상수 대입) 금지 — 모든 점수는 측정값 함수여야 하며, PMO 하네스가 diff에서 상수 대입 패턴을 탐지하면 CI 차단.

---

## 6. 실행 로드맵 (Sprint 단위)

| Sprint | 범위 | 산출 |
|---|---|---|
| **SP1 (즉시, P0)** | S-1~S-5, D-1, L-1~L-2 | 보안 패치 + 법규 판정 정확도 복원, pytest 회귀 추가 |
| **SP2** | L-3~L-4, A-1~A-6 | 구조화 facts 리팩터링, 회로차단기/의존성/RAG 수복 |
| **SP3** | Q-1~Q-2 | takeoff/pricing/quotation 신설, 단가 JSON 초판(방수·타일·철거 품목) |
| **SP4** | 매트릭스 v2 + H-1~H-5 | 진위 검증형 100점 게이트, CI 녹색화 |
| **SP5** | 채에네법 대응 | BEI/중규모 비주거(2026-04 강화분) 규칙 세트 + 체크시트 항목 추가 |

## 7. 리스크 및 회로차단기 (PMO)

- **단가 DB 초기 데이터 부재 리스크**: SP3에서 공개 단가(국토교통성 적산기준·적산표) 기반 초판 구성, 사업자 단가 교체 가능 설계.
- **법 개정 추적**: `data/laws/manifest.json`에 개정연월 기록 + 분기별 갱신 SOP(SOP_commercial_launch.md에 편입 권고).
- **변경 이력 보존**: 본 계획서 승인 후 모든 P0 커밋은 `remediation/S-*` 브랜치 네이밍 + PR에 DoD 체크리스트 첨부.
- **금지 조항**: 「適合」 목데이터 폴백 재도입, 벤치마크 상수 점수, 하드코딩 등록번호 — 발견 시 즉시 롤백 대상.

---
*본 계획서의 모든 파일 경로·라인 번호는 2026-08-26 기준 실측(grep/원본 열람) 검증 완료.*

---

## 부록 A. 실행 이력 (PMO 변경 이력 보존)

### SP1 — P0 보안·법규 정합성 (2026-08-26 완료)

| ID | 상태 | 구현 내역 |
|---|---|---|
| S-1 | ✅ 완료 | `app/api/deps.py`: mock 토큰 화이트리스트·무효 JWT 자동 승격 제거. `ALLOW_AUTH_BYPASS=1` 명시 설정 + 비운영 환경에서만 우회 허용. 운영+기본 시크릿 조합 시 RuntimeError 기동 거부 |
| S-2 | ✅ 완료 | `web/src/utils/apiAuth.ts` 신설(Supabase 세션 토큰 조립). 하드코딩 토큰 3곳 제거 — `dashboard/page.tsx`, `dashboard/editor/page.tsx`(2건, 탐사 보고 누락분 추가 발견) |
| S-3 | ✅ 완료 | `app/services/payment.py`: 접근 게이트·크레딧 차감 전면 fail-closed(회로 OPEN·DB 예외 시 거부/미실행). 기존 Grace Period e2e 테스트를 fail-closed 기대값으로 갱신 |
| S-4 | ✅ 완료 | 웹훅 서명 ENV 무관 필수화. 서명 없는 Mock 수신은 `PAYMENT_ALLOW_MOCK_WEBHOOK=1` 명시 플래그 + 비운영에서만 허용 |
| S-5 | ✅ 완료 | 미디어 서빙 `_is_safe_path_segment` 화이트리스트 가드 + resolve 컨테인먼트 이중 검증. **주의**: `Path(..).name` 및 resolve 정규화만으로는 `..` 우회 가능함을 실측 확인 → 명시 거부 방식 채택 |
| D-1 | ✅ 완료 | 인보이스 등록번호: 파라미터→환경변수(`JP_INVOICE_REGISTRATION_NUMBER`)→`(未登録)` 순 주입. 체크시트 면허번호 기본값 `"第123456号"` 제거, 공란 시 `(未登録)` 렌더링 |
| L-1 | ✅ 완료 | `compliance/extractor.py`: `resolve_px_to_m()` 신설 — payload 스케일(pixel_to_mm) 자동 수용, 부재 시에만 레거시 0.01 폴백+경고. metrics에 실사용 스케일 기록 |
| L-2 | ✅ 완료 | API·PDF 양측의 가짜「適合」목데이터 폴백 삭제 → `判定不能 (評価データ不在)` 명시. PDF 배지에 判定不能 상태 신설. 평가 예외 삼킴(`pass`) → 로깅 전환 |

**검증 결과**: pytest 105건 중 104 통과 / 6 skip / 1 실패 — 실패 1건(`test_pipeline_e2e.py::test_vector_pdf_pipeline`)은 저장소에 `scratch/` 모듈 자체가 없는 **기존 결함**으로 SP1 무관. 신규 회귀 `tests/test_sp1_security_regression.py` 21건 전부 통과. 프론트 tsc: 수정 파일 오류 0건(기존 supabase*.ts 의존성 미설정 오류 7건은 베이스라인 동일).

**SP1에서 발견된 후속 과제 (SP2 반영 권고)**:
1. `endpoints.py:789-798` 결제 회로 OPEN 시 `circuit_breaker_bypass` 무료 checkout 세션 발급 로직 — 크레딧은 없으나 UX 혼란·남용 여지, 제거 검토.
2. 벡터 PDF 경로의 스케일 캘리브레이션(`ScaleCalibrator`) 연계 — 현재 벡터 페이로드는 스케일 메타가 없어 레거시 폴백(0.01) 사용.
3. `scratch/` 샘플 생성기 부재로 인한 기존 e2e 테스트 1건 영구 실패 — 복구 또는 skip 마킹.
4. `web/` node_modules 미설정으로 tsc/eslint 게이트 자체가 불가 — CI 전 설치 단계 필수.

### SP2 — P1 아키텍처·법규 구조화 (2026-08-26 완료)

| ID | 상태 | 구현 내역 |
|---|---|---|
| A-1 | ✅ 완료 | `harness/circuit_breaker.py` 전면 재작성 — recovery_timeout 실사용, OPEN→HALF-OPEN→CLOSED 상태 전이, HALF-OPEN 시험 실패 시 즉시 재차단+타이머 리셋. 영구 잠금 결함 해소 |
| A-2 | ✅ 완료 | 가짜 스텁 `engine/exporters/export_{ifc,step}.py` **삭제**. 실 ifcopenshell 경로의 얇은 어댑터 `engine/exporters/ifc_worker.py` 신설(SSOT: `parser/export_ifc`). `verify_100_matrix.py` D3.1을 **실경로 생성+ifcopenshell 재파싱**(IfcProject/IfcSpace/IfcWall 개수·IFC4 스키마) 검증으로 교체. worker_pool·security_suite 소비자 재지향 |
| A-3 | ✅ 완료 | RAG 죽은 경로 수정 + **벡터스토어 레포 이관**(구 저장소 `e:/project/...` 13.2MB ChromaDB → `<repo>/vector_store/chromadb`). 기존 테스트가 합격하던 정체가 '옛 저장소 몰래 참조'였음을 실측으로 규명. `test_law_rag.py` 구경로도 수정 |
| A-4 | ✅ 완료 | requirements.txt에 `reportlab`, `stripe`, `google-genai` 추가 |
| A-5 | ✅ 완료 | schema.sql에 `profiles.plan_type/credits/stripe_subscription_id`, `projects.metadata(JSONB)` 반영 + 기존 배포용 멱등 ALTER 마이그레이션 블록. 정적 드리프트 가드 테스트 추가 |
| A-6 | ✅ 완료 | FreeCAD 바이너리 `FREECADCMD_PATH` env 오버라이드, 워커 스크립트 부재 방어, 타임아웃(120s), print→logging |
| L-3 | ✅ 완료 | 규칙이 `facts`(면적·필요면적·비율·층고)를 구조화 반환 → evaluator 경유 → 체크시트가 facts로 계측치 조립. 한국어 reason regex 파싱·substring 소견 선택 제거(rule_id 기반 전환). `import re` 제거 |
| L-4 | ✅ 완료 | `data/laws/manifest.json` 신설(e-Gov XML 판본 고정: 建築基準法 昭和25年法律第201号・施行令 政令第338号). 체크시트 JSON `legal_basis` 필드 + PDF 헤더 「根拠法令」 표기 |
| 후속-1 | ✅ 완료 | 회로 OPEN 시 무료 checkout 발급(`circuit_breaker_bypass`) 제거 → 503 fail-closed |
| 후속-3 | ✅ 완료 | `scratch/` 부재 e2e 테스트 skip 마킹 |

**검증 결과**: pytest **116 통과 / 7 skip / 0 실패** (SP1 대비 +12). `verify_100_matrix.py` 100/100 — 단, D3.1만 실력 기반 확정(나머지 지표의 진위화는 SP4). `test_stage2_geometry_pool.py`·`verify_security_suite.py` 실 IFC 워커로 전량 통과. py_compile 전체 OK.

**SP2에서 발견된 사실 및 후속 과제 (SP3~SP5 반영)**:
1. **RAG 무결성 의문**: 이관된 ChromaDB는 구 저장소 산물로, 현재 repo의 XML 2종과 동일 판본인지 미검증. SP4 매트릭스 v2의 "e-Gov 실코퍼스 적중률" 도입 시 재적재(re-ingest) 권고.
2. 벤치마크 D3.2(뷰어 성능) 하드코딩 10점은 **여전히 남아있음** — SP4 실측 전환 필수.
3. D2.2 RAG 채점은 여전히 자체 3노드 자기검색 — SP4에서 실코퍼스 질의로 교체 필요.

### SP3 — BIM 적산·견적 모듈 신설 (2026-08-26 완료)

계획서 §3 설계 그대로 구현. 수량은 가격과 독립된 물리량으로 산출되며 전 라인이 `source_ref`로 역추적 가능하다(数量取合書 정신).

| ID | 상태 | 구현 내역 |
|---|---|---|
| Q-1a | ✅ 완료 | `takeoff/quantities.py`: 바닥/천장 면적·벽 순연장·벽면적·호실수·개구부 수량 산출. 스케일 SSOT(pixel_to_mm) 수용, 면적 정합성 ±1% 검증 WARN |
| Q-1b | ✅ 완료 | `takeoff/overlap_resolver.py`: 包絡処理 MVP — 중복 세그먼트 제거 + 엔드포인트 공유 시 두께 절반 코너 공제(勝ち負け処理) |
| Q-1c | ✅ 완료 | `pricing/unit_price_book.py` + `data/pricing/unit_prices_jp.json`: 단가 마스터 14품목(解体/仕上/防水/設備/建具), 스키마 검증, **fail-closed**(미지 코드→예외, 0엔 계상 금지), 부위 필터(part_filter: 발코니 방수·UB 방수 등) |
| Q-1d | ✅ 완료 | `pricing/breakdown.py`: 直接工事費→共通仮設費(15%)→工事原価→経費(12%)→消費税(10%)→総工事費 구조 + 工種別 소계 |
| Q-1e | ✅ 완료 | `exporter/quotation_json.py`(数量取合書 호환 원장) + `exporter/quotation_pdf.py`(お見積書 A4, 인보이스 등록번호 env 주입/(未登録)) |
| Q-1f | ✅ 완료 | API 신설: `POST /projects/{id}/quotation`(2크레딧 게이트+차감), `GET /projects/{id}/quotation.pdf`. Pydantic 계약(`app/schemas/quotation.py`) |
| Q-2 | ✅ 완료 | `takeoff/ifc_enrichment.py`: IFC의 IfcSpace/IfcWall에 `Pset_QuantityTakeoff_Kodari` 부착(수량·UnitPriceRef) → ifcopenshell 재파싱으로 조회 확인(roundtrip 테스트) |

**검증 결과**: pytest **125 통과 / 7 skip / 0 실패** (+9). 스모크: 2룸(10m×8m LDK+발코니) → 명산 10품목, 総工事費 ¥3,377,673(税込), PDF 73KB 렌더링. 내역 수학(세율 체인)·부위 필터·包絡処리 수학 정밀 테스트 통과.

**설계 결정 및 후속 과제 (SP4~SP5 반영)**:
1. 수량-단가 분리 설계: 물리량(basis 코드)과 작업항목을 조인하는 구조로, 사업자 단가 교체는 JSON 파일만 교체하면 됨.
2. 包絡処理는 MVP 수준(기둥 관입·슬래브 관통 미고려) — 실무 오차 ±2% 목표, 고도화는 백로그.
3. 견적 크레딧 비용(2)은 `QUOTATION_CREDIT_COST` 상수 — 요금 정책 확정 시 payment.py pricing_map으로 이동 권고.
4. 벤치마크 v2(SP4)에 "견적 E2E" 지표 추가 시 본 모듈의 결정론성을 활용 가능.

### SP4 — 진위 검증형 매트릭스 v2 + 위생 정비 (2026-08-26 완료)

| ID | 상태 | 구현 내역 |
|---|---|---|
| 매트릭스 v2 | ✅ 완료 | `verify_100_matrix.py` 전면 재작성 — 배점 재구조화(D1:20/D2:25/D3:25/D4:15/D5:15), **도메인 60% 미달 시 전체 실패 게이트**, PMO AST 게이트(`harness/bench_integrity.py`)로 무조건 상수 점수 대입 기동 차단 |
| D2.1 | ✅ 완료 | 결정론 규칙 **골든셋 16케이스**(Track A 법해석 6 + Track1 수치공식 10) 일치율 채점 |
| D2.2 | ✅ 완료 | RAG 자기검색 폐지 → 레포 내부 e-Gov 실코퍼스(926청크) 대상 골든셋 Hit@3. 임베딩 회수율 부족 실측(초기 2/10점)으로 인해 **결정론적 렉시컬 하이브리드 검색**(`compliance/rag/corpus_search.py`) 신설 — 캡션 가중 스코어링, 5/5 적중 |
| D3 | ✅ 완료 | 3.1 실 ifcopenshell 재파싱(10) + **3.2 견적 E2E 신설(10)**: 수량→내역 수학검증→数量取合書 필수키→PDF 매직바이트 + **3.3 BIM 라운드트립 성능 실측(5)**: Pset 부착+재파싱 p95<3s |
| D5.2 | ✅ 완료 | fail-closed 결제 게이트·차감·경로순회 가드 실측 채점 |
| H-1 | ✅ 완료 | print→logging **127건 전량 전환**(18파일, 자동 변환기+3회 결함 수정: 함수내 import 삽입·멀티라인 import·이중 들여쓰기). grep 게이트 테스트로 재발 차단 |
| H-2 | ✅ 완료 | bare except/except-pass 전소거(app 계층 AST 게이트 테스트 포함). 폴백 유지+로그 의무화 |
| H-3 | ✅ 완료 | CORS 메서드 화이트리스트(GET/POST/PATCH/OPTIONS), ALLOWED_ORIGINS env 오버라이드 |
| H-4 | ✅ 완료 | `.github/workflows/ci.yml` — 컴파일 게이트→pytest→매트릭스 v2 순차 게이트 (TS 잡은 web 의존성 정리 후 추가) |
| H-5 | ✅ 완료 | `core/units.py` 단일 정의 수렴(extractor·takeoff 전환) + 중복 정의 금지 테스트 |

**검증 결과**: pytest **131 통과 / 7 skip / 0 실패** (+6). 매트릭스 v2 **100/100 — 전 지표 실측 기반 확정**(최초 실행 시 RAG 실력 부족이 92점으로 드러나 검색 엔진을 실제 개선한 후 통과; 이것이 진위 게이트의 작동 증명).

**SP4 설계 결정 및 후속 과제 (SP5 반영)**:
1. **뷰어 FPS 실측은 브라우저 하니스 필요**로 §5 원안에서 대체: 서버 측 BIM 라운드트립 성능(p95)으로 측정. Playwright 기반 FPS 실측은 백로그.
2. RAG 렉시컬 전환은 소규모 코퍼스에 최적 — 코퍼스 확대 시 BM25/임베딩 재도입 평가.
3. CI의 ifcopenshell/chromadb 설치 안정성은 첫 GH Actions 실행에서 확인 필요.

### SP5 — 建築物省エネ法 BEI 규칙 세트 (2026-08-26 완료) — 최종 스프린트

| ID | 상태 | 구현 내역 |
|---|---|---|
| E-1 | ✅ 완료 | `compliance/rules_energy.py` 신설 — BEI 판정 엔진. **공표 수치만 하드코딩하고 출처를 코드·매니페스트에 이중 기록**: 중규모 비주거(300~2000㎡) 2026-04-01 적판분부터 工場等 0.75 / 事務所等·学校等·ホテル等·百貨店等 0.80 / 病院等·飲食店等·集会所等 0.85, 대규모(≥2000㎡)는 2024-04-01부터 동일, 주택·소규모 1.0 |
| E-2 | ✅ 완료 | 규모×용도×적판시점 3축 기준 해석기(`resolve_bei_threshold`) — 경과조치(시행일 전 신청은 종전 기준) 반영 |
| E-3 | ✅ 완료 | 산출 데이터 부재 시 **N/A(判定不能)** 반환 — 가짜「適合」금지 정책(SP1/L-2) 계승 |
| E-4 | ✅ 완료 | 매니페스트에 채에네法 등재(law_id `427AC0000000053`, 平成27年法律第53号) + 확증 노트. 체크시트 JSON/PDF 자동 반영(energy 섹션 존재 시), FAIL 시 종합 판정 不適合 강등 |

**검증 결과**: pytest **147 통과 / 7 skip / 0 실패** (+16). 매트릭스 v2 유지 **100/100**. 임계값 해석 매트릭스(9케이스 경과조치 포함), BEI 경계값(0.80 ≤ 통과), 누락데이터 N/A, 체크시트 E2E 강등 흐름 검증.

---

## 🏁 프로젝트 종결 요약 (SP1~SP5 전량 완수)

| 스프린트 | 핵심 성과 | 테스트 증가 |
|---|---|---|
| SP1 | 인증우회 제거, 결제 fail-closed, 스케일 버그(법규 ~2배 오차) 해소, 문서 위조 폴백 소거 | +21 |
| SP2 | 가짜 IFC 스텁 삭제→실 ifcopenshell SSOT, 회로차단기 회복, RAG 실가동화, 법령 판본 고정 | +12 |
| SP3 | BIM 적산·견적 모듈 신설(takeoff/pricing/quotation, 包絡処理, Pset 부착) — 「견적서 부재」 해소 | +9 |
| SP4 | 벤치마크 진위화(92점 실패→검색엔진 개선→100점), print 127건 소거, CI 게이트 | +6 |
| SP5 | 채에네法 BEI 규칙(2026-04 강화분), 판정 데이터 거버넌스 완성 | +16 |
| **합계** | | **131+16=147통과** (개시 시 91함수 중 다수 미편입 상태에서 시작) |

**남은 백로그 (운영 전환이후 과제)**: 뷰어 FPS Playwright 실측, 包絡処리 고도화(기둥 관입 등), 사업자 단가 주입 UX, RAG 재적재 자동화, web/ TS 의존성 정리 후 프론트 CI 잡.
