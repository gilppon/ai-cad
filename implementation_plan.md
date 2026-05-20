# 🌟 일본 국토교통성 BIM 제출 의무화 대응 및 건축기준법 AI 적합성 검증 'Japanbuild-BIM3D Compliance' MVP 최종 개발 계획서

## 1. Project Definition & Business Goal

본 프로젝트는 단순한 2D 도면 뷰어를 넘어, **일본 국토교통성(MLIT)의 준공 도서 BIM(3D IFC) 제출 의무화 법령**에 선제적으로 대응하고, **일본 건축기준법(建築基準法) AI 적합성 검증**을 현장에서 3분 안에 완수해내는 상용 SaaS 솔루션입니다.

### 🎯 핵심 비즈니스 목표 (일본 소기업/개인 사업자 판매 규격)
1. **BIM 의무화 완벽 대응 (2D-3D IFC 자동 변환)**: 2D PDF/이미지 도면 업로드 시 국제 표준 **3D IFC BIM 모델**을 자동 생성 및 추출하는 코어 엔진 완비. (완료)
2. **도면 파싱 실패 극복 (2D-3D 에디터)**: 자동 인식의 현실적 기하 한계를 작업자가 웹 상에서 수동 드래그로 즉각 보정하고 3초 만에 3D 씬을 재빌드하는 UI 제공. (완료)
3. **일본 건축기준법 AI 적합성 검증**: 채광/환기(제28조) 및 반자 높이(시행령 제21조) 등을 기하학적 결정론적 규칙과 RAG+SLM AI 추론으로 복합 검증 및 보고서 패키징. (진행 중 - ReportLab CID 폰트 내장 아키텍처 및 RAG 매핑 활용)
4. **1차 실무 킬러 모듈 (구분소유법 3D 누수 판정)**: 맨션 분쟁의 뇌관인 공용부(共用部分) vs 전유부(専有部分) 책임 판정 및 배관 공간(PS/DS) 매핑 기능 탑재. (완료)
5. **글로벌 인프라 준비**: JPY 엔화 기반 Stripe 결제(1,500엔 / 월 4,900엔 / 월 9,800엔), 하네스 회로 차단기(Circuit Breaker), 현지 일본어 다국어화(i18n) 완비. (완료)

---

## 2. Current State (현재 상태 및 잔존 갭)

현재 7대 핵심 검증 테스트(`verify_*.py`)와 `verify_jp_compliance.py`가 100% PASS하여, 백엔드의 벽체 복구, 다중 층 파싱, IFC 3D 변환, 2D-3D 분할 수동 교정 API 및 일본 공동주택 구분소유법 기반 3중 책임 판정 적재 모듈까지 완벽하게 동작하고 있습니다.

### 🚨 상용 판매를 위한 잔존 갭 (Gaps to Market)
*   **보고서 패키징 기능 부재**: 고객사(원청사, 보험사, 집주인)에게 메일이나 라인(LINE)으로 즉시 전달할 수 있는 깔끔하고 공신력 있는 일본어 PDF 출력 모듈이 부재함. -> **Phase 8에서 ReportLab 기반 고품격 A4 PDF 엔진으로 정밀 해결**.
*   **결제 및 다국어 장벽**: JPY 엔화 결제를 위한 Stripe 연동 및 UI 일본어 지원 미비. -> **Phase 9에서 Stripe Checkout Mock & i18n 번역 레이어 통합으로 해결**.

---

## 3. Delivery Strategy & Harness Principles

"선보고 후실행, 계획-테스트-검증 3박자"의 **하네스 프로토콜(Harness Protocol)**을 준수합니다.

*   **Circuit Breaker (회로 차단기)**: PDF 생성 시 폰트 누락으로 인한 크래시를 방지하기 위해, ReportLab의 내장 아시안 CID 폰트(`HeiseiKakuGo-W5`, `HeiseiMin-W3`)를 1순위로 바인딩하여 윈도우/리눅스 전 환경에서 무결성 확보. Stripe 연동 실패 시에도 Mock 처리 가동으로 비즈니스 연속성 유지.
*   **Context Firewall (맥락 방화벽)**: PDF 드로잉 및 결제 미들웨어 로직은 `exporter/` 및 `app/api/v1/endpoints.py`에 격리시켜 코어 기하 파이프라인에 사이드 이펙트 전파 차단.
*   **Hard Boundaries (엄격한 경계)**: 기존에 100% 검증 완료된 `verify_*.py` 기반의 파이프라인 코어는 절대로 깨뜨리지 않고, 데코레이터나 어댑터 패턴으로 시맨틱 레이어를 확장.

