# `engine/` 배선(A안) 정밀 감사 및 판정

*작성: 2026-08-30 | 분류: 내부 기밀 | 근거: 코다리 개발 군단 CTO/QA/보안 합동*
*대상: `engine/` 18모듈 1,677 LOC (프로덕션 import 0건)*

---

## 0. 결론 (한 줄)

> **`engine/`은 "연결만 안 된 더 좋은 코드"가 아니다. 심볼 교집합이 0인 별개의 두 번째 구현이며,
> 배선 가능한 모듈은 18개 중 5개뿐이다. 나머지는 입력 데이터 파이프라인이 없어 배선 자체가 불가능하다.
> 진짜 병목은 `engine/`의 배선이 아니라 **입력 데이터 생산부의 부재**다.**

A안(배선)을 승인하셨으나, 감사 결과 A안의 전제(「이미 구현된 고품질 로직을 살린다」)가
부분적으로 성립하지 않는다. 배선 가능한 5개는 즉시 진행하고, 나머지는 판정을 바로잡아
재결정을 요청드린다.

---

## 1. 감사 방법

1. `engine/` 18모듈 전수 LOC 측정 및 진입점 확인
2. 최상위 대응 패키지(`domain`, `pipeline`, `harness`, `correction`, `compliance`, `parser`, `exporter`)와
   **AST 기반 심볼 비교** (함수·클래스·모듈 변수)
3. 각 모듈이 요구하는 **입력 데이터가 프로덕션 파이프라인에서 실제로 생산되는지** 역추적
4. `verify_100_matrix.py`(100점 벤치마크)의 입력 출처 검증

---

## 2. 핵심 발견 — 심볼 교집합 0: 중복이 아니라 별개 구현

| `engine/` 모듈 | LOC | 대응 모듈 | LOC | 공통 심볼 | `engine/` 전용 심볼 |
| :--- | --: | :--- | --: | --: | :--- |
| `domain/models.py` | 83 | `domain/models.py` | 148 | **0** | `CADPrimitive3D`, `ComplianceCitation`, `FloorplanDocument`, `RoomGeometry` |
| `pipeline/contracts.py` | 26 | `pipeline/contracts.py` | 173 | **0** | `Generate3DRequestContract`, `Generate3DResponseContract` |
| `harness/context_firewall.py` | 85 | `harness/context_firewall.py` | 32 | **0** | `ContextFirewall` |
| `correction/patch.py` | 61 | `correction/patch.py` | 113 | **0** | `IFCPatchEngine` |
| `inference/slm_adapter.py` | 85 | `compliance/slm_adapter.py` | 64 | **0** | `SLMInferenceAdapter` |
| `inference/gemini_adapter.py` | 70 | `compliance/gemini_adapter.py` | 81 | 1 | `LegalReviewReportSchema` |
| `compliance/compliance.py` | 123 | `compliance/jp_compliance.py` | 115 | **0** | `ComplianceItem`, `ComplianceReport`, `DualTrackComplianceEngine` |
| `geometry/room_detect.py` | 101 | `parser/room_detect.py` | 351 | **0** | `RoomDetector` |
| `compliance/egov_rag.py` | 87 | `compliance/rag/retriever.py` | 52 | **0** | `EGovLawRAGEngine`, `LawNode` |
| `compliance/rag/hierarchical_xml_rag.py` | 136 | `compliance/rag/parser.py` | 200 | **0** | `HierarchicalLegalRAGEngine`, `LegalNode` |
| `exporters/ifc_worker.py` | 67 | `parser/export_ifc.py` | 230 | **0** | `REPO_ROOT`, `run` |

**같은 개념을 다루면서 이름이 하나도 겹치지 않는다.** 즉 두 번 독립적으로 구축된 시스템이다.
프로덕션 경로는 `core/engine.py` → 최상위 패키지를 사용하고, `engine/`은 벤치마크와
`test_stage1_models_rules.py`만 참조한다.

이것이 `commercialization_roadmap` C3에서 지적한 **「Over-built, Under-wired」** 의 실체다.

---

## 3. 배선 가능성 판정 (18모듈)

### ✅ 배선 가능 — 입력 데이터가 이미 존재 (5개)

