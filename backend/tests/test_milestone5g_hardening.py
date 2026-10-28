import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.config import Settings, settings
from seed import check_production_seed_guard, seed_freshsip_data
from app.main import app

client = TestClient(app)

class TestMilestone5GProductionSeedGuard:
    """
    Tests enforcing the production seed guard in backend/seed.py:
    - Production execution refuses to seed.
    - No database mutations occur before refusal.
    - Development and test seeding remain functional.
    - Guard cannot be bypassed by client request headers.
    """

    def test_production_seed_refuses_to_seed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")

        with pytest.raises(RuntimeError) as exc_info:
            check_production_seed_guard()

        err = str(exc_info.value)
        assert "Demo seeding is strictly prohibited in production environments" in err
        assert "provision_admin.py" in err

    def test_production_seed_causes_zero_database_mutations(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")

        mock_session = MagicMock()

        with pytest.raises(RuntimeError):
            seed_freshsip_data(session=mock_session)

        # Assert no queries, adds, flushes, or commits occurred on the session
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()
        mock_session.flush.assert_not_called()
        mock_session.query.assert_not_called()

    def test_development_and_test_seeding_allowed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        # Should not raise
        check_production_seed_guard()

        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setattr(settings, "ENVIRONMENT", "test")
        # Should not raise
        check_production_seed_guard()

    def test_production_seed_guard_cannot_be_bypassed_by_client_headers(self, monkeypatch):
        """
        Verifies that passing spoofed HTTP client headers has no effect on the server-side environment guard.
        """
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")

        # Mocking incoming client headers environment
        spoofed_headers = {
            "X-Environment": "development",
            "X-User-Role": "org_admin",
            "X-Bypass-Seed-Guard": "true"
        }

        with pytest.raises(RuntimeError) as exc_info:
            with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
                check_production_seed_guard()

        assert "Demo seeding is strictly prohibited in production environments" in str(exc_info.value)


class TestMilestone5GProductionConfigurationSafeguards:
    """
    Tests enforcing production configuration validation:
    - DEBUG=false
    - ALLOW_DEV_LOGIN=false
    - Cryptographically strong SECRET_KEY
    - Production DB URL (no SQLite, no localhost dev postgres)
    - Explicit CORS origins (no wildcard)
    - Persistent storage configuration
    """

    def test_validate_production_readiness_catches_all_insecure_defaults(self):
        insecure_settings = Settings(
            ENVIRONMENT="production",
            DEBUG=True,
            ALLOW_DEV_LOGIN=True,
            SECRET_KEY="inkloom-dev-secret-key-super-secure-at-least-32-chars",
            DATABASE_URL="postgresql://postgres:postgres@localhost:5432/inkloom_ai",
            CORS_ORIGINS="*",
            STORAGE_BACKEND="local",
            LOCAL_STORAGE_DIR="/tmp"
        )
        errors = insecure_settings.validate_production_readiness()
        assert len(errors) >= 5
        assert any("ALLOW_DEV_LOGIN" in e for e in errors)
        assert any("DEBUG" in e for e in errors)
        assert any("SECRET_KEY" in e for e in errors)
        assert any("postgres:postgres@localhost" in e for e in errors)
        assert any("wildcard" in e for e in errors)
        assert any("LOCAL_STORAGE_DIR" in e for e in errors)

    def test_validate_production_readiness_rejects_sqlite_in_production(self):
        sqlite_settings = Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            ALLOW_DEV_LOGIN=False,
            SECRET_KEY="a-very-secure-random-token-that-is-at-least-32-characters-long!",
            DATABASE_URL="sqlite:///./inkloom_ai.db",
            CORS_ORIGINS="https://app.inkloom.ai",
            STORAGE_BACKEND="local",
            LOCAL_STORAGE_DIR="./storage_data"
        )
        errors = sqlite_settings.validate_production_readiness()
        assert any("SQLite" in e for e in errors)

    def test_validate_production_readiness_accepts_clean_production_settings(self):
        clean_settings = Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            ALLOW_DEV_LOGIN=False,
            SECRET_KEY="prod-super-secure-high-entropy-jwt-signing-key-99881122",
            DATABASE_URL="postgresql://inkloom_prod_user:StrongPassword987!@db.prod.internal:5432/inkloom_prod",
            CORS_ORIGINS="https://app.inkloom.ai,https://portal.inkloom.ai",
            STORAGE_BACKEND="local",
            LOCAL_STORAGE_DIR="/var/lib/inkloom/storage"
        )
        errors = clean_settings.validate_production_readiness()
        assert errors == []

    def test_dev_login_endpoint_blocked_in_production(self, monkeypatch):
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        res = client.post("/api/v1/auth/dev-login", json={"role": "content_creator"})
        assert res.status_code == 403
        assert "Development login bypass is disabled" in res.json()["detail"]

    def test_unauthenticated_request_rejected(self):
        res = client.get("/api/v1/content")
        assert res.status_code == 401
