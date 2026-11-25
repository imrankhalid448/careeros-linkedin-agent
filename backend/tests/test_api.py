import sys
from pathlib import Path
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import init_db
from app.main import app


init_db()
client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_connectors_registry():
    resp = client.get("/api/connectors")
    assert resp.status_code == 200
    data = resp.json()
    assert any(c["platform"] == "linkedin" for c in data)


def test_profile_and_notes_endpoints():
    prof = client.get("/api/profile")
    assert prof.status_code == 200
    assert "target_roles" in prof.json()

    notes = client.get("/api/profile/notes")
    assert notes.status_code == 200
    assert isinstance(notes.json(), list)


def test_jobs_and_posts_endpoints():
    assert client.get("/api/jobs").status_code == 200
    assert client.get("/api/content/posts").status_code == 200
    assert client.get("/api/content/comments").status_code == 200
    assert client.get("/api/settings").status_code == 200