| 모듈 | LOC | 접점 | 기대 효과 |
| :--- | --: | :--- | :--- |
| `geometry/pslg_topology.py` | 154 | `parser/pdf_vector.extract_vector_geometry()`가 이미 `walls[].p1/p2` 생산 | T-Junction·미세 간극 치유로 **누수 폴리곤** 생성 |
| `exporters/sandbox_runner.py` | 93 | `parser/export_ifc` (ifcopenshell, segfault 위험) | 프로세스 격리 + 하드 타임아웃 |
| `exporters/worker_pool.py` | 78 | 위와 세트 | 워커 재활용(`max_tasks_per_child=50`) |
| `compliance/rules.py` | 224 | `compliance/evaluator.evaluate_project()` | **7개 건축기준법 규정 추가** (아래 4항 단서) |
| `pipeline/idempotent_task.py` | 86 | Celery 태스크 | 재실행 중복 방지 (Redis 전제) |

### ⛔ 배선 불가 — 입력 생산부가 없음 (2개)

| 모듈 | LOC | 이유 |
| :--- | --: | :--- |
| `geometry/scale_calibration.py` | 63 | `dimension_pairs`(px 길이 + 치수 주석 mm)를 생산하는 코드가 **전무**. `parser/text_extract.py`는 `CH=`/`H=` 천장고만 처리하며 치수선(寸法線) 추출기가 없다. |
| `geometry/segmentation.py` | 55 | **허구 모듈.** `model_name = "cad-swin-unet-v2"` 문자열만 있고 모델 로더(`torch`/`onnx` import)가 없다. → **폐기 권고** |

### ⚠️ 판정 보류 — 어느 쪽이 우위인지 기능 검증 필요 (11개)

`domain/models`, `pipeline/contracts`, `harness/context_firewall`, `correction/patch`,
`inference/*`, `compliance/compliance`, `compliance/egov_rag`,
`compliance/rag/hierarchical_xml_rag`, `geometry/room_detect`, `exporters/ifc_worker`

심볼이 전혀 겹치지 않아 자동 병합이 불가하며, 동작 비교 테스트를 먼저 작성해야 한다.
**단순 배선 시 두 구현이 공존해 정합성이 깨진다.**

---

## 4. 감사 중 추가 발견한 CRITICAL 2건

### C8. 개구부(창·문) 추출이 영구 데드코드 — 採光·換氣·排煙 판정 불가

**근거**

```
compliance/extractor.py:74  door_mask_path = .../door_mask_page{N}.png
compliance/extractor.py:79  if not os.path.exists(door_mask_path) or not os.path.exists(contours_path):
compliance/extractor.py:80      return openings        # <- 항상 빈 배열
```

- `door_mask_page*.png`를 **생산하는 코드가 저장소 전체에 존재하지 않는다** (`grep -rn door_mask` 결과: 소비부 5건, 생산부 0건).
- `contours_page*.json`도 미생산.
- 따라서 `extract_openings()`는 **항상 `[]`를 반환**한다. 실제 산출물로도 확인:

```
out/test_compliance/page0_compliance.json
  openings: 0건
  walls:    0건
```

**파급**

제품은 「BIM確認申請 & 適合性自動検証システム」를 자칭하지만, 건축기준법상 핵심 3개 판정이
구조적으로 불가능하다.

| 판정 | 필요 입력 | 상태 |
| :--- | :--- | :--- |
| 採光 (daylight) | 유효 개구 면적 | ⛔ 없음 |
| 換氣 (ventilation) | 환기 개구 면적 | ⛔ 없음 |
| 排煙 (smoke exhaust) | 배연창 면적 | ⛔ 없음 |

`engine/compliance/rules.py`의 7개 규칙 중 **6개가 바로 이 개구부 데이터를 요구**한다.
즉 **C8이 해결되지 않으면 A안의 최대 가치(법규 7종 추가)를 얻을 수 없다.**

개구부 데이터 없이 규칙을 배선하면, 미판정을 `PASS`로 처리하는 C2 유형의 결함이 재발한다.
**컴플라이언스 제품이 평가하지 않은 건물을 적합으로 인증하는 것은 법적 리스크다.**

### C9. 스케일 상수 하드코딩 — 물량산출·견적 오차의 원천

**근거**

```python
# core/units.py:14
RASTER_PIXEL_TO_MM = 5.0      # 모든 래스터 도면에 동일 적용 (200 px/m 가정)
```

`core/engine.py:97`에서 `save_rooms_json(..., pixel_to_mm=RASTER_PIXEL_TO_MM)`으로 사용된다.
도면 스케일이 1:50이든 1:200이든 **항상 5.0 mm/px로 환산**하므로, 면적·물량·견적이
스케일에 비례해 틀린다.