---

## 4. User Review Required (대표님 결재 및 피드백 필요 사항)

> [!IMPORTANT]
> **일본 현지 세일즈 및 서비스 런칭을 위해 다음 사항에 대한 대표님의 승인이 필요합니다.**

1. **Stripe 요금제 구성 안**:
   *   **Basic Plan (월 4,900엔)**: 월 10건 도면 3D 변환 및 1장 리포트 생성.
   *   **Pro Plan (월 9,800엔)**: 무제한 변환, 3D WebGL 공유 링크 제공, 3D 파일(IFC, STEP) 다운로드 무제한.
   *   **Pay-per-case (건당 1,500엔)**: 비구독자용 1회성 결제.
2. **일본어 리포트 공식 서식의 공신력**:
   *   출력되는 PDF 보고서 상단에 **'일본 하자진단 표준 지침(住宅紛争処理技術基準) 준수'** 문구 및 시공사 날인(도장) 란을 포함할지 여부. (현장 소기업 사장님들은 날인 도장 이미지 업로드 기능을 매우 선호함).
3. **공용부/전유부 판정 기준의 책임 한계 고지**:
   *   우리 시스템이 도면과 누수원 위치를 기반으로 "공용부 책임 확률 85%" 등의 판정 보조를 내릴 때, 법적 분쟁 방지를 위한 면책 조항(Disclaimer)을 하단에 필수 기재할 예정입니다.

---

## 5. Phase Breakdown (상용화 최종 5단계 로드맵)

### Phase 6. 2D-3D 분할 수동 교정 웹 에디터 UI 개발 (완료)
*   **목표**: 비전문가도 마우스나 태블릿 터치로 오차를 바로잡을 수 있는 반응형 에디터 구현.
*   **구현 범위**:
    1. **좌측 2D SVG 인터페이스**:
       *   도면 위에 오버레이된 파싱 벽선 마우스 드래그(Drag) 조정.
       *   방 폴리곤 클릭 시 우측 드롭다운으로 방 타입(LDK, 화장실, 배관실 등) 즉시 수정.
       *   **누수 핀(Leak Pin)**: 마우스 우클릭 혹은 드래그로 누수 시발점 핀 장착.
       *   **피해 브러시(Damage Brush)**: 2D Canvas 상에 마우스 드래그로 피해 면적 색칠 (Ceiling/Wall/Floor 구분).
    2. **우측 Three.js WebGL 뷰어**:
       *   좌측 2D 편집이 끝나거나 일시 정지될 때 델타 패치(`CorrectionBatchRequest`)를 3초 안에 백엔드로 전송.
       *   백엔드 `rebuild_after_correction` 실행 후 반환된 3D IFC 데이터를 Three.js가 읽어 실시간 갱신(Orbit Controls, 단면 컷 뷰 지원).

---

### Phase 7. 일본 주택법 대응 공간 시맨틱스 및 공용부/전유부 판정 모듈 (완료)
*   **목표**: 일본 공동주택(맨션)의 하자 보수 소송 및 보험 청구의 핵심 쟁점인 책임 구역 분리.
*   **구현 범위**:
    1. **일본 주택 특화 스키마 매핑** (`compliance/jp_compliance.py` 신설):
       *   방 종류에 일본 현지 건축 도면 약어 매핑 (LDK, 洋室, 和室, UT, WC, PS, DS, MB).
       *   특히 **PS(Pipe Space, 파이프 스페이스)** 및 **DS(Duct Space, 덕트 스페이스)** 영역을 별도 중요 시맨틱 영역으로 분류.
    2. **공용부 vs 전유부 판정 엔진**:
       *   누수 핀이 꽂힌 벽체의 내부 배관 공간(PS/DS) 여부, 혹은 슬래브 상하부 위치 정보를 분석하여 **[공용부 책임(건물 장기수선충당금 처리 대상)]**인지 **[전유부 책임(개인 세대주 자부담 또는 일상생활배상책임보험 처리 대상)]**인지 1차 자동 판정 후 리포트에 출력.

---

