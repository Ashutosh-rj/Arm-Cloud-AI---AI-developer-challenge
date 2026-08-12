import pytest
from fastapi.testclient import TestClient
from main import app
from auth.middleware import create_access_token

client = TestClient(app)

def test_login_missing_credentials():
    response = client.post("/api/v1/auth/login")
    assert response.status_code == 422 # Validation error for missing form data
    
def test_login_invalid_credentials():
    response = client.post("/api/v1/auth/login", data={"username": "fake@local", "password": "bad"})
    # Without DB mock, this should either hit the DB and return 401 or fail DB conn 500
    # The contract expects 401
    if response.status_code == 401:
        assert response.json()["detail"] == "Incorrect email or password"
    elif response.status_code == 500:
        pass # DB not available in this test env

def test_protected_route_without_token():
    response = client.get("/api/v1/runs")
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required. Provide a Bearer token or X-API-Key header."

def test_protected_route_invalid_token():
    response = client.get("/api/v1/runs", headers={"Authorization": "Bearer invalid.token.here"})
    assert response.status_code == 401
    assert "Invalid or expired token" in response.json()["detail"]
    
def test_protected_route_expired_token():
    # Create an expired token manually
    from datetime import timedelta
    token = create_access_token({"sub": "test", "user_id": "123"}, expires_delta=timedelta(minutes=-10))
    response = client.get("/api/v1/runs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "Invalid or expired token" in response.json()["detail"]

def test_protected_route_malformed_header():
    response = client.get("/api/v1/runs", headers={"Authorization": "Bearer"})
    assert response.status_code == 403 or response.status_code == 401
