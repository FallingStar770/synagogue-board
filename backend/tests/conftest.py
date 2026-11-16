import os
import tempfile

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://synagogue:devpass-local-only@127.0.0.1:5432/synagogue_test")
os.environ["MEDIA_DIR"] = tempfile.mkdtemp(prefix="sdb-media-")
os.environ["SNAPSHOT_DAYS"] = "40"
os.environ["LOGIN_MAX_FAILURES"] = "5"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal, get_engine  # noqa: E402

ADMIN = ("admin", "Admin12345!")


@pytest.fixture(scope="session", autouse=True)
def database():
    eng = get_engine()
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    command.upgrade(cfg, "head")
    from app.seed import create_admin, seed_base, seed_demo
    with SessionLocal() as db:
        seed_base(db)
        seed_demo(db)
        create_admin(db, *ADMIN)
    yield


@pytest.fixture()
def client():
    from app.main import app
    from app.security import login_limiter
    login_limiter._fails.clear()
    return TestClient(app)


class Admin:
    def __init__(self, client):
        self.c = client
        r = client.post("/api/v1/auth/login", json={"username": ADMIN[0], "password": ADMIN[1]})
        assert r.status_code == 200, r.text
        self.csrf = r.json()["csrf_token"]

    def h(self):
        return {"X-CSRF-Token": self.csrf}

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, **kw):
        return self.c.post(url, headers=self.h(), **kw)

    def patch(self, url, **kw):
        return self.c.patch(url, headers=self.h(), **kw)

    def put(self, url, **kw):
        return self.c.put(url, headers=self.h(), **kw)

    def delete(self, url, **kw):
        return self.c.delete(url, headers=self.h(), **kw)


@pytest.fixture()
def admin(client):
    return Admin(client)
