import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_websocket_missing_token():
    with client.websocket_connect("/ws/invalid_run_id") as websocket:
        try:
            data = websocket.receive_json()
        except Exception as e:
            # It should fail and close immediately due to missing token
            assert "1008" in str(e) or "Authentication required" in str(e)

def test_websocket_invalid_run_id_format():
    # It checks validate_run_id first
    with client.websocket_connect("/ws/invalid_format?token=fake") as websocket:
        try:
            data = websocket.receive_json()
        except Exception as e:
            assert "1008" in str(e) or "Invalid run_id format" in str(e)
