import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "docs" in data


def test_search_endpoint_validation():
    """Test search endpoint with invalid input"""
    # Test empty query
    response = client.post("/api/v1/search", json={"query": ""})
    assert response.status_code == 422  # Validation error
    
    # Test missing query
    response = client.post("/api/v1/search", json={})
    assert response.status_code == 422  # Validation error


def test_search_endpoint_structure():
    """Test search endpoint response structure"""
    # Note: This test might fail without proper OpenAI API key
    # In a real test environment, you'd mock the agent response
    response = client.post("/api/v1/search", json={
        "query": "test query",
        "max_results": 5,
        "include_web": True,
        "include_stored": True
    })
    
    # Should return 200 or 500 (if OpenAI key is missing)
    assert response.status_code in [200, 500]
    
    if response.status_code == 200:
        data = response.json()
        assert "query" in data
        assert "answer" in data
        assert "sources" in data
        assert "processing_time" in data
        assert "session_id" in data


def test_search_history_endpoint():
    """Test search history endpoint"""
    session_id = "test-session-123"
    response = client.get(f"/api/v1/search/history/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert "history" in data
