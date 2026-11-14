"""Adversarial requests use synthetic inputs and isolated temporary databases."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from backend import app as site, auth, security


PREFS = {"level": "beginner", "goal": "health", "days_per_week": 2, "minutes_per_session": 20}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("GYMPATH_DATA_DIR", str(tmp_path / "security-data"))
    monkeypatch.setattr(auth, "rate_limiter", auth.AuthRateLimiter(limit=100))
    with TestClient(site.app, headers={"Origin": "http://testserver"}) as connection:
        yield connection


@pytest.mark.parametrize("path", ["/", "/account.html", "/api/health", "/api/plans", "/missing", "/backend/auth.py"])
def test_protections_cover_public_private_and_error_responses(client, path):
    response = client.get(path)
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    policy = response.headers["content-security-policy"]
    assert "script-src 'self'" in policy and "frame-ancestors 'none'" in policy
    assert "form-action 'none'" in policy and "unsafe-inline" not in policy
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
    if path.startswith("/api/"):
        assert response.headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in response.headers


def test_hsts_uses_actual_https_not_untrusted_forwarded_header(client):
    response = client.get("/", headers={"X-Forwarded-Proto": "https"})
    assert "strict-transport-security" not in response.headers
    with TestClient(site.app, base_url="https://testserver") as secure:
        assert secure.get("/").headers["strict-transport-security"] == "max-age=31536000"


def test_configured_exact_host_rejects_attacker_and_suffix(monkeypatch, client):
    monkeypatch.setenv("GYMPATH_ALLOWED_HOSTS", "testserver,localhost")
    assert client.get("/", headers={"Host": "testserver:8081"}).status_code == 200
    for host in ["evil.example", "testserver.evil.example", "testserver@evil.example", "testserver/path"]:
        response = client.get("/", headers={"Host": host})
        assert response.status_code == 400
        assert host not in response.text


def test_duplicate_host_and_origin_rejected(client):
    assert client.get("/", headers=[("Host", "testserver"), ("Host", "evil.example")]).status_code == 400
    assert client.post("/api/plan", json=PREFS, headers=[("Origin", "http://testserver"), ("Origin", "https://evil.example")]).status_code == 400


def test_extremely_long_content_length_is_a_protected_error(client):
    response = client.post("/api/plan", content=b"{}", headers={"Content-Type": "application/json", "Content-Length": "9" * 5000})
    assert response.status_code == 413
    assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.parametrize("path", ["/api/plan", "/api/auth/register", "/api/auth/login", "/api/plans"])
def test_oversized_bodies_rejected_before_endpoint_and_without_echo(client, path):
    response = client.post(path, content=b"secret-sentinel" * 400, headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert "secret-sentinel" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert not auth.database_path().exists()


@pytest.mark.parametrize("content_type", ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data", "text/javascript"])
def test_simple_cross_site_content_types_cannot_invoke_json_endpoints(client, content_type):
    assert client.post("/api/plan", content=json.dumps(PREFS), headers={"Content-Type": content_type}).status_code == 415


def test_compressed_payloads_and_duplicate_json_keys_rejected(client):
    assert client.post("/api/plan", json=PREFS, headers={"Content-Encoding": "gzip"}).status_code == 415
    response = client.post("/api/plan", content='{"level":"beginner","level":"experienced"}', headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "experienced" not in response.text


@pytest.mark.parametrize("payload", [b'\xff', b'{"private-sentinel":', b'[' * 1500 + b']' * 1500])
def test_malformed_encoding_json_and_deep_nesting_are_clean_errors(client, payload):
    response = client.post("/api/plan", content=payload, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "Traceback" not in response.text and "private-sentinel" not in response.text


def test_api_budget_cannot_be_reset_by_client_forwarded_headers(monkeypatch, client):
    monkeypatch.setattr(security, "api_rate_limiter", auth.AuthRateLimiter(limit=2, window_seconds=60))
    for address in ["192.0.2.1", "192.0.2.2"]:
        assert client.get("/api/health", headers={"X-Forwarded-For": address}).status_code == 200
    response = client.get("/api/health", headers={"X-Forwarded-For": "192.0.2.3"})
    assert response.status_code == 429 and response.headers["retry-after"] == "60"
    assert client.get("/").status_code == 200


def test_password_work_concurrency_rejects_without_hashing(monkeypatch, client):
    assert security.request_budget.acquire("auth")
    assert security.request_budget.acquire("auth")
    called = []
    monkeypatch.setattr(auth, "register", lambda *args: called.append(args))
    response = client.post("/api/auth/register", json={"username": "synthetic", "password": "SafePass8"})
    assert response.status_code == 503 and response.headers["retry-after"] == "5"
    assert called == []


def test_storage_failure_is_generic_and_preserves_protection_headers(monkeypatch, client):
    def fail(*args):
        raise auth.StorageUnavailable("private-path-secret")
    monkeypatch.setattr(auth, "session", fail)
    response = client.get("/api/auth/me")
    assert response.status_code == 503
    assert "private-path-secret" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert security.request_budget.active == {"auth": 0, "api": 0}


def test_registration_cap_maps_to_safe_response(monkeypatch, client):
    monkeypatch.setenv("GYMPATH_MAX_ACCOUNTS", "1")
    body = {"username": "first", "password": "SafePass8"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    response = client.post("/api/auth/register", json={**body, "username": "second"})
    assert response.status_code == 503
    assert client.post("/api/auth/login", json=body).status_code == 200


def invoke_stream(chunks, extra_headers=(), failing=False):
    async def run():
        reached = []
        messages = []
        queue = list(chunks)
        async def receive():
            if queue:
                return queue.pop(0)
            return {"type": "http.disconnect"}
        async def send(message):
            messages.append(message)
        async def endpoint(scope, receive, send):
            reached.append(True)
            if failing:
                raise RuntimeError("synthetic-private-secret")
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})
        scope = {"type": "http", "method": "POST", "scheme": "http", "path": "/api/plan", "client": ("192.0.2.90", 1), "headers": [(b"host", b"testserver"), (b"content-type", b"application/json"), *extra_headers]}
        await security.SecurityMiddleware(endpoint)(scope, receive, send)
        return reached, messages
    return asyncio.run(run())


@pytest.mark.parametrize("length_header", [(), ((b"content-length", b"2"),)])
def test_actual_stream_limit_handles_absent_and_dishonest_length(length_header):
    chunks = [{"type": "http.request", "body": b"x" * 2048, "more_body": True}] * 3
    reached, messages = invoke_stream(chunks, length_header)
    assert reached == []
    assert messages[0]["status"] == 413


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS", "POST", "DELETE"])
def test_direct_asgi_empty_content_length_is_rejected_for_every_method(method):
    async def run(method):
        reached = []
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        async def endpoint(scope, receive, send):
            reached.append(True)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        scope = {
            "type": "http", "method": method, "scheme": "http", "path": "/api/health",
            "client": ("192.0.2.91", 1),
            "headers": [(b"host", b"testserver"), (b"content-length", b"")],
        }
        await security.SecurityMiddleware(endpoint)(scope, receive, send)
        return reached, messages

    reached, messages = asyncio.run(run(method))
    assert reached == [] and messages[0]["status"] == 400
    assert dict(messages[0]["headers"])[b"x-frame-options"] == b"DENY"


def test_api_unexpected_exception_is_redacted_and_releases_budget():
    reached, messages = invoke_stream([{"type": "http.request", "body": b"{}", "more_body": False}], failing=True)
    assert reached == [True] and messages[0]["status"] == 500
    assert b"synthetic-private-secret" not in messages[1]["body"]
    assert security.request_budget.active == {"auth": 0, "api": 0}
