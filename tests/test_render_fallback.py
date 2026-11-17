import pytest
import socket
import httpx
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException
from app import _get_render_service_candidates, _call_render_service, _default_render_service_url

def test_render_service_default_url():
    url = _default_render_service_url()
    assert "3100" in url

def test_get_render_service_candidates():
    candidates = _get_render_service_candidates()
    assert len(candidates) >= 2
    assert any("localhost:3100" in c for c in candidates)
    assert any("renderer:3100" in c for c in candidates)

@pytest.mark.anyio
async def test_call_render_service_fallback_on_dns_failure():
    # Simulate first candidate failing with socket.gaierror ([Errno 11001] getaddrinfo failed)
    # and second candidate succeeding
    call_count = 0

    class MockResponse:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {"renderId": "mock-render-123", "status": "queued"}

    async def mock_post(url, json=None):
        nonlocal call_count
        call_count += 1
        if "renderer:3100" in url:
            # Simulate Errno 11001
            raise socket.gaierror(11001, "getaddrinfo failed")
        return MockResponse()

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with patch("app._get_render_service_candidates", return_value=["http://renderer:3100", "http://localhost:3100"]):
            res = await _call_render_service("POST", "/render", json_data={"test": True})
            assert res["renderId"] == "mock-render-123"
            assert call_count == 2
