from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_is_local_and_database_is_ready(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["bind_host"] == "127.0.0.1"
    assert payload["database"]["migration_rows"] == 1
    assert payload["database"]["tables"] == 31
    assert payload["database"]["pragmas"] == {
        "foreign_keys": 1,
        "journal_mode": "wal",
        "synchronous": 2,
        "busy_timeout": 5000,
    }


def test_dashboard_and_security_headers(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Universal AI Cartoon Studio" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "style-src 'self' 'unsafe-inline'" in response.headers["content-security-policy"]
    assert "script-src 'self'" in response.headers["content-security-policy"]


def test_untrusted_host_is_rejected(client: TestClient) -> None:
    response = client.get("/api/health", headers={"host": "studio.example.com"})
    assert response.status_code == 400
