"""Verify the optional hosting bridge without reading the running site data."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("a2wsgi") is None,
    reason="Install requirements-deploy.txt to check the optional WSGI bridge.",
)


@pytest.fixture
def web_client(tmp_path, monkeypatch):
    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    from backend import auth
    from deployment.pythonanywhere_wsgi import application

    monkeypatch.setenv("GYMPATH_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(auth, "rate_limiter", auth.AuthRateLimiter())
    return Client(application, Response)


BASE = "http://gympath-test.pythonanywhere.com"
ORIGIN = "https://gympath-test.pythonanywhere.com"
PROXY = {"X-Forwarded-Proto": "https", "X-Forwarded-For": "192.0.2.10"}
PREFS = {"level": "beginner", "goal": "health", "days_per_week": 2, "minutes_per_session": 20}


def request(client, method, path, payload=None, csrf=None, origin=ORIGIN):
    headers = {**PROXY, "Origin": origin}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    return client.open(path, method=method, base_url=BASE, json=payload, headers=headers)


def credentials(name):
    return {"username": name, "password": "Deployment-test-password1!"}


def test_https_registration_cookie_and_csrf_survive_the_wsgi_bridge(web_client):
    response = request(web_client, "POST", "/api/auth/register", credentials("wsgiuser"))
    assert response.status_code == 201
    cookie = response.headers["Set-Cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert response.headers["Cache-Control"] == "no-store"
    session = request(web_client, "GET", "/api/auth/me").json
    assert session["user"]["username"] == "wsgiuser"
    assert request(web_client, "POST", "/api/plans", {"preferences": PREFS}).status_code == 403
    assert request(web_client, "POST", "/api/plans", {"preferences": PREFS}, session["csrf_token"], "https://other.example").status_code == 403
    saved = request(web_client, "POST", "/api/plans", {"preferences": PREFS}, session["csrf_token"])
    assert saved.status_code == 201
    record = saved.json
    assert record["plan"]["days_per_week"] == 2
    assert request(web_client, "GET", "/api/plans").json["plans"][0]["id"] == record["id"]
    assert request(web_client, "POST", "/api/auth/logout", csrf=session["csrf_token"]).status_code == 204
    assert request(web_client, "GET", "/api/auth/me").json["user"] is None
    assert request(web_client, "POST", "/api/auth/login", credentials("wsgiuser")).status_code == 200
    assert request(web_client, "GET", "/api/plans").json["plans"][0]["id"] == record["id"]


def test_saved_plan_owner_and_delete_response_through_wsgi(web_client):
    owner = request(web_client, "POST", "/api/auth/register", credentials("owner")).json
    saved = request(web_client, "POST", "/api/plans", {"preferences": PREFS}, owner["csrf_token"]).json
    request(web_client, "POST", "/api/auth/logout", csrf=owner["csrf_token"])
    stranger = request(web_client, "POST", "/api/auth/register", credentials("stranger")).json
    assert request(web_client, "GET", "/api/plans").json["plans"] == []
    assert request(web_client, "DELETE", f"/api/plans/{saved['id']}", csrf=stranger["csrf_token"]).status_code == 404
    owner = request(web_client, "POST", "/api/auth/login", credentials("owner")).json
    assert request(web_client, "DELETE", f"/api/plans/{saved['id']}", csrf=owner["csrf_token"]).status_code == 204
    assert request(web_client, "GET", "/api/plans").json["plans"] == []


def test_wsgi_empty_content_length_supports_me_logout_and_delete(web_client):
    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    from deployment.pythonanywhere_wsgi import application

    empty_requests = []

    def host_supplies_empty_length(environ, start_response):
        method = environ["REQUEST_METHOD"]
        path = environ["PATH_INFO"]
        if method in {"GET", "HEAD", "OPTIONS", "DELETE"} or path == "/api/auth/logout":
            # Inject after Werkzeug builds the request so the empty WSGI
            # value reaches the actual bridge exactly as on the host.
            environ = dict(environ)
            environ["CONTENT_LENGTH"] = ""
            empty_requests.append((method, path))
        return application(environ, start_response)

    hosted = Client(host_supplies_empty_length, Response)
    owner = request(hosted, "POST", "/api/auth/register", credentials("emptylength"))
    assert owner.status_code == 201
    csrf = owner.json["csrf_token"]
    assert request(hosted, "GET", "/api/auth/me").json["user"] == owner.json["user"]
    saved = request(hosted, "POST", "/api/plans", {"preferences": PREFS}, csrf)
    assert saved.status_code == 201
    assert request(hosted, "DELETE", f"/api/plans/{saved.json['id']}", csrf=csrf).status_code == 204
    assert request(hosted, "GET", "/api/plans").json["plans"] == []
    assert request(hosted, "POST", "/api/auth/logout", csrf=csrf).status_code == 204
    assert request(hosted, "GET", "/api/auth/me").json["user"] is None
    assert ("GET", "/api/auth/me") in empty_requests
    assert ("POST", "/api/auth/logout") in empty_requests
    assert ("DELETE", f"/api/plans/{saved.json['id']}") in empty_requests
    # Normalizing an absent WSGI length must not affect a real positive body.
    oversized = request(hosted, "POST", "/api/plan", {"sentinel": "x" * 5000})
    assert oversized.status_code == 413
    assert oversized.headers["X-Frame-Options"] == "DENY"


def test_wsgi_serves_the_four_pages_and_keeps_internal_files_private(web_client):
    for page in ["/", "/demo.html", "/trial.html", "/account.html"]:
        response = request(web_client, "GET", page)
        assert response.status_code == 200
        assert "GYMPATH" in response.get_data(as_text=True)
    for path in ["/backend/auth.py", "/data/gympath.sqlite3", "/deployment/pythonanywhere_wsgi.py", "/docs/HANDOFF.md"]:
        assert request(web_client, "GET", path).status_code == 404
    response = request(web_client, "POST", "/api/plan", PREFS)
    assert response.status_code == 200
    assert response.json["trial_info"]["stores_inputs"] is False


def test_bridge_validates_inputs_without_reflecting_passwords(web_client):
    secret = "too-short"
    response = request(web_client, "POST", "/api/auth/register", {"username": "x", "password": secret})
    assert response.status_code == 422
    assert secret not in json.dumps(response.json)
    assert request(web_client, "POST", "/api/auth/register", credentials("validname"), origin="https://other.example").status_code == 403


def test_wsgi_without_client_port_keeps_rate_limits_separate_by_address(web_client):
    from werkzeug.test import EnvironBuilder

    def failed_login(address):
        builder = EnvironBuilder(
            path="/api/auth/login", method="POST", base_url=BASE,
            json=credentials("missinguser"),
            headers={"Origin": ORIGIN, "X-Forwarded-Proto": "https",
                     "X-Forwarded-For": address},
        )
        environ = builder.get_environ()
        environ.pop("REMOTE_PORT", None)
        return web_client.open(environ)

    for _ in range(10):
        assert failed_login("192.0.2.10").status_code == 401
    assert failed_login("192.0.2.10").status_code == 429
    assert failed_login("192.0.2.11").status_code == 401


def run_worker_probe(source, tmp_path):
    env = os.environ.copy()
    env["GYMPATH_DATA_DIR"] = str(tmp_path)
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        cwd=Path(__file__).resolve().parent.parent, env=env,
        capture_output=True, text=True, check=True, timeout=20,
    )


def test_wsgi_import_starts_no_thread_and_concurrent_first_requests_succeed(tmp_path):
    # A fresh interpreter reproduces master import before any worker request.
    # Actual concurrent HTTP requests exercise the event loop, not a fake bridge.
    result = run_worker_probe("""
        from concurrent.futures import ThreadPoolExecutor
        import threading
        import time
        from unittest.mock import patch
        from werkzeug.test import Client
        from werkzeug.wrappers import Response

        with patch.object(threading.Thread, "start", side_effect=AssertionError("thread started during master import")):
            from deployment import pythonanywhere_wsgi as bridge

        original = bridge.ASGIMiddleware
        starts = []
        def make_bridge(*args, **kwargs):
            starts.append(1)
            time.sleep(0.05)  # Allow the other first requests to reach initialization.
            return original(*args, **kwargs)
        bridge.ASGIMiddleware = make_bridge
        ready = threading.Barrier(6)
        def request(_):
            ready.wait(timeout=5)
            client = Client(bridge.application, Response)
            for _ in range(4):
                response = client.get("/api/health")
                assert response.status_code == 200
                assert "real-accounts" in response.json["capabilities"]
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(request, range(6)))
        assert len(starts) == 1, starts
        print("24 concurrent worker requests passed; one event loop initialized")
    """, tmp_path)
    assert "24 concurrent worker requests passed" in result.stdout


@pytest.mark.skipif(not hasattr(os, "fork"), reason="Actual prefork regression requires Unix os.fork.")
@pytest.mark.parametrize("warm_parent", [False, True])
def test_wsgi_import_before_fork_serves_real_child_requests(tmp_path, warm_parent):
    # The warm case also forks while the parent's initialization lock is held.
    # The child must discard the parent's loop and lock to return its own response.
    source = """
        import json
        import os
        import signal
        from werkzeug.test import Client
        from werkzeug.wrappers import Response
        from deployment import pythonanywhere_wsgi as bridge

        warm_parent = WARM_PARENT
        if warm_parent:
            assert Client(bridge.application, Response).get("/api/health").status_code == 200
            bridge._initialization_lock.acquire()
        reader, writer = os.pipe()
        child = os.fork()
        if child == 0:
            os.close(reader)
            signal.alarm(8)  # A broken inherited loop cannot leave an orphan forever.
            try:
                client = Client(bridge.application, Response)
                health = client.get("/api/health")
                prefs = {"level": "beginner", "goal": "health", "days_per_week": 2, "minutes_per_session": 20}
                plan = client.post("/api/plan", json=prefs)
                assert health.status_code == 200
                assert "real-accounts" in health.json["capabilities"]
                assert plan.status_code == 200
                assert plan.json["trial_info"]["stores_inputs"] is False
                os.write(writer, json.dumps({"health": 200, "plan": 200}).encode())
            finally:
                os.close(writer)
                os._exit(0)
        os.close(writer)
        if warm_parent:
            bridge._initialization_lock.release()
        with os.fdopen(reader, "rb") as result:
            received = result.read()
        _, status = os.waitpid(child, 0)
        assert os.waitstatus_to_exitcode(status) == 0, status
        assert json.loads(received) == {"health": 200, "plan": 200}
        print("real prefork child requests passed")
    """.replace("WARM_PARENT", repr(warm_parent))
    assert "real prefork child requests passed" in run_worker_probe(source, tmp_path).stdout
