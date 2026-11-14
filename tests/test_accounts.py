"""Real account persistence, cookie/CSRF boundaries and isolated saved plans."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend import app as site
from backend import auth


ORIGIN = "http://testserver"
PASSWORD = "a-good-password-2026"
PREFERENCES = {"level": "beginner", "goal": "muscle_gain", "days_per_week": 3, "minutes_per_session": 45}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("GYMPATH_DATA_DIR", str(tmp_path / "isolated-data"))
    monkeypatch.setattr(auth, "rate_limiter", auth.AuthRateLimiter(limit=100))
    with TestClient(site.app, headers={"Origin": ORIGIN}) as connection:
        yield connection


def register(client, username="测试同学", password=PASSWORD):
    response = client.post("/api/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201, response.text
    return response


def csrf_headers(response):
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_anonymous_me_and_guest_plan_do_not_initialize_accounts(client):
    assert client.get("/api/auth/me").json() == {"user": None, "csrf_token": None}
    assert client.post("/api/plan", json=PREFERENCES).status_code == 200
    assert not auth.database_path().exists()
    assert client.get("/api/plans").status_code == 401


def test_register_real_database_hashes_password_and_token_and_sets_cookie(client):
    response = register(client)
    result = response.json()
    assert set(result) == {"user", "csrf_token"}
    assert result["user"] == {"id": 1, "username": "测试同学"}
    assert client.get("/api/auth/me").json() == result
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=604800" in cookie
    assert "Secure" not in cookie
    assert response.headers["cache-control"] == "no-store"
    token = client.cookies.get(auth.COOKIE_NAME)
    with sqlite3.connect(auth.database_path()) as db:
        stored = db.execute("SELECT password_hash FROM users").fetchone()[0]
        session = db.execute("SELECT token_hash, expires_at-created_at, csrf_token FROM sessions").fetchone()
    assert stored.startswith("scrypt$16384$8$1$")
    assert PASSWORD not in stored
    assert auth.verify_password(PASSWORD, stored)
    assert session[0] == auth.token_hash(token) and token != session[0]
    assert session[1] == auth.SESSION_SECONDS and session[2] == result["csrf_token"]
    assert PASSWORD.encode() not in auth.database_path().read_bytes()
    assert token.encode() not in auth.database_path().read_bytes()


def test_same_password_has_distinct_random_salts(client):
    register(client, "同学甲")
    register(client, "同学乙")
    with sqlite3.connect(auth.database_path()) as db:
        hashes = [row[0] for row in db.execute("SELECT password_hash FROM users")]
    assert hashes[0] != hashes[1]
    assert all(auth.verify_password(PASSWORD, value) for value in hashes)


def test_accounts_persist_across_new_client_and_login_rotates_session(client):
    response = register(client, "Learner_01")
    old_token = client.cookies.get(auth.COOKIE_NAME)
    second = TestClient(site.app, headers={"Origin": ORIGIN})
    login = second.post("/api/auth/login", json={"username": "learner_01", "password": PASSWORD})
    assert login.status_code == 200
    assert login.json()["user"] == response.json()["user"]
    assert login.json()["csrf_token"] != response.json()["csrf_token"]
    assert second.cookies.get(auth.COOKIE_NAME) != old_token
    # A new login in the same browser invalidates the replaced cookie.
    again = client.post("/api/auth/login", json={"username": "Learner_01", "password": PASSWORD})
    assert again.status_code == 200
    assert auth.session(old_token) is None
    second.close()


def test_username_unique_case_insensitive_and_generic_login_errors(client):
    register(client, "Learner_01")
    duplicate = client.post("/api/auth/register", json={"username": "learner_01", "password": PASSWORD})
    assert duplicate.status_code == 409
    missing = client.post("/api/auth/login", json={"username": "Unknown_01", "password": PASSWORD})
    wrong = client.post("/api/auth/login", json={"username": "Learner_01", "password": "wrong-password-2026"})
    assert missing.status_code == wrong.status_code == 401
    assert missing.json() == wrong.json()
    assert PASSWORD not in wrong.text


@pytest.mark.parametrize("username,password", [
    ("a", PASSWORD), ("x" * 21, PASSWORD), ("has space", PASSWORD), ("<script>", PASSWORD),
    (123, PASSWORD), ("同学甲", "abc1234"), ("同学甲", "a" * 128 + "1"),
    ("同学甲", "中" * 85 + "a1"), ("同学甲", 1234567890), ("同学甲", None),
])
def test_invalid_account_fields_rejected_without_values(client, username, password):
    response = client.post("/api/auth/register", json={"username": username, "password": password})
    assert response.status_code == 422
    assert all("input" not in error for error in response.json()["errors"])
    assert not auth.database_path().exists()


def test_extra_fields_rejected_without_echoing_private_values(client):
    response = client.post("/api/auth/register", json={"username": "同学甲", "password": PASSWORD, "email": "private@example.invalid"})
    assert response.status_code == 422
    assert "private@example.invalid" not in response.text and PASSWORD not in response.text
    assert not auth.database_path().exists()


def test_unicode_password_and_exact_byte_boundary(client):
    value = "中" * 84 + "a1bc"  # 256 UTF-8 bytes, 88 characters.
    register(client, password=value)
    assert client.post("/api/auth/login", json={"username": "测试同学", "password": value}).status_code == 200


@pytest.mark.parametrize("password", ["abc1234", "abcdefgh", "12345678", "中文密码中文密码1", "Abcdefg١"])
def test_registration_requires_eight_characters_with_ascii_letters_and_numbers(client, password):
    response = client.post("/api/auth/register", json={"username": "新同学", "password": password})
    assert response.status_code == 422
    assert response.json()["errors"] == [{
        "field": "password", "message": "密码至少 8 个字符，并包含字母和数字。",
        "code": "string_too_short" if len(password) < 8 else "password_policy",
    }]
    assert password not in response.text
    assert not auth.database_path().exists()


def test_exact_eight_character_password_registers_logs_in_and_saves(client):
    password = "Abcdef12"
    registered = register(client, password=password)
    assert client.post("/api/auth/logout", headers=csrf_headers(registered)).status_code == 204
    login = client.post("/api/auth/login", json={"username": "测试同学", "password": password})
    assert login.status_code == 200
    saved = client.post("/api/plans", json={"preferences": PREFERENCES}, headers=csrf_headers(login))
    assert saved.status_code == 201
    assert client.get("/api/plans").json()["plans"] == [saved.json()]


@pytest.mark.parametrize("password", ["LettersOnly", "1234567890", "中文密码中文密码中文", "中" * 85 + "a"])
def test_legacy_passwords_still_log_in_without_new_registration_policy(client, password):
    # Synthesize an account allowed by the earlier policy in this test's new DB.
    # No production account or database migration is involved.
    user, token, _ = auth.register("旧同学", password)
    auth.revoke(token)
    login = client.post("/api/auth/login", json={"username": "旧同学", "password": password})
    assert login.status_code == 200
    assert login.json()["user"] == user
    assert client.get("/api/auth/me").json()["user"] == user
    saved = client.post("/api/plans", json={"preferences": PREFERENCES}, headers=csrf_headers(login))
    assert saved.status_code == 201
    assert client.get("/api/plans").json()["plans"] == [saved.json()]
    new_registration = client.post("/api/auth/register", json={"username": "新同学", "password": password})
    assert new_registration.status_code == 422


def test_login_does_not_apply_registration_minimum_or_composition(client):
    register(client)
    wrong = client.post("/api/auth/login", json={"username": "测试同学", "password": "a"})
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == "用户名或密码不正确。"


@pytest.mark.parametrize("path", ["/api/auth/register", "/api/auth/login"])
@pytest.mark.parametrize("password", ["a" * 128 + "1", "中" * 85 + "a1"])
def test_password_resource_limits_use_friendly_errors_without_technical_limits(client, path, password):
    response = client.post(path, json={"username": "同学甲", "password": password})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "password"
    assert response.json()["errors"][0]["message"] == "密码过长，请缩短后重试。"
    assert password not in response.text
    assert "UTF-8" not in response.text and "256" not in response.text and "128" not in response.text
    assert not auth.database_path().exists()


def test_password_exact_character_limit_is_accepted(client):
    password = "a" * 127 + "1"
    register(client, password=password)
    assert client.post("/api/auth/login", json={"username": "测试同学", "password": password}).status_code == 200


@pytest.mark.parametrize("password", ["", None, 12345678])
def test_login_requires_a_nonempty_string_password(client, password):
    response = client.post("/api/auth/login", json={"username": "同学甲", "password": password})
    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == "请输入密码。"
    assert not auth.database_path().exists()


@pytest.mark.parametrize("origin", [None, "null", "https://evil.example", "http://testserver.evil.example", "https://testserver"])
def test_register_requires_same_origin(client, origin):
    client.headers.pop("origin", None)
    headers = {} if origin is None else {"Origin": origin}
    response = client.post("/api/auth/register", json={"username": "同学甲", "password": PASSWORD}, headers=headers)
    assert response.status_code == 403
    assert not auth.database_path().exists()


def test_login_also_rejects_cross_origin(client):
    register(client)
    assert client.post("/api/auth/login", json={"username": "测试同学", "password": PASSWORD}, headers={"Origin": "https://evil.example"}).status_code == 403


def test_https_cookie_secure_and_spoofed_forwarded_proto_not_trusted(client):
    response = register(client)
    assert "Secure" not in response.headers["set-cookie"]
    spoof = client.post("/api/auth/login", json={"username": "测试同学", "password": PASSWORD}, headers={"X-Forwarded-Proto": "https"})
    assert spoof.status_code == 200 and "Secure" not in spoof.headers["set-cookie"]
    with TestClient(site.app, base_url="https://gympath.example", headers={"Origin": "https://gympath.example"}) as secure:
        login = secure.post("/api/auth/login", json={"username": "测试同学", "password": PASSWORD})
        assert login.status_code == 200 and "Secure" in login.headers["set-cookie"]
        assert secure.get("/api/auth/me").json()["user"] is not None


def test_logout_requires_csrf_and_revokes_server_session(client):
    response = register(client)
    token = client.cookies.get(auth.COOKIE_NAME)
    assert client.post("/api/auth/logout").status_code == 403
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    logout = client.post("/api/auth/logout", headers=csrf_headers(response))
    assert logout.status_code == 204 and logout.content == b""
    assert "Max-Age=0" in logout.headers["set-cookie"]
    assert auth.session(token) is None
    assert client.get("/api/auth/me").json()["user"] is None
    assert client.get("/api/plans").status_code == 401


def test_expired_or_unknown_session_cannot_access_plans(client):
    register(client)
    token = client.cookies.get(auth.COOKIE_NAME)
    with sqlite3.connect(auth.database_path()) as db:
        db.execute("UPDATE sessions SET expires_at = 1")
    assert auth.session(token) is None
    assert client.get("/api/auth/me").json()["user"] is None
    assert client.get("/api/plans").status_code == 401
    assert auth.session("not-a-real-token") is None


def test_saved_plans_generated_on_server_and_persist_with_owner(client):
    response = register(client)
    saved = client.post("/api/plans", json={"preferences": PREFERENCES}, headers=csrf_headers(response))
    assert saved.status_code == 201
    record = saved.json()
    assert set(record) == {"id", "title", "created_at", "preferences", "plan"}
    assert record["preferences"] == PREFERENCES
    assert record["plan"]["adaptation"]["version"] == "time-fit-v1"
    assert record["plan"]["days_per_week"] == 3 and record["plan"]["weekly_schedule"]
    assert client.get("/api/plans").json() == {"plans": [record]}
    assert client.post("/api/plans", json={"preferences": PREFERENCES, "plan": {"forged": True}}, headers=csrf_headers(response)).status_code == 422
    assert client.post("/api/auth/logout", headers=csrf_headers(response)).status_code == 204
    login = client.post("/api/auth/login", json={"username": "测试同学", "password": PASSWORD})
    assert client.get("/api/plans").json()["plans"] == [record]
    deleted = client.delete(f"/api/plans/{record['id']}", headers=csrf_headers(login))
    assert deleted.status_code == 204
    assert client.get("/api/plans").json() == {"plans": []}


def test_cross_user_access_and_deletion_are_isolated(client):
    first = register(client, "同学甲")
    record = client.post("/api/plans", json={"preferences": PREFERENCES}, headers=csrf_headers(first)).json()
    second = register(client, "同学乙")
    assert client.get("/api/plans").json() == {"plans": []}
    assert client.delete(f"/api/plans/{record['id']}", headers=csrf_headers(second)).status_code == 404
    login = client.post("/api/auth/login", json={"username": "同学甲", "password": PASSWORD})
    assert client.get("/api/plans").json()["plans"][0]["id"] == record["id"]
    assert client.delete(f"/api/plans/{record['id']}", headers=csrf_headers(login)).status_code == 204


@pytest.mark.parametrize("method,path", [("post", "/api/plans"), ("delete", "/api/plans/1"), ("post", "/api/auth/logout")])
def test_unsafe_account_operations_require_csrf_and_origin(client, method, path):
    response = register(client)
    kwargs = {"json": {"preferences": PREFERENCES}} if path == "/api/plans" else {}
    assert getattr(client, method)(path, **kwargs).status_code == 403
    assert getattr(client, method)(path, headers={**csrf_headers(response), "Origin": "https://evil.example"}, **kwargs).status_code == 403
    assert getattr(client, method)(path, headers={"X-CSRF-Token": "wrong"}, **kwargs).status_code == 403


def test_plan_limit_requires_explicit_deletion_instead_of_losing_old_plans(client):
    response = register(client)
    for _ in range(20):
        saved = client.post("/api/plans", json={"preferences": PREFERENCES}, headers=csrf_headers(response))
        assert saved.status_code == 201
    assert len(client.get("/api/plans").json()["plans"]) == 20
    assert client.post("/api/plans", json={"preferences": PREFERENCES}, headers=csrf_headers(response)).status_code == 409
    assert client.delete(f"/api/plans/{saved.json()['id']}", headers=csrf_headers(response)).status_code == 204
    assert client.post("/api/plans", json={"preferences": PREFERENCES}, headers=csrf_headers(response)).status_code == 201


def test_rate_limit_is_bounded_and_does_not_accept_spoofed_forwarded_ip(client, monkeypatch):
    limiter = auth.AuthRateLimiter(limit=2, max_clients=2)
    monkeypatch.setattr(auth, "rate_limiter", limiter)
    for index in range(2):
        response = client.post("/api/auth/login", json={"username": "Unknown", "password": PASSWORD}, headers={"X-Forwarded-For": f"198.51.100.{index}"})
        assert response.status_code == 401
    response = client.post("/api/auth/login", json={"username": "Unknown", "password": PASSWORD}, headers={"X-Forwarded-For": "198.51.100.50"})
    assert response.status_code == 429 and response.headers["retry-after"] == "600"
    assert len(limiter.clients) == 1
    assert limiter.allow("second-client")
    assert not limiter.allow("third-client") and len(limiter.clients) == 2


@pytest.mark.parametrize("path", ["/data/gympath.sqlite3", "/data/gympath.sqlite3-wal", "/backend/auth.py"])
def test_account_database_and_auth_source_are_not_static_files(client, path):
    register(client)
    assert client.get(path).status_code == 404


def test_account_public_routes_use_only_named_files(client, monkeypatch, tmp_path):
    (tmp_path / "account.html").write_text("<main>Account</main>", encoding="utf-8")
    (tmp_path / "account.js").write_text("// Account", encoding="utf-8")
    monkeypatch.setattr(site, "SITE_ROOT", tmp_path)
    assert client.get("/account.html").text == "<main>Account</main>"
    assert client.get("/account.js").text == "// Account"
