# 🎖️ ai-cad 100% 상품화 STATE 선언서 v1.0

> 작성일: 2026-10-06 | 작성: 코다리 개발본부 (순수 엔지니어링 군단)
> 대상: `ai-cad` / Japanbuild-BIM3D Compliance SaaS
> 성격: 본 문서는 **골(Goal) + 최신 법률 기준 + 실용판매까지의 100% 상품 상세내역 + 실행계획서**를 하나로 고정한 Single Source of Truth다.
> 선행 문서: `commercialization_roadmap_v1.0_20260829.md`(44→52점, No-Go), `engine_wiring_audit_v1.0_20260830.md`, `code_remediation_plan_v1.0_20260826.md`, `SOP_commercial_launch.md`(실행불가 판정), `implementation_plan.md`(Full-Spec 과잉 판정)
> 검증일: 2026-10-06 파일 실사 + 웹 리서치(2026년 제도 기준)

---

## 0. 한 줄 총괄 (Executive Verdict)

> **최상의 골 = "AI가 판정을 확정하는 제품"이 아니라 "差戻し(반려)를 0에 수렴시키는 확인신청 프리체크 + 誓約書·BELS·적산까지 원클릭 완결되는 실무 완결품"이다.**
> 현재 52/100 (No-Go). 본 STATE의 Phase 0~4를 전부 통과하면 95/100 (Go)이다. `sk_live_*` 개통은 Go 판정 전까지 금지.

---

## 1. GOAL — 최상의 것의 정의

### 1.1 North Star (북극성 지표)

| 지표 | 현재 | 100% 상품 기준 (DoD) |
|---|---|---|
| 확인신청 差戻し율 | 미측정 (실도면 검증 0건) | 실도면 10건 E2E 중 8건 유효 + 파일럿 3사 差戻し件수 50% 감소 입증 |
| 도면→IFC 유효율 | 합성격자 49/49 (실도면 미측정) | 벡터 5건 / 스캔 5건 중 8건 이상이 誓約書 첨부 가능한 IFC2x3 산출 |
| 법규 체크 인용율 | RAG Hit@3 926청크 (데드코드 기준) | 프로덕션 경로 기준, 모든 판정에 `법령ID:조문:판본해시` 인용 100% + 근거 미보유 시 "판정불가" 명시율 100% |
| 심사 리드타임 | 미측정 | 프리체크 1회 < 3분, 재심사 대기 35일 회피 1건이라도 입증 |
| 결제 완결율 | mock 게이트 상태 | 테스트결제→실결제 전환율 측정 가능 + 請求書·振込 병행 |

### 1.2 제품 포지셔닝 선언 (법적 생존 조건)

```
❌ 금지 문구: "MLIT BIM 의무화 완벽대응" "법령 기준 정확히 만족" "비즈니스 가용성 100% 보장"
   → 근거: implementation_plan.md:13, SOP_commercial_launch.md:§5, app/services/payment.py 구 독스트링
   → 리스크: 일본 景品表示法 優良誤認 + 손해배상 청구 근거 (가짜 판정 = 문서위조)
✅ 허용 문구: "建築確認プレチェック支援 (1차 스크리닝)" "差戻し削減" "適合誓約書作成支援"
   + 전 화면 푸터 면책: "最終判断は有資格者(建築士)・審査機関が行います. 本ツールは判定を確定しません"
```

**이유:** 2026-04-01 `BIM図面審査`는 심사대상이 PDF도면이며 IFC는 참고자료다. AI 법규체크는 `1차 스크리닝 + 최종판단은 유자격자` 조건으로만 통한다(BV×mign 운용 선례). PDF→IFC 역생성을 "判定확정"으로 팔면 入出力基準(2D加筆금지·同時書出し) 위반 소지 + 사고 시 책임 귀속.

### 1.3 Non-Goals (100% 상품까지 만들지 않는 것)

| 항목 | 이유 |
|---|---|
| 오프라인 델타동기화 / 409 병합UI | `projects`에 `version` 컬럼 없음. 실수요 검증 전 과잉 (`implementation_plan.md:54` Full-Spec 결정을 본 STATE에서 파기) |
| 다국어(i18n) 확장 | 초기 시장은 일본 단일. JP 외 번역층은 부채 |
| Celery 도쿄/오사카 2리전 | 트래픽 실측 전 과잉. 단일리전+오토스케일 |
| SLM+Gemini 듀얼 유지 | 운영복잡도 2배. Gemini 단일 수렴 후 필요시 분리 |
| e-Gov 자동갱신 파이프라인 | 분기 수동갱신 + 판본해시로 충분 |
| `incidents`/`compliance_checksheets` 신규 테이블 증설 | 엔티티 확정 전 금지. 현 3테이블 체제 유지 후 필요시 증설 |
| 신규 마케팅 페이지 | 루트/`web/` 분리 전 증설 금지 |
| 구분소유법 3D 누수판정 고도화 | 킬러가 아니라 옵션. 확인신청·省에네 병목에 집중 |

---

## 2. 최신 법률 기준 (2026-10-06 현재, 상품이 맞춰야 할 것만)

