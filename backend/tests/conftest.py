import pytest
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend root is on sys.path
backend_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_path))

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.scripts.seed import seed_database
from app.services.auth_service import create_access_token
from app.models.auth import User

# Use in-memory SQLite database for test isolation
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Seed test database once for test session."""
    # Temporarily bind test engine
    import app.database
    import app.scripts.seed
    
    app.database.engine = test_engine
    app.database.SessionLocal = TestingSessionLocal
    app.scripts.seed.engine = test_engine
    app.scripts.seed.SessionLocal = TestingSessionLocal
    
    Base.metadata.create_all(bind=test_engine)
    seed_database(verbose=False)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Provide clean database session for test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(db_session):
    """Provide Bearer auth headers for the admin user."""
    admin = db_session.query(User).filter(User.email == settings.admin_email).first()
    token = create_access_token(admin)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def demo_headers(db_session):
    """Provide Bearer auth headers for the demo manager user."""
    demo = db_session.query(User).filter(User.email == settings.demo_email).first()
    token = create_access_token(demo)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_user(db_session):
    """Provide standard test user (admin or operator)."""
    user = db_session.query(User).filter(User.email == settings.admin_email).first()
    if not user:
        user = db_session.query(User).first()
    return user


@pytest.fixture
def test_manager(db_session):
    """Provide manager/admin user for approvals."""
    user = db_session.query(User).filter(User.role.in_(["manager", "admin"])).first()
    if not user:
        user = db_session.query(User).first()
    return user