### Phase 8. A4 1장 최적화 '일본어 누수 진단 보고서' PDF 생성기 (완료)
*   **목표**: 현장 사장님이 원청 대기업 및 손해보험사에 바로 전달할 수 있는 극도로 깔끔하고 가독성 높은 A4 1장 보고서 패키징.
*   **구현 범위**:
    1. **1장 레이아웃 디자인 시스템**:
       *   정부 및 보험사 제출 규격에 맞춘 단정하고 신뢰감 주는 디자인.
       *   **헤더**: 주소, 건물명, 진단 일자, 진단 기사 날인(도장 이미지).
       *   **좌측 단**: 평면 2D 오버레이 이미지 (누수원 핀 및 피해 브러시 영역 표시).
       *   **우측 단**: Three.js WebGL이 서버 사이드 혹은 클라이언트 사이드에서 캡처한 고해상도 3D 입체 투시도 (누수 발생 메커니즘을 3D 그래픽으로 직관적 설명).
       *   **하단**: 누수 판정 결과 (공용/전유 여부, 예상 보수 비용 범위, 특이사항 코멘트).
    2. **PDF 렌더링 파이프라인** (`exporter/pdf_generator.py` 신설):
       *   `WeasyPrint` 또는 `ReportLab`을 활용하여 HTML/CSS 템플릿을 고해상도 인쇄용 PDF로 변환.
       *   일본어 폰트(Noto Sans JP 등) 깨짐 방지 및 정렬 최적화.

---

### Phase 9. Stripe 결제 및 다국어화(i18n) 통합 (완료)
*   **목표**: 일본 로컬 개인 사업자들의 신용카드 즉시 결제 및 완벽하게 일본어로 현지화된 서비스 인프라 구성.
*   **구현 범위**:
    1. **Stripe Japan API 연동**:
       *   `stripe` 라이브러리를 활용하여 `/payments/checkout` 및 webhook 엔드포인트 구현.
       *   신용카드, 편의점 결제(Konbini Payment) 등 일본 현지 선호 결제 수단 활성화.
       *   사용자의 결제 상태(구독 만료, 크레딧 보유량)를 Supabase DB의 `profiles` 테이블과 연동하여 API 호출 시 미들웨어에서 권한 차단(Circuit Breaker).
    2. **다국어(i18n) 엔진 탑재**:
       *   프론트엔드 전체 UI 문구를 일본어로 완벽 번역 및 수용.
       *   백엔드 파이프라인에서 방 감지 시 방 영문 라벨(toilet, bedroom)을 일본어 표준 표기(トイレ, 洋室)로 자동 변환하는 변환 맵 내장.

---

### Phase 10. 통합 E2E 검증 및 실전 QA (Verification Gate) (완료)
*   **목표**: 실제 일본식 도면 PDF를 업로드하여 [자동 파싱] → [2D/3D 웹 에디터 수동 보정] → [책임 판정] → [PDF 진단 보고서 발행] → [결제 차감]에 이르는 전체 사용자 시나리오의 무결성 증명.
*   **구현 범위**:
    1. **모의 통합 테스트** (`tests/test_japan_market_e2e.py` 신설):
       *   Stripe Mocking을 통한 가상 결제 완료 처리.
       *   실제 수동 교정 API를 호출하여 누수원 핀을 주방(台所)과 벽 내부(PS)에 배치.
       *   최종 PDF 리포트가 정상 생성되고, Supabase 스토리지에 업로드 완료되는 전 과정을 검증.
    2. **모바일/태블릿 기기 호환성 테스트**:
       *   아이패드 및 일본 현지 저가형 안드로이드 태블릿 크롬 브라우저에서 Three.js 3D 화면이 버벅임 없이 렌더링되는지 성능 한계 측정.

---

## 🌟 6. 추가 고도화 로드맵: 일본 건설 3대장 벤치마킹 피처 상세 설계 (Phases 11~13)