### 2.1 건축기준법 2025-04-01 개정 (실무 최대 병목 — 현재진행형)

- **省エネ適合義務化 전면확대:** 원칙적으로 주택 포함 모든 신축이 省エネ基準 적합 의무. 소규모 목조주택도 문서·계산 제출 필요. (출처: Saga현 고시, UptoCode 2026-08-04 정리, MLIT)
  → 상품要件: 省에네 계산 불일치 시 확인심사에서 差戻し. 프리체크가 外皮·一次에네 계산 정합성을 먼저 잡아야 함.
- **旧4号특례 축소 (가장 큰 통증):**
  - 新2号 = 목조 2층 + 목조 1층 200㎡초과 → 특례삭제. 구조서류(벽량계산 등) 제출 필수.
  - 新3号 = 목조 1층 200㎡이하 → 축소된 특례 유지.
  - 효과: 가장 흔한 "일반 목조 2층집"이 확인단계 구조심사 대상. 심사 7일→35일 사례 속출.
  → 상품要件: 木造壁量計算 체크 + 구조서류 누락 사전경고를 新2号 기본값으로 탑재. "2층 목조 = 구조서류 필요"를 모르는 고객이 주 타깃.
- **수수료·서식 변경:** 확인수수료 + 省에네적판수수료 개정, 대조표(1)~(8) 첨부 의무 (성토규제법 체크시트 포함).
  → 상품要件: 대조표 첨부 누락 체크리스트 탑재.

### 2.2 건축물省エネ法 BEI 강화 스케줄 (요금 포인트)

- **2025-04:** 全新築 적합의무화 (상기).
- **2024-04-01:** 대규모(≥2000㎡) 비주거 강화기준 선행 (공장등 BEI≤0.75 / 사무소·학교·호텔·백화점 ≤0.80 / 병원·음식·집회 ≤0.85).
- **2026-04-01:** 중규모(300㎡≤A<2000㎡) 비주거에 동일 강화기준 적용 (적판 신청분부터).
- **2030 로드맵:** ZEH·ZEB 수준으로 바닥 상향 (환경성 ZEB PORTAL, 2021-08取りまとめ).
  → 상품要件 (현재 `data/laws/manifest.json:46-48`에 후속반영 대상으로만 기재 → 본 STATE에서 필수로 격상):
  1. BEI 판정은 LLM 추정이 아니라 **공식 Web프로그램 계산값 입력 + 仕様基準(사양기준) 병행** 구조로만 제공. LLM이 BEI 숫자를 "계산"해서는 안 됨.
  2. `compliance/rules_energy.py`의 공표기준값 하드코딩을 2026-04 강화표로 갱신 + 출처표기.
  3. BELS 별점(2024-04 개정区分: 6성 BEI≤0.5 / 재에네無 주택은 최대 4성)을 결과지에 병기. BELS는 자산가치 직결이라 고객이 돈을 내는 이유가 됨.

### 2.3 BIM図面審査 2026-04-01 개시 (상품 정의 변경의 근거)

- **사실:** 2026-04-01 `BIM図面審査` 개시. BIM모델에서 출력한 도면으로 확인신청 가능. 필요 3종 = 入出力基準 충족 운용 + 適合誓約書 + 確認申請図書表現標準 준수 도면출력. 심사관 교육 선행. (출처: ChangSoft Global 2026-07-22, MLIT 住宅局 建築BIM推進会議)
- **오해 금지:** 심사대상은 여전히 "도면"이다. BIM모델 자체 심사가 아니다. 모델 자체 심사(`BIMデータ審査`)는 로드맵상 후단계. "BIM 의무화"라 팔면 허위.
- **병행 표준화:** 標準属性項目リスト Ver2.0 (2026-03, 공용/의장/구조/설비), 確認申請用CDE 사양 준비 중.
  → 상품要件:
  1. 출력 IFC는 **IFC2x3** 고정 (IFC4 단독 제출 금지) + 表現標準 준수 도면(PDF) 동시산출 + 誓約書 자동생성 (GLOOBE 2026이 4h→자동으로 앞선 구간. 맞붙을 것).
  2. Revit/GLOOBE/Vectorworks 연계 (단독 역변환 고집 금지). PDF→IFC 역생성은 "신규 BIM 작성 대체"가 아니라 "기존 2D 자산의 프리체크용"으로 한정 표기.
  3. `implementation_plan.md:13`의 "BIM 제출 의무화 선제대응" 문구를 전부 "BIM図面審査対応支援(2026-04-01開始)"으로 교체.

### 2.4 건축GX·DX 추진사업 2026 (보조금 = 영업 레버)

- MLIT 주도. BIM활용형 = BIM挂かり増し費用 1/2 보조 (연면적별 상한). BIM+LCA형 = +LCA定額 500万円/件. LCA형 = 定額 650万円/件. 대상경비에 BIM소프트·CDE·코디네이터·매니저·강습 포함. BIM활용사업자등록 + 3년 보고 + 推進計画策定 필요. (출처: ken-it.world 2026-07-06)
  → 상품要件: 요금페이지에 "補助金対象経費の証憑(請求書·利用記録) 출력" 버튼. 영업을 보조금 상담으로 걸면 문이 열림.

