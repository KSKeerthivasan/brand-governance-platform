import pytest
import os
import sys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_DB_URL = "sqlite:///./test_inkloom.db"
os.environ["DATABASE_URL"] = TEST_DB_URL

from app.database import Base, get_db
from app.main import app
from seed import seed_freshsip_data
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    
    # Override app get_db
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    
    # Seed data into test database
    seed_session = TestingSessionLocal()
    seed_freshsip_data(session=seed_session)
    seed_session.close()

    yield

    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    try:
        if os.path.exists("./test_inkloom.db"):
            os.remove("./test_inkloom.db")
    except Exception:
        pass

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_tokens(client):
    """
    Returns authenticated bearer tokens for all 4 roles.
    """
    roles = ["org_admin", "knowledge_reviewer", "content_creator", "approval_manager"]
    tokens = {}
    for role in roles:
        res = client.post("/api/v1/auth/dev-login", json={"role": role, "organization_slug": "freshsip"})
        assert res.status_code == 200, f"Failed dev-login for {role}: {res.text}"
        data = res.json()
        tokens[role] = {
            "token": data["access_token"],
            "org_id": data["organization_id"],
            "headers": {
                "Authorization": f"Bearer {data['access_token']}",
                "X-Organization-Id": data["organization_id"]
            }
        }
    return tokens