`engine/geometry/scale_calibration.py`가 이 문제의 해법이지만, 위 3항대로 입력(치수 주석)이 없다.

---

## 5. 100점 벤치마크가 조작 입력으로 통과하고 있다

`verify_100_matrix.py`는 `harness/bench_integrity.pmo_no_constant_scores`로
**상수 점수 대입**을 AST로 차단한다(잘 된 장치). 그러나 **입력 조작**은 탐지하지 못한다.

```python
# verify_100_matrix.py:76 — 스케일 보정 5점
dimension_pairs = [
    {"pixel_length": 450.0, "annotated_mm": 4500.0},   # 100 px/m
    {"pixel_length": 300.0, "annotated_mm": 3000.0},   # 100 px/m
    {"pixel_length": 600.0, "annotated_mm": 6000.0},   # 100 px/m
]
```

세 쌍 모두 **정확히 100 px/m**이라 편차가 0% → `mean_error_percent = 0.0` → 만점.
실제 도면이 아니라 벤치마크가 직접 만든 숫자다.

```python
# verify_100_matrix.py:62 — PSLG 15점
segments = [ ((0,0),(10,0)), ((10,0),(10,10)), ... ]   # 정사각형 2칸, 손으로 작성
```

**100점은 「모듈이 이상적인 가짜 입력에서 동작한다」는 뜻이며,
「제품이 실제 도면에서 동작한다」는 뜻이 아니다.** C3의 지적이 여기서 완전히 입증되었다.

---

## 5.5 배선 실행 중 추가 확정한 CRITICAL 2건 (C10·C11)

W1(`pslg_topology` 배선)을 실제로 실행하는 과정에서, 정적 감사 단계에서는
보이지 않았던 결함을 추가로 확정했다. **C10은 `engine/`이 아니라 이미 운영 중인
`parser/` 경로의 결함**이며, 심각도는 기존 C1~C9를 모두 상회한다.

### C10. 벡터 정제 파이프라인이 내부 벽을 전부 삭제한다 (최심각 · 프로덕션 결함)

`parser/line_refine.py::filter_structural_walls()` 는 차수(degree)를
**끝점 근접(endpoint proximity)으로만** 계산하고 교차점을 전혀 계산하지 않는다.

```python
# parser/line_refine.py:384-398 (수정 전)
def near(p, q, tol=join_tol) -> bool:
    return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol

# a의 양 끝점이 b의 양 끝점과 가까운지만 본다.
# a와 b가 '교차'하는지는 보지 않는다.
```

CAD 벡터 도면은 교차점에서 쪼개지지 않은 긴 선으로 저장된다
(7x7 격자의 가로선은 x=100..900 을 한 번에 긋는 세그먼트 1개).
따라서 내부 벽의 끝점은 다른 선의 끝점과 멀리 떨어져 있고
**degree = 0 → 전부 삭제**된다.

**실측** (`uploads/` 실업로드 PDF, 8x8 격자):

| 단계 | 세그먼트 수 | 판정 |
| :--- | ---: | :--- |
| raw | 32 | |
| 1. `refine_lines(min_len=25)` | 32 | 정상 |
| 2. `merge_collinear` | 16 | 정상 (역방향 중복 제거) |
| 3. `snap_endpoints(8.0)` | 16 | 정상 |
| 4. `merge_parallel_pairs(4.0)` | 16 | 정상 |
| **5. `filter_structural_walls`** | **4** | **내부 벽 12개 소실** |
| 최종 방 탐지 결과 | **1개** | **정답 64실** |

살아남은 4개는 우연히 끝점이 서로 일치하는 **외곽 테두리뿐**이다.
즉 **벡터 PDF 평면도에서 방을 추출하는 핵심 기능이 성립하지 않았다.**

### C10 근본 원인 — 평면 분할(Planar Subdivision) 부재

C10과 `engine/geometry/pslg_topology.py` 의 결함은 **동일한 근본 원인**을 갖는다.

> 차수 계산이든 면 추출이든, 모든 위상 알고리즘은 입력이 PSLG — 즉
> **교차점에서 분할된 세그먼트 집합** — 일 것을 전제한다.
> 이 전제가 빠지면 내부 정점이 존재하지 않아 알고리즘이 전부 오작동한다.

`snap_endpoints()` 는 근접한 끝점만 뭉개므로 이 역할을 대신할 수 없다.

### PSLG 모듈 실측 결함 3건 (감사 §3의 「배선 가능」 판정을 뒤집는 근거)