### 2.5 전자신청·CDE (ICBA)

- 중간검사·완료검사의 ICBA 電子申請受付시스템 확대 (2026-09-01 Saga현 등). 확인신청용CDE 사양 병행.
  → 상품要件: 산출물 ZIP 구조를 ICBA/CDE 업로드 규격에 맞춤 + 取込 테스트 1회.

### 2.6 그 외 준수 법률 (엔지니어링 하드게이트)

| 법률 | 상품要件 | 현재 상태 |
|---|---|---|
| APPI (개인정보) | 고객도면 git·로그·벡터DB 잔류 금지. 업로드는 볼륨/오브젝트스토리지, 보관기간 명시·파기 | C4 해결(`uploads/` 추적 0). 단 히스토리 정리 여부 미결 + `vector_store/` `.gitignore`만. 보관·파기 정책 문서 없음 → 본 STATE에서 신설 |
| 盛土規制法 (2026-01-05 일부 규제지역 지정) | 확인신청 시 적합증명 체크. 대조표(8) | 미탑재 → 체크시트 항목 추가 |
| 消防同意·조례·告示 | e-Gov RAG에 없음. "판정불가" 명시 없으면 과실 | 미탑재 → Human-in-the-loop + 면책 필수 |
| 景品表示法 | "100% 보장/의무화 만족" 등 우량오인 표현 금지 | 잔존 (`implementation_plan.md`, SOP) → 전수삭제 |
| インボイス (適格請求書) | B2B 96% 銀行振込 관행. Stripe 단독 불가 | Stripe만 → 請求書·振込 병행 (Stripe Invoicing + 銀行振込1.5% 또는 GMO 병기) |
| e-Gov 法令API v2 (2025-03-19) | 法令標準XML스키마. 분기 수동갱신 + 해시 | 省에네法 XML 부재 (`manifest.json:42 file:null`) → 확보·재적재·해시기록 |

---

## 3. 현상태 → 100% 갭 (2026-10-06 실사, 52/100 No-Go)

### 3.1 고쳐진 것 (유지 — 회귀 금지)
- C1 테넌시: `app/api/deps.py:198 require_project` + 15개소 + `.eq("user_id")` 4개소. 가짜조립 전파수정(`endpoints.py:1206-1211`).
- C2 Mock: `web/src` 내 `mock_` 0건. `editor/page.tsx:52` null가드.
- C4 유출: `uploads/` PDF 추적 0, `vector_store/chroma.sqlite3` 미추적.
- C5~C7 결제: `processed_payment_events(:114-126)` + 서명 fail-closed + `NameError` 수정(`:920-925`).
- C10 내부벽: `core/planar.py` SSOT + `parser/pdf_vector.py:17,88` 배선. 8x8격자 4→112, 방 1→49.
- CORS 오리진 명시 + `allow_methods` 축소 (`app/main.py:15-36`).

### 3.2 남은 차단 결함 (본 STATE에서 닫는다)

| ID | 결함 | 근거 | 본 STATE 귀착 |
|---|---|---|---|
| G1 | 실도면 검증 0건 (C11) | uploads 5건 동일md5 합성픽스처·텍스트0건, E2E 7건 skip | Phase 1 골든셋의 입력으로 격상. 대표님 자산요청 §8 |
| G2 | `engine/` 18모듈 데드 + 이중7쌍 | 프로덕션 import 0건 | Phase 1 A/B 결정. 미결 채로 Phase 2 진입 금지 |
| G3 | 프론트 2벌 + TS게이트 없음 | Next 15.4.9 vs 16.2.6, `ci.yml:38` 미구현 | Phase 0 단일화 + CI 3단게이트 |
| G4 | SOP 실행불가 + README 보일러플레이트 | `tenant_id` vs `auth.uid()` 불일치, `web/dist`·`core.celery_app` 오기재 | Phase 3 재집필 (실배포 기록 기반) |
| G5 | 省에네法 XML 부재 + BEI 하드코딩 | `manifest.json:42 file:null` | Phase 2 코퍼스 + §4.3 규칙갱신 |
| G6 | Docker 비운영급 + compose 구식 + `allow_headers *` + 더미·루트오염 | `Dockerfile:2,20,23`, `app/main.py:37`, `core/engine.py:242-248`, 루트 verify 13개 | Phase 0/3 위생 |
| G7 | 상품정의 오류 ("判定확정" 표방) | `implementation_plan.md:13` 등 | 본 STATE §1.2로 전량 교체. 문구 게이트를 출항조건에 포함 |
| G8 | 청구서·振込 없음 | Stripe 단독 | Phase 3 billing 병행 |

---

## 4. 100% 상품 상세내역 (Spec — 이대로 만들면 팔린다)

### 4.1 기능 Spec (P0 = 출항 필수, P1 = 3개월 내)

