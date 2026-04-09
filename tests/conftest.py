import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def pytest_configure(config):
    # Pierwszy import testSite1 (np. testy jednostkowe) nie powinien dotykać Sense HAT ani pisać sekretu na dysk.
    os.environ.setdefault("SENSORPI_TESTING", "1")
    os.environ.setdefault("SENSORPI_SENSOR", "none")
    os.environ.setdefault("SENSORPI_SECRET_KEY", "pytest-import-secret")


@pytest.fixture()
def app_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Import the app module with test-specific ENV so that:
    - DB uses an isolated sqlite file
    - sensor provider is disabled (no Sense HAT required)
    - CSRF disabled for form POST tests
    """
    db_path = tmp_path / "test_app.db"
    monkeypatch.setenv("SENSORPI_TESTING", "1")
    monkeypatch.setenv("SENSORPI_SENSOR", "none")
    monkeypatch.setenv("SENSORPI_DB_URI", "sqlite:///" + str(db_path).replace("\\", "/"))
    monkeypatch.setenv("SENSORPI_SECRET_KEY", "test-secret-key")

    import importlib

    import testSite1

    importlib.reload(testSite1)
    return testSite1


@pytest.fixture()
def app(app_module):
    return app_module.app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app_module):
    return app_module.dbl


@pytest.fixture()
def create_user(app_module, db):
    def _create(username="alice", email="alice@example.com", password="password123"):
        with app_module.app.app_context():
            u = app_module.User(username=username, email=email)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            return u

    return _create

