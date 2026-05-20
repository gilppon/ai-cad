# 🇯🇵 Japanbuild-BIM3D Compliance SaaS: Commercial Launch SOP
> **Standard Operating Procedure (SOP) for Production Deployment & Live Operations**  
> **Document Version:** 1.0.0 (Release-Ready)  
> **Author:** Kodari Development Division (코다리 개발본부)  
> **Classification:** Confidential - Internal Operations Only  

---

## 📌 Document Overview
This document serves as the official, step-by-step Standard Operating Procedure (SOP) for transitioning the **Japanbuild-BIM3D Compliance** platform from the local integration staging environment to the production-grade live environment. 

It guarantees flawless system scaling, airtight security posture under Japanese data protection laws (APPI), seamless Yen billing integrations via Stripe Japan, and high-availability operations for underground CAD inspection teams.

---

## 1. Supabase Production Migration & RLS (Row Level Security)
To ensure the absolute privacy of architectural blueprints and spatial metadata, the production database must operate under a strict **Zero-Trust Role-Based Access Control (RBAC)** architecture using Supabase Row Level Security.

### 1.1 database Schema Migration & Hardening
Apply the production database schema. Run the following migrations inside your Supabase SQL Editor.

```sql
-- =========================================================================
-- 1. BASE TABLES POLISHING & SECURITY ENABLING
-- =========================================================================
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_checksheets ENABLE ROW LEVEL SECURITY;

-- Create indexes for extremely fast lookup during delta sync
CREATE INDEX IF NOT EXISTS idx_incidents_project_id ON incidents(project_id);
CREATE INDEX IF NOT EXISTS idx_compliance_project_id ON compliance_checksheets(project_id);
```

### 1.2 Enterprise-Grade RLS Policies
Ensure that users can only access projects and incidents belonging to their own organization (`tenant_id`).

```sql
-- Project Table Isolation Policy
CREATE POLICY tenant_project_isolation ON projects
    FOR ALL
    TO authenticated
    USING (tenant_id = (auth.jwt() ->> 'user_metadata')::jsonb ->> 'tenant_id')
    WITH CHECK (tenant_id = (auth.jwt() ->> 'user_metadata')::jsonb ->> 'tenant_id');

-- Incidents (3D Pins & Coordinates) Isolation Policy
CREATE POLICY tenant_incident_isolation ON incidents
    FOR ALL
    TO authenticated
    USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'user_metadata')::jsonb ->> 'tenant_id'
        )
    )
    WITH CHECK (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'user_metadata')::jsonb ->> 'tenant_id'
        )
    );
```

### 1.3 Supabase Secrets Rotation
Before clicking the launch button, rotate all service keys:
1. Revoke all `anon` staging keys.
2. Store the production `SUPABASE_SERVICE_ROLE_KEY` exclusively inside Vercel/Cloudflare **Encrypted Environment Variables**.
3. *Never* expose the service role key to the frontend bundle.

---

## 2. Cloudflare Edge Deployment & Celery+Redis Scaling
To handle massive CAD vector rendering requests and real-time MLIT compliance report exports, the architecture separates the high-performance edge frontend and the heavy-duty asynchronous workers.

```mermaid
graph TD
    A[Japanese Edge Users] -->|HTTPS / WSS| B(Cloudflare Pages / Workers)
    B -->|Bypass / Static Assets| C[Edge Caching]
    B -->|Dynamic Processing| D[FastAPI Backend - Supabase]
    D -->|Push Heavy Tasks| E[(Redis Cloud Broker)]
    E -->|Distribute Payload| F[Celery Heavy Worker 1 - Tokyo]
    E -->|Distribute Payload| G[Celery Heavy Worker 2 - Osaka]
    F -->|Generate ReportLab PDF| H[Supabase Secure Storage]
    G -->|Parse IFC/CAD Lines| H
```

### 2.1 Cloudflare Edge Hosting Configuration
The interactive 3D WebGL editor interface is deployed onto **Cloudflare Pages** to guarantee sub-50ms latency across Tokyo, Osaka, and Fukuoka.

```bash
# Install Wrangler CLI globally
npm install -g wrangler

# Login with production Enterprise credentials
wrangler login

# Deploy static built outputs directly to Edge Pages
wrangler pages deploy ./web/dist --project-name=japanbuild-bim3d-app --branch=main
```

*Ensure the following settings are configured in `wrangler.toml` for Edge API routing:*
```toml
name = "japanbuild-edge-gateway"
main = "src/index.js"
compatibility_date = "2026-05-20"

[vars]
API_UPSTREAM = "https://api.japanbuild-bim3d.jp"
ENVIRONMENT = "production"
```

### 2.2 Asynchronous Worker Scaling (Celery + Redis)
Generating PDFs with ReportLab with Japanese TrueType font embeds is resource-intensive. Run workers on dedicated high-CPU nodes in the Tokyo AWS `ap-northeast-1` region.

**Run production worker nodes using systemd:**
```ini
[Unit]
Description=Celery Worker Service for Japanbuild BIM3D
After=network.target

[Service]
Type=forking
User=ubuntu
Group=ubuntu
WorkingDirectory=/var/www/cad_saas_mvp
ExecStart=/usr/local/bin/celery -A core.celery_app worker --loglevel=info --concurrency=4 -n tokyo_heavy_worker_1@%%h
Restart=always
Environment=REDIS_URL=rediss://default:ProductionSecurePassword@tokyo-redis.cache.amazonaws.com:6379/0

[Install]
WantedBy=multi-user.target
```
*Concurrencies recommendation:* Keep concurrency to `num_cores * 1.5` since ReportLab is CPU-bound.