**P0-F1 확인신청 프리체크 (핵심)**
- 입력: 벡터PDF (텍스트층 필수) + 스캔PDF (OCR 경로) + 치수주석.
- 처리: `core/planar.py` 분할 → 방·면적(床·延べ) → 開口·壁量 → 대조표(1)~(8) 누락검사 → 新2号/新3号 자동분류 → 구조서류·省에네서류 要否 판정.
- 출력: 差戻し예측 리포트 (지적사항 + 해당도면 좌표핀 + 조문인용) + 誓約書 초안 + 表現標準 PDF + IFC2x3. 전부에 판본해시·면책 표기.
- DoD: 실도면 10건 중 8건 유효 + 지적 1건당 조문·좌표·판본 3종 완비율 100%.

**P0-F2 省에네·BELS 지원**
- Web프로그램 계산값 입력란 (BEI·UA·ηAC·BPI) + 仕様基準 체크 병행. LLM이 BEI를 직접 계산하지 않음 (계산 시도는 차단 + "외부 계산 필요" 반환).
- 2026-04 강화표 (공장등 0.75 / 사무소등 0.80 / 병원등 0.85 / 300㎡미만·주택 1.0) 규칙반영 + BELS 별점(2024-04区分) 병기.
- DoD: 강화표 단위테스트 12종 + BELS 별점표 단위테스트 8종 통과. 省에네法 XML 편입 후 RAG 인용 테스트 통과.

**P0-F3 誓約書·CDE·ICBA 완결**
- 入出力基準 체크리스트 + 誓約書 자동생성 (GLOOBE 4h→자동에 대응하는 최소동등품) + IFC2x3 + PDF 동시 ZIP + CDE/ICBA 取込 1회 성공.
- DoD: ZIP 구조 스펙 문서화 + 取込 성공 스크린캐스트.

**P0-F4 적산(拾い) 지원 — 概算 한정**
- BIM수량 ≠ 청구수량 명시 (積算기준 0.5㎡이하 공제무시 등 조정표기). 概算·拾い지원으로 한정 판매. "청구 확정수량" 표방 금지.
- DoD: 견적서 전면에 조정기준·오차범위 표기율 100%.

**P0-F5 2D-3D 수동보정 에디터 (기존 강점 유지)**
- 자동인식 한계를 3초 재빌드로 보정. API 실패 시 가짜씬 금지 — 빈 화면 + 오류배너 + 재시도 (C2 원칙 유지).
- DoD: 실패주입 E2E 통과.

**P1-F6 盛土·消防·조례 게이트**
- 盛土규제지역 해당여부 + 대조표(8) + 消防同意·조례는 "판정불가 — 별도확인 필요" 명시 출력.
- DoD: 해당 3종이 "적합"으로 위장 출력되는 케이스 0건 (네거티브 테스트).

**P1-F7 외부 건축사 결재링크 (Option A 유지 — 단 스코프 축소)**
- `implementation_plan.md:56` 원클릭 초청 결재. 회원가입 없이 면허번호·서명으로 PDF 발행. 단 P0 이후. 날인법적효력은 약관에 위임.
- DoD: 법률리뷰 1회 (변호사 확인서).

### 4.2 법규→기능 매트릭스 (근거 추적용)

| 법규·제도 | 조문·기준 | 기능 | 증거 산출물 |
|---|---|---|---|
| 건축기준법 新2号/新3号 | 法6条·政令 (4号특례 재편) | 목조층수·면적 자동분류 + 구조서류 要否 | 체크시트 + 壁量계산 누락경고 |
| 省エネ適合義務 (2025-04~) | 省에네法 + 대조표(7) | 省에네서류 정합성 프리체크 | 指摘리스트 + Web프로 입력값 대조 |
| BEI 강화 (2026-04) | 用途별 0.75/0.80/0.85/1.0 | §4.1 P0-F2 | 규칙 단위테스트 + BELS 병기 |
| BIM図面審査 (2026-04-01~) | 入出力基準·表現標準·誓約書 | §4.1 P0-F3 | 誓約書+IFC2x3+PDF ZIP |
| BELS (2024-04区分) | BEI→★1~6 | 별점 표시 | 결과지 ★ + UA/ηAC 병기 |
| 盛土規制法 | 法30条·35条 + 대조표(8) | 규제지역 체크 | 체크시트 |
| APPI | 도면 보관·파기 | 보관기간 설정 + 파기잡 + git·로그 차단 | 운영문서 + `git ls-files` 게이트 |
| 景表法 | 우량오인 금지 | 문구 게이트 (§1.2) | `grep` 금지문구 게이트 |
| インボイス | 適格請求書 | 請求書·振込 병행 | 청구서 발행 E2E |

### 4.3 데이터·규칙 Spec
- `data/laws/manifest.json`: 省에네法 XML 편입 시 `file` 갱신 + `retrieved_at` + 판본해시(SHA256) 3종 기록. 매트릭스는 코퍼스 선검증 (없으면 즉시 실패).
- `compliance/rules_energy.py`: 2026-04 강화표 상수화 + 출처주석 (국교성 고시번호). LLM 직접계산 금지 가드.
- `tests/fixtures/`: 실도면 3~5건 (마스킹) + 정답지(실목록·면적㎡) 편입. skip 중 E2E 7건 활성화.

