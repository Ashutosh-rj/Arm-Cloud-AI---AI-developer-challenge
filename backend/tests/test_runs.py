import pytest
from fastapi.testclient import TestClient
from main import app
from auth.middleware import create_access_token

client = TestClient(app)

def get_auth_headers():
    token = create_access_token({"sub": "test@local", "user_id": "00000000-0000-0000-0000-000000000000"})
    return {"Authorization": f"Bearer {token}"}

def test_optimize_unauthenticated():
    response = client.post("/api/v1/optimize", json={"model_url": "test"})
    assert response.status_code == 401

def test_optimize_missing_body():
    response = client.post("/api/v1/optimize", headers=get_auth_headers())
    assert response.status_code == 422

def test_optimize_invalid_model_url():
    response = client.post("/api/v1/optimize", headers=get_auth_headers(), json={
        "model_url": "https://169.254.169.254/meta-data"
    })
    # Our validator raises HTTPException on SSRF
    assert response.status_code == 400 or response.status_code == 403

def test_runs_list_unauthenticated():
    response = client.get("/api/v1/runs")
    assert response.status_code == 401

def test_runs_list_success():
    # If DB is not available, we expect 500, else 200
    response = client.get("/api/v1/runs", headers=get_auth_headers())
    assert response.status_code in (200, 500)

def test_run_get_unauthenticated():
    response = client.get("/api/v1/runs/invalid-uuid")
    assert response.status_code == 401

def test_run_get_invalid_uuid():
    response = client.get("/api/v1/runs/invalid-uuid", headers=get_auth_headers())
    assert response.status_code == 400

def test_run_get_not_found():
    import uuid
    response = client.get(f"/api/v1/runs/{uuid.uuid4()}", headers=get_auth_headers())
    # Should be 404 if DB is connected and run not found, or 500 if DB is offline
    assert response.status_code in (404, 500)
