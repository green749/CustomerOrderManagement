# Customer Order Management Agent - Backend

Production-grade FastAPI backend architected for enterprise manufacturing order tracking, transparent rule-based risk evaluation, and LangChain-powered Domo AI conversational agents.

---

## 1. Architecture & Technology Stack

- **Framework**: Python 3.11+ / FastAPI
- **Database**: Neon PostgreSQL (with dialect-agnostic support for SQLite in local development and testing)
- **ORM**: SQLAlchemy 2.x with connection pooling (`pool_size=10`, `max_overflow=20`, `pool_recycle=300`)
- **Schema Migrations**: Alembic
- **Validation**: Pydantic v2 (ConfigDict, strict type checking)
- **Authentication**: JWT access tokens (~15 min expiry) + Opaque refresh tokens stored as SHA-256 hashes with automatic rotation and revocation
- **Password Security**: Argon2 password hashing
- **AI Agent**: LangChain (`langchain-core`) with custom `DomoTextLLM` wrapper executing a controlled JSON-action / ReAct tool loop
- **Deployment**: Render Web Service (`render.yaml`)

---

## 2. Directory Structure

```text
backend/
├── alembic/                       # Alembic database migration environment
│   ├── versions/                  # Revision versions (e.g. initial_schema.py)
│   ├── env.py                     # Alembic configuration
│   └── script.py.mako             # Revision template
├── app/
│   ├── __init__.py
│   ├── config.py                  # Pydantic BaseSettings environment config
│   ├── database.py                # SQLAlchemy engine, session maker, base
│   ├── main.py                    # FastAPI application, middlewares, lifespans
│   ├── models/                    # SQLAlchemy declarative models
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── business.py            # 8 Business datasets + read-only mutation guards
│   │   ├── auth.py                # Users & RefreshTokens
│   │   └── chat.py                # Conversations & Messages (with tool steps)
│   ├── schemas/                   # Pydantic v2 schemas
│   │   ├── __init__.py
│   │   ├── common.py              # Pagination, Standard, and Error responses
│   │   ├── auth.py                # Login, Token, and User DTOs
│   │   ├── order.py               # Customer order list, detail, timeline DTOs
│   │   ├── dashboard.py           # KPIs, status breakdowns, at-risk DTOs
│   │   ├── inventory.py           # Raw material inventory DTOs
│   │   └── chat.py                # Conversations, messages, tool traces DTOs
│   ├── controllers/               # Controller coordination layer
│   │   └── __init__.py
│   ├── services/                  # Business logic services
│   │   ├── __init__.py
│   │   ├── auth_service.py        # Argon2 hashing, JWT signing, token rotation
│   │   ├── risk_service.py        # Transparent rule-based order risk analyzer
│   │   ├── order_service.py       # Order listing, detail, and timeline builder
│   │   ├── inventory_service.py   # Raw material calculations (available qty)
│   │   ├── dashboard_service.py   # Operational summary & at-risk order filtering
│   │   └── chat_service.py        # AI conversation state & execution manager
│   ├── repositories/              # Database data access layer
│   │   ├── __init__.py
│   │   ├── order_repo.py          # Optimized SQL queries & pre-fetches (no N+1)
│   │   ├── inventory_repo.py      # Material snapshot querying
│   │   ├── dashboard_repo.py      # Summary metrics and aggregation
│   │   ├── user_repo.py           # User credential querying
│   │   └── chat_repo.py           # Message & conversation persistence
│   ├── routes/                    # FastAPI route modules
│   │   ├── __init__.py
│   │   ├── auth.py                # /api/auth routes
│   │   ├── dashboard.py           # /api/dashboard routes
│   │   ├── orders.py              # /api/orders routes
│   │   ├── inventory.py           # /api/inventory routes
│   │   ├── conversations.py       # /api/conversations routes
│   │   └── agent.py               # /api/agent routes
│   ├── middleware/                # Security and operational middlewares
│   │   ├── __init__.py
│   │   ├── request_id.py          # X-Request-ID propagation
│   │   ├── security.py            # Security headers (HSTS, CSP, X-Frame)
│   │   ├── rate_limit.py          # IP-based rate limiter (login & AI)
│   │   └── error_handler.py       # Centralized exception handler (no leaked secrets)
│   ├── agent/                     # Domo AI Agent implementation
│   │   ├── __init__.py
│   │   ├── domo_client.py         # Custom LangChain LLM wrapper for Domo Text API
│   │   ├── prompts.py             # ReAct JSON tool execution prompt templates
│   │   ├── tools.py               # 4 Approved read-only domain service tools
│   │   └── agent_loop.py          # Controlled step loop, JSON parser, and traces
│   └── scripts/
│       ├── __init__.py
│       └── seed.py                # Safe, idempotent bulk importer & user seeder
├── tests/                         # Pytest test suite (24 unit & integration tests)
│   ├── __init__.py
│   ├── conftest.py                # Test fixtures & test DB setup
│   ├── test_auth.py               # Authentication, token rotation, logout tests
│   ├── test_orders.py             # Order querying, details, and timeline tests
│   ├── test_dashboard.py          # Dashboard aggregation & KPI tests
│   ├── test_inventory.py          # Material inventory snapshot tests
│   ├── test_risk.py               # Rule-based delay & consistency tests
│   ├── test_agent.py              # Tool execution & agent conversation tests
│   └── test_import.py             # Row counts & read-only enforcement tests
├── .env.example                   # Environment configuration template
├── alembic.ini                    # Alembic migration configuration
├── requirements.txt               # Pinned backend dependencies
└── README.md
```

