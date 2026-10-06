# AI CAD Converter — 建築確認プレチェック支援 SaaS

> **本ツールは判定を確定しません。最終判断は有資格者(建築士)・審査機関が行います。**
> 対応制度: BIM図面審査(2026-04-01開始) / 建築基準法(旧4号→新2号/新3号, 2025-04-01) / 建築物省エネ法(BEI強化 2026-04-01) / BELS(2024-04区分)
> 정본 계획서: `state.md` v1.0

## 구성

- `app/` — FastAPI (진입점 `app/main.py`, `/health` 포함)
- `core/engine.py` — 프로덕션 파이프라인 (`engine.geometry.pslg_topology` SSOT 배선됨)
- `compliance/` — `rules_building`(新2号분류) / `rules_energy`(BEI 2026-04표) / `rules_bels`(별점) / `rules_site`(盛土·소방 판정불가)
- `web/` — 제품 프론트 (정본. 루트 `app/*.tsx` Next는 레거시, `site/` 분리 예정)
- `supabase/schema.sql` — 3테이블 (`profiles/projects/processed_payment_events`), RLS `auth.uid()=user_id`
- `tests/` — 게이트 (`test_state_gates.py` 포함). 루트 `verify_*.py`는 `tests/legacy/`로 이동됨

## 실행

```bash
# 1. ENV
cp .env.example .env  # SUPABASE_URL / SUPABASE_ANON_KEY / STRIPE_* / ENV=development
# 2. backend
pip install -r requirements.txt
python -m pytest tests/ -q
# 3. frontend (정본 web/)
cd web && npm ci && npx tsc --noEmit && npm run build
# 4. infra
docker compose up --build
```

## 법규 판본

`data/laws/manifest.json` 고정. 省エネ法 XML 미수록 시 매트릭스는 즉시 실패해야 하며 BEI는 Web프로그램 값 입력 + 仕様基準 병행만 허용 (LLM 직접계산 금지).

## 요금

¥1,500/30C · ¥4,900/100C · ¥9,800/300C (IFC 3C / 검증+PDF 10C). 請求書·銀行振込 병행 (Stripe 단독 금지). 補助金(建築GX·DX) 증빙 출력 지원.

## 출항 조건

`state.md` §9 Go/No-Go 전부. `sk_live_*`는 그 전까지 금지.