### Phase 11. 현장 실사 사진 클라우드 업로드 및 3D IFC 객체 매핑 (Photoruction 벤치마킹)
*   **목표**: 현장 조사원이 스마트폰으로 촬영한 균열/누수/법규 위반 현장 사진을 3D 기하 데이터와 일대일 바인딩하여 보고서의 증빙 공신력을 극대화.
*   **시스템 아키텍처 및 미디어 업로드 흐름**:
    ```mermaid
    sequenceDiagram
        autonumber
        actor FieldUser as 현장 조사원 (모바일 Web)
        participant Client as React/Three.js 프론트엔드
        participant API as FastAPI 백엔드
        participant DB as Supabase PostgreSQL
        participant Storage as Supabase Storage Bucket
        
        FieldUser->>Client: 현장 하자 사진 촬영 & 3D 벽체 핀 클릭
        Client->>API: POST /api/v1/projects/{project_id}/media (바이너리)
        API->>Storage: projects/{project_id}/media/{file_name}.png 업로드
        Storage-->>API: CDN Public URL 반환
        API-->>Client: { "media_id": "...", "url": "https://..." }
        Client->>API: PATCH /api/v1/projects/{project_id}/incidents/{incident_id}/pins (3D좌표 & media_url 바인딩)
        API->>DB: UPDATE damage_zones / annotations SET photos = array_append(photos, url)
        DB-->>API: 업데이트 완료
        API-->>Client: 200 OK & 3D 핀 갱신
        Client-->>FieldUser: WebGL 화면에 실시간 사진 카드 팝업 표시
    ```

*   **DB 스키마 확장 사양**:
    | 테이블 / 필드명 | 데이터 타입 | 제약 조건 | 설명 |
    | :--- | :--- | :--- | :--- |
    | `damage_zones.photos` | `TEXT[]` | DEFAULT '{}' | 현장 실사 균열/누수 부위 고해상도 사진 CDN URL 목록 |
    | `annotations.attached_photo` | `TEXT` | Nullable | 도면 메모용 첨부 실사 사진 CDN URL |
    | `media_attachments` (신설) | `UUID` | PK, FK (project_id) | 현장 업로드 미디어 메타데이터 통합 관리 테이블 |

*   **API 라우트 상세 명세**:
    *   **1) 현장 미디어 업로드 API**
        *   `METHOD`: `POST`
        *   `ROUTE`: `/api/v1/projects/{project_id}/media`
        *   `REQUEST HEADER`: `Content-Type: multipart/form-data`
        *   `REQUEST BODY`: `file: UploadFile` (JPEG/PNG, Max 10MB)
        *   `RESPONSE (201 Created)`:
            ```json
            {
              "media_id": "att_8f7b9c2a-9e12-4d2b-8a5f-7c8d9e0f1a2b",
              "url": "https://supabase.co/storage/v1/object/public/projects/proj_001/media/leak_wall_01.png",
              "created_at": "2026-05-20T14:50:00Z"
            }
            ```
    *   **2) 3D IFC 객체 핀 및 미디어 매핑 API**
        *   `METHOD`: `PATCH`
        *   `ROUTE`: `/api/v1/projects/{project_id}/incidents/{case_id}/pins`
        *   `REQUEST BODY`:
            ```json
            {
              "pin_type": "leak_source",
              "target_room_id": 12,
              "coordinate": { "x": 12.45, "y": 1.82, "z": 2.4 },
              "media_urls": [
                "https://supabase.co/storage/v1/object/public/projects/proj_001/media/leak_wall_01.png"
              ],
              "comment": "파이프 스페이스(PS) 하부 이음매 미세 누수 및 콘크리트 균열 관측"
            }
            ```
        *   `RESPONSE (200 OK)`:
            ```json
            {
              "status": "success",
              "updated_pin": {
                "id": 105,
                "coordinate": { "x": 12.45, "y": 1.82, "z": 2.4 },
                "media_urls": ["https://..."],
                "comment": "..."
              }
            }
            ```

---

