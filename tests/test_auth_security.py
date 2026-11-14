"""Abuse boundaries use only new temporary databases and synthetic data."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from backend import auth


@pytest.fixture(autouse=True)
def isolated_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("GYMPATH_DATA_DIR", str(tmp_path / "security-data"))
    monkeypatch.delenv("GYMPATH_MAX_ACCOUNTS", raising=False)


def test_auth_budget_survives_new_limiter_and_account_database_is_not_created():
    first = auth.PersistentAuthRateLimiter(limit=2)
    assert first.allow("192.0.2.1")
    assert first.allow("192.0.2.1")
    assert not auth.PersistentAuthRateLimiter(limit=2).allow("192.0.2.1")
    assert not auth.database_path().exists()
    assert first.path().exists()
    with sqlite3.connect(first.path()) as db:
        serialized = " ".join(str(row) for row in db.execute("SELECT * FROM auth_buckets"))
    assert "192.0.2.1" not in serialized


def test_auth_budget_is_atomic_across_independent_workers():
    def attempt(_):
        return auth.PersistentAuthRateLimiter(limit=5).allow("192.0.2.2")

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(attempt, range(24)))
    assert sum(results) == 5


def test_auth_budget_is_shared_with_a_fresh_python_process():
    assert auth.PersistentAuthRateLimiter(limit=1).allow("192.0.2.4")
    check = subprocess.run(
        [sys.executable, "-c", "from backend.auth import PersistentAuthRateLimiter; "
         "print(PersistentAuthRateLimiter(limit=1).allow('192.0.2.4'))"],
        cwd=Path(auth.__file__).resolve().parent.parent,
        capture_output=True, text=True, check=True, timeout=10,
    )
    assert check.stdout.strip() == "False"


def test_auth_global_budget_limits_distributed_hash_work():
    limiter = auth.PersistentAuthRateLimiter(limit=10, global_limit=3)
    assert all(limiter.allow(f"192.0.2.{index}") for index in range(3))
    assert not limiter.allow("198.51.100.1")
    with sqlite3.connect(limiter.path()) as db:
        assert db.execute("SELECT COUNT(*) FROM auth_buckets").fetchone()[0] == 4


def test_auth_storage_is_bounded_without_evicting_active_limits():
    limiter = auth.PersistentAuthRateLimiter(limit=2, max_clients=2)
    assert limiter.allow("192.0.2.1")
    assert limiter.allow("192.0.2.2")
    assert not limiter.allow("192.0.2.3")
    assert limiter.allow("192.0.2.1")
    assert not limiter.allow("192.0.2.1")
    with sqlite3.connect(limiter.path()) as db:
        rows = db.execute("SELECT key, events FROM auth_buckets").fetchall()
    assert len(rows) == 3
    assert all(len(json.loads(events)) <= (240 if key == "global" else 2) for key, events in rows)


def test_auth_budget_expires_after_window(monkeypatch):
    clock = [1000]
    monkeypatch.setattr(auth.time, "time", lambda: clock[0])
    limiter = auth.PersistentAuthRateLimiter(limit=1, window_seconds=600, max_clients=1)
    assert limiter.allow("192.0.2.1")
    clock[0] = 1599
    assert not limiter.allow("192.0.2.1")
    assert not limiter.allow("192.0.2.2")
    clock[0] = 1600
    assert limiter.allow("192.0.2.2")
    with sqlite3.connect(limiter.path()) as db:
        assert db.execute("SELECT COUNT(*) FROM auth_buckets").fetchone()[0] == 2


def test_auth_database_failure_denies_instead_of_bypassing_budget(monkeypatch):
    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("unavailable")

    monkeypatch.setattr(auth.sqlite3, "connect", unavailable)
    assert not auth.PersistentAuthRateLimiter().allow("192.0.2.1")


def test_account_storage_failure_is_a_safe_typed_exception(monkeypatch):
    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("private filesystem details")

    monkeypatch.setattr(auth.sqlite3, "connect", unavailable)
    with pytest.raises(auth.StorageUnavailable):
        auth.register("Synthetic", "Testpass1")


def test_configured_account_quota_is_enforced(monkeypatch):
    monkeypatch.setenv("GYMPATH_MAX_ACCOUNTS", "1")
    auth.register("Synthetic", "Testpass1")
    with pytest.raises(auth.RegistrationClosed):
        auth.register("Second", "Testpass1")


@pytest.mark.parametrize("quota", ["0", "-1", "1001", "unlimited"])
def test_invalid_account_quota_cannot_disable_storage_cap(monkeypatch, quota):
    monkeypatch.setenv("GYMPATH_MAX_ACCOUNTS", quota)
    with pytest.raises(ValueError, match="integer from 1 to 1000"):
        auth.register("Synthetic", "Testpass1")
    assert not auth.database_path().exists()


def test_registration_cap_is_atomic_and_preserves_existing_login(monkeypatch):
    monkeypatch.setattr(auth, "ACCOUNT_LIMIT", 2)
    password = "Testpass1"
    user, _, _ = auth.register("Existing", password)

    def register(index):
        try:
            auth.register(f"Synthetic{index}", password)
            return True
        except auth.RegistrationClosed:
            return False

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(register, range(8)))
    assert sum(results) == 1
    with sqlite3.connect(auth.database_path()) as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2
    logged_in, _, _ = auth.login("Existing", password)
    assert logged_in == user


def test_account_cap_does_not_delete_sessions_or_plans(monkeypatch):
    monkeypatch.setattr(auth, "ACCOUNT_LIMIT", 1)
    user, token, csrf = auth.register("Existing", "Testpass1")
    preferences = {"goal": "health", "minutes_per_session": 20}
    plan = {"days_per_week": 1, "weekly_schedule": [{"exercises": ["synthetic-only"]}]}
    saved = auth.save_plan(user["id"], preferences, plan)
    with pytest.raises(auth.RegistrationClosed):
        auth.register("NewUser", "Otherpass1")
    assert auth.session(token) == {"user": user, "csrf_token": csrf}
    assert auth.list_plans(user["id"]) == [saved]
