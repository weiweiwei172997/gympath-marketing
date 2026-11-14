"""Keep process-local request counters independent between test cases."""

import pytest

from backend import security
from backend.auth import AuthRateLimiter


@pytest.fixture(autouse=True)
def isolated_request_budgets(monkeypatch):
    monkeypatch.setattr(security, "api_rate_limiter", AuthRateLimiter(limit=120, window_seconds=60))
    monkeypatch.setattr(security, "request_budget", security.RequestBudget())
    monkeypatch.delenv("GYMPATH_ALLOWED_HOSTS", raising=False)
