from typing import List, Optional
import os
from datetime import date
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import dotenv

# Explicitly load backend/.env into os.environ for runtime services and external connectors
_env_candidates = [
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
    Path(".env").resolve(),
]
for _ep in _env_candidates:
    if _ep.exists():
        dotenv.load_dotenv(_ep, override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[
            str(Path(__file__).resolve().parent.parent / ".env"),
            str(Path(__file__).resolve().parent.parent.parent / ".env"),
            ".env",
        ],
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database
    database_url: str = "sqlite:///./manufacturing.db"
    readonly_database_url: Optional[str] = None

    # Reference Date for business datasets and risk calculation
    reference_date: date = date.today()
    as_of_date: Optional[date] = None

    # Application
    environment: str = "development"
    port: int = 8000
    host: str = "0.0.0.0"

    # Security
    secret_key: str = "super-secret-key-for-jwt-customer-order-management-agent-2026"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cors_origins: str = (
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,"
        "https://customer-order-management-two.vercel.app"
    )

    # Rate Limiting
    rate_limit_login_max: int = 10
    rate_limit_login_window_sec: int = 60
    rate_limit_ai_max: int = 30
    rate_limit_ai_window_sec: int = 60

    # Agent Autonomous Automation Settings
    monitoring_interval_seconds: int = 86400  # Runs once every 24 hours (86,400 seconds)
    intake_poll_seconds: int = 300
    agent2_autonomous_enabled: bool = False
    monitoring_agent_mode: str = "agentic"  # "rules" | "agentic"
    monitoring_max_llm_calls_per_cycle: int = 50
    feasibility_agent_mode: str = "agentic"  # "rules" | "agentic"

    # Automated Commercial Approval Policy (Permanently disabled: all orders require human approval)
    auto_approve_enabled: bool = False
    auto_approve_max_value_inr: float = 0.0
    auto_approve_max_per_day: int = 0

    # Agent 3 Corrective Action Policy & Caps
    agent3_auto_execute_actions: str = "REQUEST_REASSESSMENT,REQUEST_EXPEDITE,REQUEST_CARRIER_UPGRADE"  # Comma-separated list
    agent3_max_actions_per_order: int = 5
    agent3_max_actions_per_day: int = 50

    # Cross-Cutting Limits & Boundary Controls
    max_llm_calls_per_hour: int = 100
    max_auto_actions_per_day: int = 50
    max_cost_per_cycle: float = 5.0

    # External Multi-Agent Database URLs (Strictly Read-Only)
    agent_01_prod_planning_db_url: Optional[str] = None
    agent_03_oee_db_url: Optional[str] = None
    agent_07_ecm_db_url: Optional[str] = None
    agent_08_traceability_db_url: str = (
        "postgresql://neondb_owner:npg_0VrFXEB2pCNQ@ep-snowy-sea-aoujn0yz-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    )
    quality_genealogy_db_url: Optional[str] = None
    agent_09_inventory_db_url: Optional[str] = None
    agent_10_supplier_db_url: Optional[str] = None
    agent_12_logistics_db_url: Optional[str] = None
    agent_13_energy_db_url: Optional[str] = None
    agent_14_ehs_db_url: Optional[str] = None
    agent_16_cost_db_url: Optional[str] = None
    agent_18_customer_order_db_url: Optional[str] = None
    vision_ai_inspection_db_url: Optional[str] = None

    # Domo AI
    domo_subdomain: Optional[str] = "gwcteq-partner"
    domo_token: Optional[str] = None
    domo_model: Optional[str] = "domo.domo_ai.domogpt-small-v2.1:anthropic"

    # Data
    data_dir: str = "../data/data"

    # Seed credentials (loaded strictly from environment variables)
    admin_email: str = "admin@manufacturing.com"
    admin_password: str = "DevAdminSecret123!"
    admin_full_name: str = "System Administrator"

    demo_email: str = "demo@manufacturing.com"
    demo_password: str = "DevDemoSecret123!"
    demo_full_name: str = "Demo Operations Manager"

    # Default alert routing email
    default_alert_email: str = "dyfs2m763cn7s2uz@ethereal.email"

    # SMTP Email Configuration
    smtp_host: Optional[str] = "smtp.ethereal.email"
    smtp_port: int = 587
    smtp_user: Optional[str] = "dyfs2m763cn7s2uz@ethereal.email"
    smtp_password: Optional[str] = "KFHKGSc119pe56eY4f"
    smtp_from: str = "Manufacturing 360 <dyfs2m763cn7s2uz@ethereal.email>"

    @property
    def cors_origin_list(self) -> List[str]:
        return [orig.strip() for orig in self.cors_origins.split(",") if orig.strip()]

    @property
    def effective_reference_date(self) -> date:
        if self.as_of_date:
            return self.as_of_date
        return self.reference_date

    @property
    def normalized_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://") and not url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def normalized_readonly_database_url(self) -> str:
        if self.readonly_database_url:
            url = self.readonly_database_url
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg://", 1)
            elif url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            return url
        return self.normalized_database_url

    def resolve_data_path(self, filename: str) -> Path:
        # Check configured data_dir, current dir data/data, parent dir data/data
        candidates = [
            Path(self.data_dir) / filename,
            Path("data/data") / filename,
            Path("../data/data") / filename,
            Path("data") / filename,
            Path("../data") / filename,
        ]
        for p in candidates:
            if p.exists():
                return p.resolve()
        # Fallback to candidate 0
        return candidates[0].resolve()


settings = Settings()