### Phase 12. 일본 국토교통성 표준 'BIM 준공 설계자 자가 확인 체크시트' PDF 패키징 (ANDPAD 벤치마킹)
*   **목표**: 2026 일본 국토교통성 BIM 제출 법령 가이드라인 규격 "BIM 준공 설계자 자가 확인 체크시트(BIM確認申請チェックシート)"를 자동 패키징하여, 소규모 설계사무소 사장님들의 인허가 관서 행정 비용을 0원으로 축소.
*   **체크시트 항목 데이터 모델 및 매핑 규격**:
    ```python
    # app/schemas/compliance.py 신설 또는 확장
    from pydantic import BaseModel, Field
    from typing import List, Optional

    class BIMComplianceCheckItem(BaseModel):
        article_no: str = Field(..., description="일본 건축기준법 조항 번호 (예: 第28조)")
        item_name_jp: str = Field(..., description="검증 항목명 (예: 居室の採光及び換気)")
        standard_value: str = Field(..., description="법령상 기준치 (예: 窓面積 / 居室面積 >= 1/7)")
        calculated_value: str = Field(..., description="3D IFC 파싱 및 기하 연산 값 (예: 1/5.8)")
        status: str = Field(..., description="적합성 판정 결과: PASS(O), FAIL(X)")
        inspector_comment: str = Field(..., description="설계자 종합 소견")

    class BIMComplianceChecksheet(BaseModel):
        project_id: str
        building_name: str
        chief_designer: str
        license_number: str  # 1급 건축사 면허번호
        check_items: List[BIMComplianceCheckItem]
        overall_judgment: str  # "適合" 또는 "不適合"
        digital_seal_url: Optional[str] = None  # 설계자 인장 이미지 URL
    ```

*   **PDF Generation Layout (`exporter/pdf_generator.py` 연동)**:
    - **ReportLab 기반 고해상도 벡터 테이블 드로잉**:
      - A4 세로 규격에 맞춰 관청 제출 공문 서식 구현.
      - 헤더 영역: 'BIM確認申請チェックシート' 타이틀, 1급 건축사 날인 이미지 정밀 합성.
      - 본문 영역: `check_items`를 돌며 법령 적합 판정 결과(O/X)와 수치 값을 셀에 맞춰 동적 렌더링. 특히 `PASS` 판정 시 붉은색 원형 합격 인장(`O`)을 데코레이션 처리하고, `FAIL` 시 `X` 및 `재검토 필요(再検討要)`를 굵은 고딕체로 강조.
    - **PDF 검증 자동화 가드**:
      - `verify_pdf_generation.py`에 자가 확인 체크시트 렌더링 테스트 코드 탑재 및 무결성 검사.

---

### Phase 13. IndexedDB 기반 오프라인 임시 저장 및 델타 동기화 미들웨어 (SPIDERPLUS 벤치마킹)
*   **목표**: 콘크리트 두께가 두꺼운 신축 현장이나 지하실 등 LTE/5G 음영 지역에서 통신이 끊겨도 서비스가 무중단 작동하는 오프라인-퍼스트 환경 구축.
*   **데이터 흐름도 (Offline-to-Online Synchronizer)**:
    ```mermaid
    graph TD
        A[사용자: 3D 벽체 보정 / 핀 편집] --> B{네트워크 온라인 상태?}
        B -- 예 (Online) --> C[즉시 백엔드 API 전송: PATCH /correction]
        B -- 아니오 (Offline) --> D[IndexedDB: DeltaActionLog 적재]
        D --> E[로컬 UI에 '임시저장됨' 상태 배지 표시]
        
        %% 네트워크 모니터링 루프
        F[브라우저 Heartbeat 서비스] -->|5초 주기로 핑 체크| G{네트워크 복구 완료?}
        G -- 예 --> H[IndexedDB Queue에서 미동기 델타 FIFO 순차 추출]
        H --> I[FastAPI 백엔드로 벌크 전송: POST /api/v1/projects/sync]
        I --> J[백엔드: 낙관적 락 검사 후 3D IFC 일괄 재빌드]
        J --> K[IndexedDB 내 로그 삭제 및 UI '동기화 완료' 녹색 동기화 배지 전환]
        G -- 아니오 --> F
    ```

*   **IndexedDB 스키마 설계 (`LocalForage` / `Dexie.js` 바인딩)**:
    ```javascript
    // IndexedDB 구조 선언 (Dexie.js 예시)
    const db = new Dexie('JapanbuildOfflineDB');
    db.version(1).stores({
      delta_actions: '++id, project_id, action_type, timestamp, sync_status'
    });

    // delta_actions 레코드 구조 예시
    {
      "id": 4012,
      "project_id": "proj_9982",
      "action_type": "CORRECT_WALL_COORDINATE",
      "payload": {
        "wall_id": "wall_3f2a",
        "new_start_point": { "x": 10.5, "y": 4.2 },
        "new_end_point": { "x": 10.5, "y": 9.8 }
      },
      "timestamp": 1779378600000,
      "sync_status": "pending" // pending -> syncing -> success/failed
    }
    ```