---

## 3. Database & Dataset Import

The system imports eight distinct business datasets from original CSV files:
1. **Customers** (`dim_customer.csv`): 4 records
2. **Products** (`dim_product.csv`): 3 records
3. **Plants** (`dim_plant.csv`): 2 records
4. **Customer Orders** (`fact_customer_order.csv`): 1,500 records
5. **Production Orders** (`fact_production_order.csv`): 450 records
6. **Shipment Milestones** (`fact_shipment_milestone.csv`): 1,000 records
7. **Quality Inspections** (`fact_quality_inspection.csv`): 16,000 records
8. **Inventory Daily Snapshots** (`fact_inventory_daily_snapshot.csv`): 6,624 records

### Critical Data Rules Enforced
- **Original CSVs Unaltered**: The source files remain unmodified.
- **No Synthetic Relationships**: In the raw dataset, production orders reference customer order numbers like `CO-10873` which are unlinked to `fact_customer_order` (`CO-000001` - `CO-001500`). The system strictly avoids fabricating relationships and instead surfaces these as explicit **data-quality warnings**.
- **Raw Material Inventory**: Clarified that inventory snapshots represent raw materials (e.g. `MAT-SOC-001`), not finished goods.
- **Read-Only Business Tables**: Event listeners in `app.models.business` prevent application sessions from updating or deleting business records (`PermissionError`).
- **Separate Application Tables**: `users`, `refresh_tokens`, `conversations`, and `messages` are maintained as dedicated application tables.

---

## 4. Transparent Rule-Based Order Risk Analysis

The risk analyzer evaluates each customer order against transparent, deterministic business rules:
- **`ACTUAL_DELAY`**:
  - Current date is past `confirmed_delivery_date` and status is not `DELIVERED`.
  - Carrier shipment milestone has `shipment_status == 'DELAYED'`.
  - Delivered late: `actual_delivery_ts` occurred after `confirmed_delivery_date`.
- **`POTENTIAL_DELAY`**:
  - Delivery due within 3 days but order is still `OPEN` or `CONFIRMED`.
  - Carrier ETA exceeds customer's confirmed delivery date.
- **`UNKNOWN_RISK`**:
  - Order has no matching production order link in manufacturing records to verify production progress.