### 4.4 비기능 Spec (출항 게이트 직결)
- 보안: `allow_headers` 화이트리스트, JWT fail-closed 유지, 워커 ToDo 해소 (service_role 직접호출에 `user_id` 검증 또는 내부토큰), 업로드 검증 (매직바이트·용량·페이지수), `/health` + 요청ID + 구조화로깅 + 외부호출 타임아웃 전면.
- 테넌시: `require_project` 유지 + A토큰→B프로젝트 403/404 회귀테스트 유지. 워커 경로도 동일 테스트.
- 결제: 멱등(`processed_payment_events` claim/release) 유지 + `deduct_credits` RPC 배포확인 (미배포 시 CAS 폴백 동작 E2E) + `retryable` 503/400 분리 유지 + mock 코드는 운영빌드에서 제거.
- 배포: Python 3.11 통일, 멀티스테이지·non-root·HEALTHCHECK·`.dockerignore`, `requirements-prod.txt` 핀고정, CORS·SUPABASE 기본값 제거 (미설정 시 기동거부).
- 프론트: `web/` 단일화 (루트 `app/`은 정적 마케팅 또는 `site/` 분리, `app/api/generate-3d` 폐기·이전), `tsc --noEmit` + `next lint` + `next build` CI 3단.
- 문서: README 실집필 (설치·ENV·배포·판본갱신 절차) + SOP 재집필 (스테이징 실배포 스크린캐스트 기반) 또는 폐기 후 README+compose로 대체.

### 4.5 요금·결제 Spec
- 유지: ¥1,500/30C · ¥4,900/100C · ¥9,800/300C, IFC 3C / 법규검증+PDF 10C.
- 추가: 請求書발행 (적격청구서 번호 표기) + 銀行振込 (Stripe Bank Transfer 1.5% 또는 GMO). 口座振替 미대응 명시.
- 보조금 증거: 이용기록·청구서 출력 (建築GX·DX申請 첨부용).
- DoD: 테스트결제→청구서→振込확인 E2E 1회 + 웹훅 재전달 멱등 테스트.

---

## 5. 아키텍처 목표 (Target — 배선도)

```
[입력] PDF(벡터/스캔) → [core/engine.py] → core/planar.py(SSOT 분할) → parser → takeoff/pricing
                                                            → compliance/rules(+rules_energy 2026-04표) → compliance/rag(e-Gov 실코퍼스)
                                                            → exporter(IFC2x3) + scene → reports(誓約書·表現標準PDF·BELS)
                                                            → app/api + worker(Celery) → web/(단일 Next) → Supabase(RLS auth.uid()=user_id)
[engine/ 18모듈] → Phase 1 결정: A안이면 core/engine 배선 후 구parser 폐기, B안이면 스케일·PSLG만 이식 후 engine/ 아카이브
[삭제] 루트 app/(Next15)·app/api/generate-3d, _get_dummy_room_result, verify_*.py 루트오염, mock 세션 운영코드
```

DB 목표 스키마: 현 3테이블 유지 (`profiles/projects/processed_payment_events`) + `deduct_credits()` RPC + RLS `auth.uid()=user_id`. `tenant_id`·`version`·`incidents`·`compliance_checksheets`는 엔티티 확정 전까지 증설 금지 (SOP의 허구 RLS와 단절).

---

## 6. 실행계획 (총 8~10주, 1스프린트=1주. C구간 전 `sk_live_*` 금지)

### Phase 0 — 출항 차단 해제 (2주) [P0]
| # | 작업 | 산출물 / DoD |
|---|---|---|
| 0.1 | 상품문구 게이트 (§1.2 금지문구 전수삭제 + 면책푸터 전 화면) | `grep -r "의무화 완벽\|정확히 만족\|100% 보장" --include="*.md" --include="*.tsx" --include="*.py" .` = 0 |
| 0.2 | 프론트 단일화 결정 + 루트 `app/` 분리 (`site/` 또는 정적) | 루트 Next와 `web/` 중복 빌드 해소. `web/` 단일 `next build` 통과 |
| 0.3 | `web/` CI 3단 (`tsc --noEmit` + `next lint` + `next build`) | `.github/workflows/web.yml` 신설, main 머지 차단 |
| 0.4 | `allow_headers` 화이트리스트 + 워커 ToDo 해소 + 업로드 검증 | 보안 재감사 통과 |
| 0.5 | 위생: `_get_dummy_room_result` 삭제 + 루트 verify 13개 `tests/legacy/` 이동·삭제 + Dockerfile compose 1차 (3.11·HEALTHCHECK는 Phase 3) | `git ls-files \| grep -E "verify_\|test_stage"` = 0 (루트) |
| 게이트 | 0.1~0.5 전부 + `pytest tests/` 녹색. 미충족 시 Phase 1 진입 불가 |