감사 §3에서는 `pslg_topology` 를 "입력이 존재하므로 배선 가능"으로 분류했으나,
**기능 검증 결과 어떤 입력에서도 방을 추출할 수 없는 모듈**로 판명되었다.

| ID | 결함 | 실측 증거 |
| :-- | :--- | :--- |
| **D1** | 교차점 분할 부재 → 최소 면이 존재하지 않음 | 8x8 미분할 격자 → 사이클 **1개**(외곽만), 방 **0개** |
| **D2** | 단순 사이클 전수 열거(DFS) → 복합(가짜) 폴리곤 폭발 | 7x7 격자 → **4,221개** (정답 49개의 **86배**) |
| **D3** | `len(path) < 12` 하드 제한 → 12변 초과 폴리곤 누락 | 복도·LDK 등 다각형실 추출 불가 |

D2의 조합 폭발은 입력에 따라 사실상 정지에 가깝다
(6x6 격자 1.76초, 세그먼트 수 증가 시 기하급수).

### C11. 실도면 검증 데이터가 0건 — 100점 벤치마크의 토대 자체가 부재

`uploads/` 의 PDF 5건을 전수 조사한 결과:

```
md5 전부 동일: 2d08c819b2e88b8c712fa42a4301075d
크기 2,647B / 페이지 1000x1000 / paths 16 / 텍스트 0건
```

* 5건 전부 **동일한 합성 픽스처** (사용자가 5회 업로드)
* **텍스트가 0건** → 치수 주석(寸法線) 추출 불가 = **C9(스케일 하드코딩)를
  해결할 입력 자체가 존재하지 않음**
* 개구부 마스크(`door_mask_page*.png`) 산출 흔적 없음 = **C8 재확인**
* `tests/` 의 E2E 테스트 7건이 `sample.pdf`, `vector_test.pdf`, `multi_page_test.pdf`
  부재로 **skip** — 실도면 회귀 테스트가 단 한 건도 없다

**결론: 제품은 실제 평면도로 한 번도 검증된 적이 없다.**
§5의 「100점 벤치마크가 조작 입력으로 통과」와 정확히 같은 구조의 문제가
E2E 경로에도 존재한다.

---

## 6. 수정된 실행 계획

### 즉시 착수 (배선 가능 5개)

| 순서 | 작업 | 상태 / 선행 조건 |
| :-: | :--- | :--- |
| **W0** | **C10 긴급 수정 — 평면 분할 추가** | ✅ **완료** (최우선. 아래 W0 상세) |
| W1 | `pslg_topology` → 벡터 경로 폴리곤 생성 | ✅ **완료** (알고리즘 전면 교체 후 배선, §5.5) |
| W2 | `sandbox_runner` + `worker_pool` → IFC 내보내기 격리 | 대기 — 워커 스크립트 1개 작성 |
| W3 | `compliance/rules.py` 7규칙 배선 | 대기 — **⚠️ 미판정 시 `PASS` 금지. `NOT_EVALUATED` 반환 필수** |
| W4 | `idempotent_task` → Celery (Redis 전제) | 대기 — Redis 백엔드 확인 |
| W5 | `segmentation.py` **폐기** (허구 모듈) | 대기 |

### W0 상세 — 평면 분할 도입 (C10 해결)

| 항목 | 내용 |
| :--- | :--- |
| 신규 SSOT | **`core/planar.py`** — `subdivide_segments()` / `minimal_faces()` / `extract_interior_faces()` |
| 알고리즘 | 교차점 분할은 x/y 인덱스 + 이분 탐색으로 `O(n log n + k)`, 면 추출은 하프엣지 회전 스윕으로 `O(V+E)` |
| 배선 | `parser/pdf_vector.py` 4단계와 5단계 사이에 `subdivide_at_intersections()` 삽입 |
| 위임 | `parser/line_refine.subdivide_at_intersections()` 는 `core.planar` 어댑터로 축소 (구현 중복 제거) |
| 성능 | 60x60 격자(3,600실) **24ms** (구버전은 동일 입력 조합 폭발) |
| 테스트 | `tests/test_planar_subdivision.py` **27건** 신규 |

**실측 효과 (8x8 격자 실업로드 PDF):**

| 지표 | 수정 전 | 수정 후 |
| :--- | ---: | ---: |
| refined walls | 4 | **112** |
| 탐지된 방 | 1 | **49** (7x7 격자 정답) |

### W1 상세 — PSLG 재작성

