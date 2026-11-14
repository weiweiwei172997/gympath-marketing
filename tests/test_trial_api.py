"""Exercise real planning rules, validation and the public-file boundary."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import app as trial


@pytest.fixture
def client():
    with TestClient(trial.app) as connection:
        yield connection


def preferences(**changes):
    return {
        "level": "restarting",
        "goal": "fat_loss",
        "days_per_week": 3,
        "minutes_per_session": 60,
        **changes,
    }


def test_health_describes_actual_trial_boundary(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "service": "gympath-local-trial",
        "capabilities": ["deterministic-plan", "time-fit-v1", "real-accounts", "saved-plans"],
        "stores_inputs": False,
        "account_storage": True,
    }


@pytest.mark.parametrize("level", ["beginner", "restarting", "experienced"])
@pytest.mark.parametrize("goal", ["muscle_gain", "strength_gain", "fat_loss", "health"])
@pytest.mark.parametrize("days, minutes", [(1, 15), (7, 180)])
def test_all_levels_goals_and_boundaries_generate_real_plans(client, level, goal, days, minutes):
    response = client.post(
        "/api/plan",
        json=preferences(level=level, goal=goal, days_per_week=days, minutes_per_session=minutes),
    )
    assert response.status_code == 200
    plan = response.json()
    assert plan["level"] == level
    assert plan["goal"] == goal
    assert plan["minutes_per_session"] == minutes
    assert 1 <= plan["days_per_week"] <= 7
    assert plan["split"]["split_name"]
    assert plan["split"]["reason"]
    assert plan["safety_note"]
    assert plan["trial_info"] == {
        "engine": "gympath-rules-adapted",
        "stores_inputs": False,
        "creates_account": False,
    }
    schedule = plan["weekly_schedule"]
    training_days = [day for day in schedule if not day.get("is_rest_day")]
    assert len(training_days) == plan["days_per_week"]
    for day in training_days:
        assert day["day"] and day["focus"]
        assert day["warmup"]
        assert day["exercises"]
        assert day["session_note"]
        for exercise in day["exercises"]:
            assert exercise["name"]
            assert isinstance(exercise["sets"], int) and exercise["sets"] > 0
            assert exercise["reps"]
            assert exercise["rest_seconds"] >= 0
            assert exercise["teaching_url"].startswith("https://")


def test_beginner_override_includes_the_original_recovery_day(client):
    plan = client.post(
        "/api/plan", json=preferences(level="beginner", days_per_week=1, minutes_per_session=15)
    ).json()
    assert plan["days_per_week"] == 1
    assert plan["adaptation"]["requested_days"] == 1
    assert len(plan["weekly_schedule"]) == 2
    rest_days = [day for day in plan["weekly_schedule"] if day.get("is_rest_day")]
    assert len(rest_days) == 1
    assert rest_days[0]["exercises"] == []
    assert rest_days[0]["warmup"] == []
    assert rest_days[0]["rest_note"]


def test_goals_and_levels_change_plan_shape_instead_of_repeating_a_demo(client):
    health = client.post("/api/plan", json=preferences(goal="health")).json()
    strength = client.post("/api/plan", json=preferences(level="beginner", goal="strength_gain")).json()
    muscle = client.post("/api/plan", json=preferences(level="experienced", goal="muscle_gain")).json()
    fat_loss = client.post("/api/plan", json=preferences()).json()
    assert len({plan["goal"] for plan in [health, strength, muscle, fat_loss]}) == 4
    assert health["weekly_schedule"][0]["exercises"][0]["name"] == "徒手深蹲"
    assert strength["weekly_schedule"][0]["exercises"][0]["name"]
    assert muscle["days_per_week"] == 3
    assert fat_loss["days_per_week"] == 3
    assert all(plan["adaptation"]["version"] == "time-fit-v1" for plan in [health, strength, muscle, fat_loss])
    assert health["weekly_schedule"][0]["focus"] != fat_loss["weekly_schedule"][0]["focus"]


def test_shorter_sessions_reduce_the_experienced_generic_plan(client):
    short = client.post("/api/plan", json=preferences(level="experienced", minutes_per_session=15)).json()
    long = client.post("/api/plan", json=preferences(level="experienced", minutes_per_session=180)).json()
    assert sum(day["adaptation"]["planned_sets"] for day in short["weekly_schedule"] if not day.get("is_rest_day")) < sum(day["adaptation"]["planned_sets"] for day in long["weekly_schedule"] if not day.get("is_rest_day"))


@pytest.mark.parametrize(
    "field, value",
    [
        ("days_per_week", 0),
        ("days_per_week", 8),
        ("days_per_week", 3.0),
        ("days_per_week", 3.5),
        ("days_per_week", "3"),
        ("days_per_week", True),
        ("minutes_per_session", 14),
        ("minutes_per_session", 181),
        ("minutes_per_session", 60.0),
        ("minutes_per_session", "60"),
        ("minutes_per_session", False),
        ("level", "advanced"),
        ("level", "BEGINNER"),
        ("goal", "general_fitness"),
        ("goal", "lose_fat"),
        ("level", None),
    ],
)
def test_invalid_or_coerced_inputs_are_rejected_with_field_feedback(client, field, value):
    response = client.post("/api/plan", json=preferences(**{field: value}))
    assert response.status_code == 422
    feedback = response.json()
    assert isinstance(feedback["detail"], str)
    assert {error["field"] for error in feedback["errors"]} == {field}
    assert all(error["message"] and error["code"] for error in feedback["errors"])
    assert all("input" not in error and "ctx" not in error for error in feedback["errors"])


def test_unknown_fields_and_their_values_are_not_echoed(client):
    response = client.post("/api/plan", json=preferences(email="private-sentinel@example.invalid"))
    assert response.status_code == 422
    assert "private-sentinel" not in response.text
    assert response.json()["errors"] == [
        {"field": "email", "message": "Unexpected field.", "code": "extra_forbidden"}
    ]


def test_missing_field_reports_a_clear_path(client):
    body = preferences()
    del body["goal"]
    response = client.post("/api/plan", json=body)
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "goal"
    assert response.json()["errors"][0]["message"] == "This field is required."


@pytest.mark.parametrize("body", [None, [], "private-sentinel"])
def test_non_object_json_is_not_accepted_or_echoed(client, body):
    response = client.post("/api/plan", content=json.dumps(body), headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "private-sentinel" not in response.text
    assert response.json()["errors"][0]["field"] == "body"


def test_malformed_json_does_not_echo_body(client):
    response = client.post(
        "/api/plan", content='{"private-sentinel":', headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert "private-sentinel" not in response.text
    assert response.json()["errors"][0]["code"] == "json_invalid"


def test_generation_value_error_is_a_clean_bad_request(client, monkeypatch):
    def rejected_plan(**kwargs):
        raise ValueError("private-sentinel from the generator")

    monkeypatch.setattr(trial, "generate_fitted_plan", rejected_plan)
    response = client.post("/api/plan", json=preferences())
    assert response.status_code == 400
    assert "private-sentinel" not in response.text
    assert response.json() == {"detail": "Unable to generate a plan for these preferences."}


@pytest.mark.parametrize(
    "url, content_type",
    [
        ("/", "text/html"),
        ("/index.html", "text/html"),
        ("/demo.html", "text/html"),
        ("/styles.css", "text/css"),
        ("/script.js", "application/javascript"),
        ("/assets/mark.svg", "image/svg+xml"),
        ("/assets/training-path.svg", "image/svg+xml"),
        ("/favicon.ico", "image/svg+xml"),
    ],
)
def test_named_public_files_are_served(client, url, content_type):
    response = client.get(url)
    assert response.status_code == 200
    assert content_type in response.headers["content-type"]
    assert response.content


def test_trial_public_files_are_explicit_routes_and_use_the_expected_files(client, monkeypatch, tmp_path):
    # The front-end agent creates these files independently; use small public
    # fixtures here so route coverage does not depend on its editing progress.
    (tmp_path / "trial.html").write_text("<main>Trial</main>", encoding="utf-8")
    (tmp_path / "trial.js").write_text("// native trial script", encoding="utf-8")
    monkeypatch.setattr(trial, "SITE_ROOT", tmp_path)
    assert client.get("/trial.html").text == "<main>Trial</main>"
    assert client.get("/trial.js").text == "// native trial script"


@pytest.mark.parametrize(
    "url",
    [
        "/docs/HANDOFF.md",
        "/docs/2026-10-12-local-trial-design.md",
        "/references/gympath-original/frontend/app/page.tsx",
        "/references/gympath-original/plan-engine-source.json",
        "/backend/app.py",
        "/backend/plan_engine.py",
        "/tests/test_trial_api.py",
        "/requirements-trial.txt",
        "/README.md",
        "/.env",
        "/gympath.db",
        "/uploads/photo.jpg",
        "/assets/not-allowed.svg",
        "/assets/secret.txt",
        "/assets/../docs/HANDOFF.md",
        "/assets/%2e%2e/docs/HANDOFF.md",
        "/assets/%2e%2e%2fdocs%2fHANDOFF.md",
        "/assets/%5c..%5cdocs%5cHANDOFF.md",
        "/docs",
        "/redoc",
        "/openapi.json",
    ],
)
def test_internal_files_and_path_traversal_are_unavailable(client, url):
    assert client.get(url).status_code == 404


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", "/api/community/posts"),
        ("post", "/api/community/posts-with-image"),
        ("get", "/api/uploads/community/photo.jpg"),
        ("post", "/api/ai-chat"),
        ("post", "/api/nutrition"),
        ("post", "/api/feedback"),
        ("post", "/api/progress"),
        ("get", "/api/exercises"),
    ],
)
def test_unmigrated_community_upload_and_ai_endpoints_are_absent(client, method, url):
    assert getattr(client, method)(url).status_code == 404


def test_generating_plans_never_creates_storage_files(client, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    before = set(Path.cwd().rglob("*"))
    for goal in ["muscle_gain", "strength_gain", "fat_loss", "health"]:
        response = client.post("/api/plan", json=preferences(goal=goal))
        assert response.status_code == 200
    assert set(Path.cwd().rglob("*")) == before
    assert not list(tmp_path.rglob("*.db"))