*   **백엔드 벌크 동기화 수신 엔드포인트**:
    *   `POST /api/v1/projects/{project_id}/sync`
    *   동일 객체에 대한 덮어쓰기 충돌을 차단하기 위해 타임스탬프 순서대로 순차 실행하는 **비관적/낙관적 복합 트랜잭션 락** 적용.

---

## 📅 Recommended 3-Week Accelerated Execution Plan (벤치마킹 피처 3주 완성 세부 일정)

### 📅 1주차: 현장 사진 업로드 API & 3D 객체 매핑 연동 (Phase 11)
*   **주요 태스크**:
    *   `app/api/v1/endpoints.py`에 사진 업로드 API 구현 및 Supabase 스토리지 버킷 연동.
    *   `IncidentCreateRequest` 데이터 모델에 사진 URL 배열 필드(`media_urls`) 신설 및 DB 스키마 업데이트.
    *   Three.js 3D 핀 클릭 시, 사진 팝업을 띄워주는 프론트엔드 연동 완성.
*   **검증 가드**: 모의 사진 업로드 및 핀 매핑 시, 이미지 경로가 정상 바인딩되어 API와 DB 상에 실시간 적재되는지 타임아웃 검증 통과.

### 📅 2주차: 국토교통성 가이드라인 'BIM 확인신청 체크시트' PDF 모듈 개발 (Phase 12)
*   **주요 태스크**:
    *   `exporter/pdf_generator.py`에 일본 관청 제출용 자가 확인 시트 템플릿(인쇄용 레이아웃) 코딩 및 이식.
    *   채광 면적과 반자 높이(층고)의 통과 여부를 동적으로 판정하여 O/X 도장을 찍어주는 렌더링 알고리즘 완성.
*   **검증 가드**: 생성된 PDF 파일의 마지막 페이지에 깨짐 없는 표준 양식으로 수치들이 정밀 렌더링되어 포함되는지 PDF 검증 스크립트 실행 통과.

### 📅 3주차: IndexedDB 기반 오프라인 캐싱 및 델타 동기화 미들웨어 구축 (Phase 13)
*   **주요 태스크**:
    *   프론트엔드 내 IndexedDB 로컬 캐싱 드라이버(LocalForage 등) 설치 및 델타 트랜잭션 로깅 모듈 개발.
    *   하트비트 복구 체크 미들웨어 및 델타 벌크 동기화 백그라운드 태스크 구현.
*   **검증 가드**: 인위적으로 네트워크 오프라인 모드를 가동한 상태에서 수정 작업을 집행하고, 온라인 복귀 시 누락 없이 백엔드 `/correction` API를 타고 3D 재빌드가 에러 없이 작동하는지 E2E 최종 시나리오 테스트 통과.

---

## 7. Success Definition (상용 런칭 합격 기준)

본 고고화 MVP의 완성은 다음 5대 지표를 완벽히 통과할 때 비로소 달성된 것으로 간주합니다:

1. **에디터 반응 속도**: 작업자가 2D 에디터에서 벽을 드래그하거나 누수 핀을 수정한 후, 우측 Three.js WebGL 뷰어에 보정된 3D 씬이 실시간으로 재렌더링되는 시간이 **평균 3초 이내**일 것.
2. **리포트 완성도**: 생성된 A4 1장 누수 진단 PDF가 깨짐 없는 정교한 일본어로 출력되며, 2D 도면 오버레이와 3D 입체 스냅샷이 오차 없이 시각화될 것.
3. **법적/보험사 부합성**: 공용부/전유부 판정 코멘트가 일본 손해보험사 청구 가이드 및 맨션 하자 소송 판례의 핵심 기준(PS 내 위치, 슬래브 하부 등)과 일치할 것.
4. **결제 및 사용성**: 일본 현지 카드 결제가 Stripe Sandbox에서 성공적으로 이루어지고, 모바일/태블릿에서 렉(Lag) 없이 에디터가 정상 작동할 것.
5. **BIM 인허가 완결성**: 일본 국토교통성 규격의 'BIM 자가 확인 체크시트'가 정상 출력되며, 3D 핀에 결합된 모바일 실사 사진이 깨짐 없이 PDF 리포트에 합산 출력될 것.

---
🛡️ **코다리 개발부장 보고 (충성! 대표님, 즉각 검토 후 재가 부탁드립니다!)**