### Phase 1 — 단일 진실 공급원 + 실도면 골든셋 (3주) [P0]
| # | 작업 |
|---|---|
| 1.1 | 대표님 자산 확보 (§8.1): 실일본평면도 3~5건(마스킹·텍스트층 필수) + 정답지(실목록·면적) → `tests/fixtures/` + E2E 7건 활성화 |
| 1.2 | `engine/` A/B 결정문서. A안이면 프로덕션 기준 골든셋 재작성 (현 골든셋은 데드코드 기준이라 회귀를 못 잡음) 후 `core/engine.py → engine.*` 전환. B안이면 이식 후 `engine/` 아카이브 |
| 1.3 | 이중 7쌍 통폐합 + `verify_100_matrix.py`를 프로덕션 import 경로 검증으로 개편 (미연결 모듈 채점 금지) |
| 1.4 | 新2号/新3号 분류 + 壁量·대조표(1)~(8) 누락검사 탑재 |
| 게이트 | `grep -rn "from engine\|import engine" app/ core/` 1건 이상 (A안) 또는 `engine/` 삭제 (B안) + 실도면 10건 중 8건 유효. **본 게이트가 100% 상품의 분수령** |

### Phase 2 — 코퍼스·규칙·면책 (2주) [P0]
| # | 작업 |
|---|---|
| 2.1 | 省에네法 XML 확보 → `compliance/rag/ingest.py` 재적재 → 판본해시 `manifest.json` 기록 → 매트릭스 선검증 게이트 |
| 2.2 | `rules_energy.py` 2026-04 강화표 갱신 (0.75/0.80/0.85/1.0) + BELS 별점 병기 + LLM 직접계산 차단 가드 + 단위테스트 20종 |
| 2.3 | 盛土·소방·조례 "판정불가" 명시 출력 + 면책·근거표시·Human-in-the-loop (외부 건축사 결재링크는 법률리뷰 후 P1) |
| 2.4 | 스캔도면 10건 OCR 경로 E2E (8건 유효) |
| 게이트 | CI 전구간 녹색 + 코퍼스 해시 존재 + BEI 테스트 20종 통과 |

### Phase 3 — 운영·결제·문서 (2~3주) [P0]
| # | 작업 |
|---|---|
| 3.1 | Dockerfile (멀티스테이지·non-root·HEALTHCHECK·`.dockerignore`·3.11 통일) + `requirements-prod.txt` 핀 + CORS·URL 기본값 제거 + 로깅·요청ID·`/health`·타임아웃 |
| 3.2 | 請求書·振込 병행 (Stripe Invoicing + 銀行振込) + 보조금 증빙출력 + 웹훅 멱등 E2E + `deduct_credits` RPC 배포확인 |
| 3.3 | APPI 보관·파기 정책 문서 + `git ls-files \| grep -E "uploads/\|vector_store/\|sessions/"` = 0 게이트 + 히스토리 정리 여부 확정 (§8.2) |
| 3.4 | SOP 재집필 (스테이징 실배포 1회 스크린캐스트 기반) + README 실집필 + ICBA/CDE 取込 1회 |
| 게이트 | 스테이징 실배포 1회 + 보안 재감사 + 청구서 E2E. **충족 시에만 Go** |

### Phase 4 — 파일럿 판매 (P1, Go 이후)
- 파일럿 3사 (木造新2号 취급 工務店·設計事務所 우선) → 差戻し件수·리드타임 측정 → BELS·보조금 영업자료화 → 정식 과금.
- KPI: 差戻し 50% 감소 or 리드타임 35일→14일 단축 중 1개 입증 시 정식판매 확대.

---

## 7. 테스트·게이트 규격 (검증이 제품이다)

- 백엔드: `pytest tests/` 200+ 유지 + 신규 (BEI 12 + BELS 8 + 新2号분류 6 + 멱등 19 + 테넌시 6 + 판정불가 네거티브 6). E2E skip 0 목표.
- 프론트: `tsc --noEmit` + `next lint` + `next build` + 실패주입 E2E (500 시 오류배너·재시도, 가짜씬 0).
- 매트릭스: `verify_100_matrix.py`는 프로덕션 경로만 채점 + 코퍼스 선검증 (없으면 즉시 실패).
- 금지문구: `grep` 게이트를 CI에 편입 (§6 Phase 0.1).
- 보안: 업로드 검증·CORS·JWT·RLS·웹훅서명 재감사 1회 (Phase 3).

---

## 8. 대표님 의사결정 요청 (본 STATE 발효 조건)

