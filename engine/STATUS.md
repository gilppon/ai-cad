# engine/ 인벤토리 (M1, STATE A안 경과보고 — 2026-10-06)

`engine/` 18모듈은 프로덕션 미배선 상태로 남는다. 완전 배선(A안 본丸)은
프로덕션 기준 골든셋 재작성(Phase 1.1)이 선행 조건이므로 본 문서에서
각 모듈의 상태를 고정하고, 무단 증식을 테스트로 차단한다.

## 상태 정의

- WIRED: 프로덕션 경로에서 import됨.
- DELEGATE: 실로직을 생산 모듈에 위임하는 얇은 어댑터.
- TEST-ONLY: 테스트·벤치마크 전용. 프로덕션 사용 금지.

## 모듈별 상태

| 모듈 | 상태 | 비고 |
|---|---|---|
| `geometry/pslg_topology.py` | WIRED | `core/engine.py`에서 import. 내부는 `core/planar` SSOT에 위임 |
| `exporters/ifc_worker.py` | DELEGATE | `parser/export_ifc.build_ifc_from_multi_floor` 호출. 포맷 표기 IFC2X3 |
| `exporters/sandbox_runner.py` | TEST-ONLY | `test_sp2_reliability.py` 격리 실행용 |
| `exporters/worker_pool.py` | TEST-ONLY | legacy stage2 전용 |
| `geometry/scale_calibration.py` | TEST-ONLY | 매트릭스 D1.2 전용(평균법). 생산 SSOT는 `parser/scale_calibrate.py`(중앙값+괴리율 fail-closed) |
| `geometry/room_detect.py` | TEST-ONLY | 생산은 `parser/room_detect.py` 사용. 통폐합은 A안 본丸에서 |
| `geometry/segmentation.py` | TEST-ONLY | — |
| `compliance/rules.py` | TEST-ONLY | 생산은 `compliance/rules*.py` 사용 |
| `compliance/compliance.py` | TEST-ONLY | — |
| `compliance/egov_rag.py` | TEST-ONLY | 생산은 `compliance/rag/*` 사용 |
| `compliance/rag/hierarchical_xml_rag.py` | TEST-ONLY | legacy stage3 전용 |
| `correction/patch.py` | TEST-ONLY | 생산은 `correction/patch.py` 사용 |
| `domain/models.py` | TEST-ONLY | 생산은 `domain/models.py` 사용 |
| `pipeline/contracts.py` | TEST-ONLY | 생산은 `pipeline/contracts.py` 사용 |
| `pipeline/idempotent_task.py` | TEST-ONLY | 매트릭스 D4.1 전용 |
| `harness/context_firewall.py` | TEST-ONLY | 생산은 `harness/context_firewall.py` 사용. 매트릭스 D5.1 전용 |
| `inference/gemini_adapter.py` | TEST-ONLY | legacy stage3 전용 |
| `inference/slm_adapter.py` | TEST-ONLY | 매트릭스 D5.1 전용 |

## 규칙

- 신규 `engine/*.py` 추가 시 본 문서 갱신 + 아래 테스트 갱신이 필수. 무단 증식 금지.
- TEST-ONLY 모듈을 `app/`·`core/`에서 import하는 것은 금지 (게이트 테스트).
