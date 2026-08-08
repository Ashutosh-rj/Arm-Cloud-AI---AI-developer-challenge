import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.validators import validate_model_url, validate_run_id

client = TestClient(app)

def test_health_check():
    # Since DB and Redis are not mocked, it might return 503 degraded, which is expected
    response = client.get("/health")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "InferaV22"

def test_validate_model_url_valid():
    assert validate_model_url("meta-llama/Llama-3.2-3B-Instruct") == "meta-llama/Llama-3.2-3B-Instruct"
    assert validate_model_url("https://huggingface.co/model.gguf") == "https://huggingface.co/model.gguf"

def test_validate_model_url_ssrf():
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        validate_model_url("https://169.254.169.254/meta-data.gguf")
    with pytest.raises(HTTPException):
        validate_model_url("https://localhost/test.gguf")

def test_validate_model_url_traversal():
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        validate_model_url("meta-llama/../../etc/passwd")

def test_validate_run_id():
    import uuid
    valid_id = str(uuid.uuid4())
    assert validate_run_id(valid_id) == valid_id
    
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        validate_run_id("invalid-uuid-string")
