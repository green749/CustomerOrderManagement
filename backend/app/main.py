import logging
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .database import engine, Base, get_db, SessionLocal
from .models import (
    DimCustomer,
    DimProduct,
    DimPlant,
    FactCustomerOrder,
    FactProductionOrder,
    FactInventoryDailySnapshot,
    FactQualityInspection,
    FactShipmentMilestone,
    User,
    RefreshToken,
    Conversation,
    Message,
)
from .middleware import (
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    ETagCacheMiddleware,
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from .routes import (
    auth_router,
    dashboard_router,
    orders_router,
    inventory_router,
    conversations_router,
    agent_router,
    agents_router,
    allocation_router,
    commitments_router,
    kpis_router,
    feasibility_router,
    monitoring_router,
    alerts_router,
    actions_router,
    customers_router,
)
from .routes.connectors import connectors_router
from .routes.admin import admin_router
from .services.email_service import EmailService
from .services.auth_service import ensure_seed_users
from .services.scheduler_service import scheduler
from .services.intake_service import intake_watcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Manufacturing 360 Three-Agent Backend...")
    # Initialize schema tables if they do not exist
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema verified/created successfully.")
    except Exception as e:
        logger.warning(f"Database auto-creation warning (handled by migrations if configured): {e}")

    # Seed default department contacts and ensure default users exist with configured passwords
    try:
        seed_db = SessionLocal()
        EmailService.seed_default_contacts(seed_db)
        ensure_seed_users(seed_db)
        seed_db.close()
    except Exception as e:
        logger.warning(f"Default contacts/users seed note: {e}")

    # Start Agent 3's background monitoring scheduler and Agent 2's intake watcher (skip auto-threads during testing)
    if "pytest" not in sys.modules and not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            scheduler.start()
            logger.info("Agent 3 Background Monitoring Scheduler activated.")
        except Exception as e:
            logger.warning(f"Scheduler activation note: {e}")
        try:
            intake_watcher.start()
            logger.info("Agent 2 Background Intake Watcher activated.")
        except Exception as e:
            logger.warning(f"Intake watcher activation note: {e}")
    else:
        logger.info("Test environment detected; background scheduler/watcher auto-threads deferred.")

    yield

    logger.info("Shutting down Manufacturing 360 Three-Agent Backend...")
    try:
        scheduler.stop()
    except Exception as e:
        logger.warning(f"Scheduler stop note: {e}")
    try:
        intake_watcher.stop()
    except Exception as e:
        logger.warning(f"Intake watcher stop note: {e}")


app = FastAPI(
    title="Customer Order Management Agent API",
    description="Intelligent manufacturing customer order tracking, risk assessment, and Domo AI agent backend.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Exception handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# Middlewares (executed in reverse order of addition)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(ETagCacheMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Content-Disposition"],
)
app.add_middleware(RequestIDMiddleware)

# Include Routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(orders_router)
app.include_router(inventory_router)
app.include_router(conversations_router)
app.include_router(agent_router)
app.include_router(agents_router)
app.include_router(allocation_router)
app.include_router(commitments_router)
app.include_router(kpis_router)
app.include_router(feasibility_router)
app.include_router(monitoring_router)
app.include_router(alerts_router)
app.include_router(actions_router)
app.include_router(customers_router)
app.include_router(connectors_router)
app.include_router(admin_router)


@app.get("/", tags=["Health"])
def root():
    return {
        "service": "Customer Order Management Agent API",
        "version": "1.0.0",
        "status": "online",
        "documentation": "/api/docs",
    }


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint to verify API and database connectivity."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if "unhealthy" not in db_status else "degraded",
        "database": db_status,
        "environment": settings.environment,
    }