- **Inconsistency Warnings**:
  - `shipped_qty > order_qty` (over-shipped).
  - Marked `DELIVERED` but `shipped_qty < order_qty` (incomplete fulfillment).
  - Sum of shipment milestone quantities differs from order `shipped_qty`.

---

## 5. Domo AI Agent Implementation

Because the Domo Text Generation API does not support native function calling, the agent implements a custom LangChain LLM wrapper (`DomoTextLLM`) with a controlled JSON-action loop:
- **Model**: `domo.domo_ai.domogpt-small-v2.1:anthropic` via Domo API (`https://gwcteq-partner.domo.com/api/ai/v1/text/generation`).
- **Approved Read-Only Tools**:
  1. `get_order_status(customer_order_id: str)`
  2. `list_at_risk_orders(limit: int = 10, risk_type: str = None)`
  3. `get_customer_summary(customer_id: str)`
  4. `get_order_delay_analysis(customer_order_id: str)`
- **Safety**: Tools execute strictly via verified service functions. Arbitrary SQL execution is disallowed.
- **Observability**: Tool steps, inputs, and outputs are saved in the `messages` table and returned as execution traces in the API response.
- **Offline / Local Dev Fallback**: When Domo API tokens are not provided, an integrated fallback simulator enables seamless local testing and UI development.

---

## 6. Authentication & Security

- **Authentication**: `POST /api/auth/login` issues short-lived JWT access tokens and long-lived opaque refresh tokens.
- **Refresh Token Rotation**: Each refresh request rotates the opaque token, hashes the new value, and revokes the old one. Reusing a revoked token triggers immediate revocation of all sessions for that user.
- **No Public Registration**: Only pre-seeded administrative and demo accounts exist:
  - `admin@manufacturing.com` (System Administrator)
  - `demo@manufacturing.com` (Demo Operations Manager)
- **Security Middlewares**:
  - Security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy`.
  - Request ID middleware: propagates `X-Request-ID` across all logs and responses.
  - Rate limiting: 10 login requests / min, 30 AI requests / min.
  - Centralized exception handlers: Prevents leakage of stack traces or database connection details.

---

## 7. Setup & Local Run Instructions

### 1. Prerequisites
- Python 3.11 or 3.12
- Git

### 2. Install Dependencies
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
To connect to Neon PostgreSQL, set:
```env
DATABASE_URL=postgresql+psycopg://username:password@ep-cool-name-123456.region.aws.neon.tech/dbname?sslmode=require
```
*(If unset, the application defaults to local SQLite `sqlite:///./manufacturing.db` for instant offline testing).*

### 4. Run Alembic Migrations
```bash
alembic -c alembic.ini upgrade head
```

### 5. Seed Database & Import CSVs
```bash
python app/scripts/seed.py
```
This imports all 8 datasets (25,583 total records) and seeds admin and demo users.

### 6. Start the Backend Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Base URL: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/api/docs`
- Health check: `http://localhost:8000/api/health`

### 7. Run Test Suite
```bash
python -m pytest tests -v
```

---

## 8. Render Deployment Instructions

1. Push your repository to GitHub or GitLab.
2. In the [Render Dashboard](https://dashboard.render.com), click **New +** -> **Blueprint**.
3. Select your repository. Render will automatically detect `render.yaml`.
4. Configure the following environment variables in the Render Dashboard:
   - `DATABASE_URL`: Your Neon PostgreSQL connection string (e.g. `postgresql+psycopg://...`).
   - `SECRET_KEY`: A cryptographically secure random string (Render can generate this automatically).
   - `DOMO_TOKEN`: Your Domo AI developer token.
   - `ADMIN_PASSWORD`: Secure password for the admin account.
   - `DEMO_PASSWORD`: Secure password for the demo account.
5. Click **Apply**.
   - Render runs `pip install -r backend/requirements.txt && python backend/app/scripts/seed.py`.
   - The server boots via `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
   - Health check verifies at `/api/health`.