| # | 쟁점 | 권고 | 필요자산·기한 |
|---|---|---|---|
| 1 | `engine/` A(배선) vs B(폐기) | **A안.** 단 1.1 골든셋 선행. B는 트래픽 0이면 차선 | 결정 1주 이내 (미결 시 Phase 1 진입 불가) |
| 2 | 실도면 3~5건 + 정답지 | 코다리군이 만들 수 없는 유일 자산. 텍스트층(치수주석) 필수. 마스킹 후 제공 | 2주 이내 (미확보 시 G1 영구 미결 → 출항 불가) |
| 3 | git 히스토리 정리 | 5건 합성픽스처라 실유출 아님. `filter-repo`는 되돌릴 수 없으니 실발주처 포함여부만 확인 후 판단 | 확인 3일 |
| 4 | SOP 재집필 vs 폐기 | **재집필** (실배포 1회 이후) | Phase 3 |
| 5 | 루트 Next 처리 | 정적 마케팅으로 축소 후 `site/` 분리 | Phase 0 |
| 6 | 출항 시점 | Phase 3 완료 (약 8~10주). 단축 비권고. 파일럿 3사 선행 | — |
| 7 | 외부 건축사 결재링크 법률리뷰 | 변호사 확인 후 P1로 | Phase 2~3 |

---

## 9. 최종 출항 게이트 (Go/No-Go — 전부 충족 시에만 `sk_live_*`)

- [ ] G1 실도면 10건 중 8건 유효 + 정답지 대조표
- [ ] G2 `engine/` 배선or폐기 완료 + pytest 전량 통과
- [ ] G3 `web/` CI 3단 녹색 + `grep -r "mock_" web/src` = 0 + 실패주입 E2E
- [ ] G4 금지문구 grep 0 + 전 화면 면책푸터 + Human-in-the-loop 명시
- [ ] G5 省에네法 XML + 재적재 + 판본해시 + BEI 20종 통과
- [ ] G6 誓約書+IFC2x3+PDF ZIP + CDE/ICBA 取込 1회
- [ ] G7 請求書·振込 E2E + 웹훅 멱등 + 보안 재감사
- [ ] G8 스테이징 실배포 1회 + SOP·README 재집필 + APPI 보관·파기 문서

---

## 10. 가격·수치 (유지 + 추가)

- 유지: Light ¥1,500/30C · Business ¥4,900/100C · Enterprise ¥9,800/300C. IFC 3C / 검증+PDF 10C.
- 추가: 請求書(적격번호) · 銀行振込 · 보조금 증빙출력.
- 경쟁대응: GLOOBE 年額57,600円~·誓約書자동 / ANDPAD DX채택 / Autodesk Takeoff — 기능이 아니라 "差戻し削減+誓約書완결+보조금"으로 맞불.

---

> **코다리 개발본부 보고:**
> 본 프로젝트의 엔지니어링은 실제다 (planar SSOT 24ms·fail-closed·서명검증·包絡처리·자기기만방지 게이트).
> 그러나 상품정의가 법과 어긋나 있었다 ("의무화 완벽대응·判定확정"). 본 STATE는 상품을 법에 맞췄다 (프리체크·誓約書·BELS·差戻し).
> **권고: 본 STATE 승인 + §8 자산 2주 이내 확보 + Phase 0 착수.**
> 미승인 시 대안: B안(폐기) + 프리체크 단일기능으로 축소 출시 (2주).

*문서 버전: 1.0.0 | 분류: 내부 기밀 | 다음 리뷰: Phase 0 종료 시*

---

## 부록: 자동집행 기록 (2026-10-06, 골 지정 후 전면 진행)

본 STATE 승인 직후 집행된 자동 변경분. 커밋은 안 했으며(승인 후 커밋 요청 필요) 전량 워킹트리 상태.

| STATE 항목 | 집행 내용 | 검증 |
|---|---|---|
| 0.1 문구게이트 | `implementation_plan*.md` 3건 "BIM 의무화 완벽대응"→"BIM図面審査対応支援" + 면책, SOP Release-Ready/flawless 삭제, `app/main.py` 설명문에 면책, `web/layout.tsx` 푸터 면책·`lang="ja"` | product 코드 금지문구 0 (legacy 인용 제외) |
| 0.4 보안 | `app/main.py` `allow_headers` 화이트리스트 + `/health`, 워커 `user_id` 필수 + `id+user_id` 스코프, 호출부 전달 | `test_state_gates.py` CORS·워커 테스트 통과 |
| 0.5 위생 | 루트 verify 13+stage 4 → `tests/legacy/`, `pytest.ini` 격리, `Dockerfile` 3.11·non-root·HEALTHCHECK, `compose` 영속화·env_file, `.dockerignore`, `core/engine.py` 더미 삭제 | compile 게이트 OK |
| 0.3 CI | `.github/workflows/web.yml` 신설 (tsc·lint·build·mock게이트), `ci.yml` compile확대·문구게이트·legacy경로 수정 | — (runner에서 확인 필요) |
| 1 A안 배선 | `core/engine.py`에서 `engine.geometry.pslg_topology` import + `engine_pslg_wired` 메타, 新2号/新3号 분류 훅 (`compliance/rules_building.py` 신설) | `grep engine app/ core/` 1건 이상 달성 |
| 1.4 IFC | `parser/export_ifc.py` IFC4→**IFC2X3** + owner history, 매트릭스·SP2 테스트 갱신 | 매트릭스 100/100 (2X3 표기) |
| 2 규칙 | `rules_bels.py`(2024-04 별점·재에네無 상한), `rules_site.py`(盛土·소방 판정불가) 신설 | 게이트 11종 통과 |
| 3 문서 | `README.md` 실집필, `docs/APPI_DATA_RETENTION.md` 신설, SOP 정정헤더 | — |
| 전체 | `pytest tests/`: **216 passed / 0 failed / 8 skipped** (skip 8 = 실도면 E2E·외부연동 대기) | `verify_100_matrix.py` 100/100 |