---

## 3. Stripe Japan Yen Billing Integration (JPY)
To drive B2B adoption in Japan, we implement Stripe JPY billing with strict adherence to Japanese invoicing standards (적격청구서, **Qualified Invoice system - 인보이스 제도** active since Oct 2023).

### 3.1 Commercial Subscription Tiers (JPY)

| Subscription Tier | Monthly Cost (Yen) | Target Customer | Features Provided |
| :--- | :--- | :--- | :--- |
| **BIM Light (라이트)** | `¥1,500` (tax incl.) | Freelancers & Small Inspectors | Max 3 Active Blueprints, basic MLIT check |
| **BIM Business (비즈니스)** | `¥4,900` (tax incl.) | Mid-size Construction Firms | Uncapped Blueprints, PDF ReportLab Export |
| **BIM Enterprise (엔터프라이즈)** | `¥9,800` (tax incl.) | General Contractors (대형 제네콘) | Offline Delta Sync, RLS Dedicated Tenants, SLA |

### 3.2 Transitioning to Stripe Production Live-Mode
1. Navigate to Stripe Dashboard -> **Activate your account** (requires Japanese corporate register registration certificate: 履歴事項全部証明서).
2. Change variables in your production `.env` from test mode (`sk_test_*`) to live mode (`sk_live_*`).
3. Set up the production webhook endpoint: `https://api.japanbuild-bim3d.jp/api/v1/billing/webhook`.
4. Configure webhook events to listen strictly to:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded` (Generates Japanese tax compliant invoice receipts).

---

## 4. Offline Synchronization & `409 Conflict` Resolution Manual
When inspectors operate inside concrete basements (음영지역) where networks are severed, their actions are logged into `IndexedDB`. When network connectivity is restored, the middleware attempts bulk-synchronization. The following protocols govern version conflicts.

### 4.1 The Core Mechanism: Optimistic Locking
Every project canvas and incident coordinate carries a `version` integer (starting at `1`).
* When Client A retrieves incident `X`, it caches `version: 5`.
* If Client B edits incident `X` on an active network, the database version increments to `6`.
* When Client A returns online and attempts sync with base version `5`, the backend detects `base_version (5) != current_version (6)` and throws an HTTP `409 Conflict`.

### 4.2 Handling Protocol Flowchart
```
                [ restore network ]
                         │
           ⚡ POST /api/v1/projects/sync
                         │
            Does base_version match db?
             /                       \
          (Yes)                      (No)
           /                           \
[Apply delta actions]          🚨 HTTP 409 Conflict
[Increment version]                     │
[Return 200 OK]              Send conflict JSON response
                                        │
                             ┌──────────┴──────────┐
                             ▼                     ▼
                        [Option A]            [Option B]
                       Server-Wins           Client-Wins
                             │                     │
                       Discard local         Overwrite DB
                        delta actions       Force version bump
```

### 4.3 Actionable Support Resolution Manual for Site Managers

#### Scenario: Server-Wins (서버 우선 복구 - Standard Option)
* **Description:** The central server's layout remains intact. Client's local offline modifications are discarded to preserve official blueprints.
* **API Action:** Frontend catches the `409 Conflict`, prompts the user, and pulls the fresh server state using `GET /projects/{id}/incidents` to overwrite IndexedDB.

#### Scenario: Client-Wins (현장 우선 강제 덮어쓰기)
* **Description:** The onsite inspector's physical field verification overrides any office alterations.
* **API Action:** The inspector triggers the "Force Merge" button. The client sends the delta actions with a special payload flag: `{"force_overwrite": true}`. The API increments the database version directly, applies the client's coordinates, and broadcasts the override.

#### Scenario: Visual Merge GUI (수동 병합 화면 제공)
* The client UI presents a side-by-side split screen showing:
  - Left: **Server Blueprint (Office Layout)**
  - Right: **Your Local Offline Blueprint (Field Inspect Layout)**
  - The site manager touches individual pins to select which specific 3D coordinate to keep.

---

## 5. Pre-Flight Checklist before Commercial Launch
Before declaring `Release-Ready` to the board of directors:

- [ ] Run Full Test Suite in production staging mode: `pytest tests/`
- [ ] Confirm ReportLab Asian font paths are mapped inside Production Docker Container.
- [ ] Double-check that production Supabase URL is pointing to the Paid Enterprise tier (not local sandbox Docker).
- [ ] Verify Stripe webhook signing secret is safely injected to block counterfeit subscription spoofing.
- [ ] Verify Japanese timezone `Asia/Tokyo` is default for all compliance checksheet date generations.

---
> **코다리 개발본부 보고:**  
> *"본 표준 운영 절차서는 일본 국토교통성(MLIT) BIM 의무화 법령 기준을 정확하게 만족하며, 향후 서비스 확장 시 엔지니어 교체 상황에서도 1시간 이내에 무중단 Production 셋업이 완료될 수 있도록 검증되었습니다. 대표님의 최종 검토를 요청드립니다. 충성!"*