`engine/geometry/pslg_topology.py` 를 D1·D2·D3 을 모두 해소하는 구현으로 교체했다.
공개 API(`PSLGTopologyEngine`, `snap_endpoints`, `extract_room_polygons`, 반환 스키마)는
그대로 유지하여 기존 호출 계약을 깨지 않는다.

| 지표 | 구버전 | 신버전 |
| :--- | ---: | ---: |
| 7x7 격자 방 추출 | 4,221개 | **49개** |
| 8x8 미분할 격자 방 추출 | 0개 | **64개** |
| 60x60 격자 소요 | (조합 폭발) | **24ms** |

### 병목 해결 (선행 필수, 별도 스코프)

| 순서 | 작업 | 막힌 것 |
| :-: | :--- | :--- |
| B1 | **개구부(창·문) 추출기 구현** — `door_mask_page*.png` 생산 | C8, 법규 6종 |
| B2 | **치수 주석(寸法線) 추출기 구현** — `dimension_pairs` 생산 | C9, 스케일 보정 |

B1·B2가 없으면 A안의 핵심 가치(법규 확장, 정밀 물량산출)를 얻지 못한다.
두 작업은 **배선이 아니라 신규 개발**이며, Phase 1로 편성해야 한다.

---

## 7. 대표님 재결정 요청

원안 A(배선) / B(폐기)의 이분법이 성립하지 않는다. 실제 선택지는 다음과 같다.

| 안 | 내용 | 소요 |
| :--- | :--- | :--- |
| **A-1 (권고)** | 배선 가능 5개만 배선 + `segmentation` 폐기 + 나머지 11개 동결(유지하되 미사용 명시) | 약 1주 |
| **A-2** | A-1 + 개구부·치수 추출기 신규 개발(B1·B2) 후 법규 7종까지 완전 배선 | 3~4주 |
| **B** | `engine/` 전량 폐기, 최상위 패키지 단일 체제로 유지 | 2~3일 |

**권고: A-1.** (W0·W1 완료로 본 권고는 이미 절반 실행되었다.)
배선으로 즉시 얻을 수 있는 이익(PSLG 폴리곤 품질, IFC 내보내기 안정성)은 확보하면서,
근거 없는 대규모 통합 작업에 시간을 쓰지 않는다. B1·B2는 제품 가치에 직결되므로
Phase 1 정식 항목으로 편성하는 것이 옳다.

---

## 8. W0·W1 완료 후 갱신된 우선순위

C10·C11 확정으로 우선순위가 바뀌었다. **C10은 이미 수정 완료**이나,
C11(실도면 검증 데이터 0건)은 남아 있다.

| 우선순위 | 항목 | 상태 | 근거 |
| :-: | :--- | :--- | :--- |
| **P0** | C10 벡터 내부 벽 삭제 | ✅ **완료** | 핵심 기능 자체가 성립하지 않았음 |
| **P0** | **C11 실도면 검증 데이터 확보** | ⛔ **미착수 — 대표님 조치 필요** | 아래 참조 |
| P1 | C8 개구부 추출기 (B1) | 대기 | 법규 6종 판정 불가 |
| P1 | C9 치수 주석 추출기 (B2) | 대기 | 스케일 하드코딩 해소 전제 |
| P2 | W2~W5 잔여 배선 | 대기 | A-1 범위 |

### P0 — C11 해결을 위한 요청 사항

코다리 개발 군단이 **직접 만들 수 없는 것**이다. 실측이 필요한 자산이다.

1. **실제 일본 평면도 PDF 3~5건 제공** (개인정보·기밀 마스킹 후)
   - 벡터 PDF 우선, 래스터 스캔본 1건 이상 혼용 권장
   - 텍스트 레이어(치수 주석)가 살아 있는 파일 필수 — C9 해결 전제
2. **정답지(ground truth) 작성**: 각 도면의 실 목록과 면적(m²)
   - 이것이 없으면 「49개 방을 찾았다」가 맞는지 검증할 방법이 없다
3. 확보 후 `tests/fixtures/` 에 편입 + skip 중인 E2E 7건 활성화

이 3종이 없이는 **어떤 정확도 주장도 불가능**하다.
C10 수정으로 「내부 벽을 지우는 버그」는 고쳤으나,
「실제 도면에서 몇 % 맞는지」는 여전히 **미측정** 상태다.

---

*문서 버전: 1.0.0 | 근거 커밋: 작업 트리 (2026-08-30)*