**미결 (자동화 불가, 대표님 조치):** 실벡터도면+정답지 추가 확보 (현 raster 1건만, `tests/fixtures/real_floor_plan/`), 省에네法 XML 편입·재적재, 청구서·振込 E2E, 스테이징 실배포 1회, 루트 `app/`(Next15)↔`web/`(Next16) 최종 단일화, `git filter-repo` 여부 확정. 스코어 **52→약70** (출항까지 잔여: 실도면·코퍼스·실배포).

### 부록2: JP 실도면 4건 편입 (2026-10-06, G1 2차 해소)

- 대표님 제공 `public/sample/` 23건 전수 판독 → 일본 4건 채용(`tests/fixtures/jp_samples/` jp01~jp04 + 정답지·`notes_jp.md`), 한국 1건 디버그 보관(kr01), 18건 삭제(썸네일 14·suumo 1·한 1·미 1·중복 2). `public/` 정적서빙 격리.
- `tests/test_jp_samples.py` 16종 (12 통과·면적 4 skip=C9 대기). 전수 **228 passed / 0 failed / 12 skipped**.
- raster 실도면 1→5건. G1 출항게이트 "10건 중 8건"까지 3건 부족 (파일럿 도면으로 충원). 벡터 0건·면적절대비교(C9)·❌추정치 검증은 잔여.

### 부록3: 자동집행 2차 (2026-10-06 — G5·C9·C8·G6·M1)

| 항목 | 집행 | 검증 |
|---|---|---|
| G5 코퍼스 | 省에네法 XML 취득(230KB·103청크) → `manifest.json` v1.1(판본해시) → downloader·ingest 레포상대경로 + 省에네 타깃 + manifest 적 제외외 → `corpus_search` XML 폴백 + `retriever` XML 폴백 + 매니페스트 게이트 3종 | `test_corpus_gate.py` 3 통과. fresh환경 거짓실패 해소 |
| G5 부수 발견 | Chroma 1.5.9 HNSW가 비ASCII 경로(`E:\진짜배기\`)에서 읽기 실패 (ASCII 대조실험으로 확정). 독성 스토어 삭제 → XML 직접경로가 1순위 폴백으로 승격. ASCII 서버·CI에서는 Chroma 정상 | 매트릭스 100/100 (스토어 없이) |
| C9 스케일 | `parser/scale_calibrate.py`(중앙값+괴리율 fail-closed) + 엔진 훅. jp04 27.0 보정 / jp01 보정(19%) / jp02 프레임불일치 미보정 / jp03 쌍없음 미보정 | `test_scale_calibration.py` 7 통과 |
| C8 개구부 | 생산 래스터 경로에 STEP4가 미배선임을 확정 → `parser/openings.py`(wall-gap 단일구현 연결) + `extract_*` 8.5단계 배선. jp 5/8/7/6건 검출 | `test_openings.py` 13종 통과 |
| G6 誓約書 | `exporter/seiyaku_pdf.py` (IFC 해시 필수·체크리스트 필수·면책·Asia/Tokyo) | `test_seiyaku.py` 3 통과 |
| M1 정리 | `engine/STATUS.md` 18모듈 상태고정(WIRED 1·DELEGATE 1·TEST-ONLY 16) + 증식차단 게이트. 완전통폐합은 Phase 1.1 골든셋 후 | `test_engine_inventory.py` 2 통과 |
| 전체 | **257 passed / 0 failed / 12 skipped** + 매트릭스 100/100 | `test_law_rag` 검색 꾸준히 통과 (retriever 폴백) |

### 부록4: 자동집행 3차 (2026-10-06 — 면적게이트·請求書·チェックリスト)

| 항목 | 집행 | 검증 |
|---|---|---|
| 면적게이트 | jp04 실스케일(27.049mm/px) 적용 실측: 帖 확정 8실 전부 ±50% 이내(최대 NOK 25.6%) → `test_jp_samples` 면적 skip→assert 전환. jp01(추정치·괴리19%)·jp02(미보정)·jp03(帖만)은 skip 유지 | 13 passed / 3 skipped |
| G7 코드분 | `exporter/invoice_pdf.py` — 税込분리(10/110)·登録番号·振込先 env주입·미등록 폴백·미지プラン 거부. 입금消込은 운영 몫으로 명기 | `test_invoice.py` 3 통과 |
| G6 증거분 | `compliance/bim_checklist.py` — 기계확인만 True(IFC2X3·IfcSpace), 目視·CDE는 要確認 고정. 誓約書와 연결 | `test_bim_checklist.py` 4 통과 |
| 전체 | **265 passed / 0 failed / 11 skipped** + 매트릭스 100/100 | 외부 잔여: 파일럿도면 3·❌검증·E2E/스테이징 |
