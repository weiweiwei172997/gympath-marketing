"""Verify complete, source-based time fitting rather than named-template copies."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from backend import plan_adapter as fitted
from backend import plan_engine as source


LEVELS = tuple(fitted.FREQUENCY_CAPS)
GOALS = ("muscle_gain", "strength_gain", "fat_loss", "health")


def training_days(plan):
    return [day for day in plan["weekly_schedule"] if not day.get("is_rest_day")]


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("days", range(1, 8))
@pytest.mark.parametrize("minutes", (15, 30, 60, 180))
def test_available_frequency_budget_and_source_prescriptions(level, goal, days, minutes):
    plan = fitted.generate_fitted_plan(level, goal, days, minutes)
    expected = min(days, fitted.FREQUENCY_CAPS[level])
    assert plan["days_per_week"] == plan["split"]["days"] == expected
    assert len(training_days(plan)) == expected
    assert plan["adaptation"]["requested_days"] == days
    assert plan["adaptation"]["scheduled_days"] == expected
    assert plan["adaptation"]["requested_minutes"] == minutes
    assert plan["adaptation"]["estimation_note"]
    patterns = set()
    for day in training_days(plan):
        assert day["warmup"] and day["exercises"]
        breakdown = day["duration_breakdown"]
        assert breakdown["warmup_seconds"] == 300
        assert breakdown["cooldown_seconds"] == 120
        assert breakdown["transition_seconds"] == 45 * len(day["exercises"])
        assert breakdown["total_seconds"] == sum(value for key, value in breakdown.items() if key != "total_seconds")
        assert 0 < breakdown["total_seconds"] <= minutes * 60
        assert 0 < day["estimated_minutes"] <= minutes
        assert day["adaptation"]["planned_sets"] == sum(exercise["sets"] for exercise in day["exercises"])
        assert day["adaptation"]["source_sets"] >= day["adaptation"]["planned_sets"]
        for exercise in day["exercises"]:
            patterns.add(exercise["movement_pattern"])
            prescription = exercise["source_prescription"]
            original = source._exercise(prescription["name"])
            assert prescription == {key: original[key] for key in ("name", "sets", "reps", "rest_seconds")}
            assert exercise["name_original"] == prescription["name"]
            assert 1 <= exercise["sets"] <= min(original["sets"], fitted.SET_CAPS[level])
            assert exercise["rest_seconds"] == original["rest_seconds"]
            assert exercise["teaching_url"] == original["teaching_url"]
            assert "session_video_url" not in day and "warmup_video_url" not in day
            assert "failure" not in exercise["reps"] and "pump" not in exercise["reps"]
    assert {"push", "pull", "legs"} <= patterns
    assert "strength_plan" not in plan and "muscle_gain_plan" not in plan
    recoveries = [day for day in plan["weekly_schedule"] if day.get("is_rest_day")]
    assert recoveries
    for recovery in recoveries:
        assert recovery["exercises"] == [] and recovery["estimated_minutes"] == 0
        assert recovery["duration_breakdown"]["total_seconds"] == 0
        assert recovery["rest_note"]


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("days", (1, 2))
def test_each_low_frequency_session_preserves_push_pull_and_legs(level, goal, days):
    plan = fitted.generate_fitted_plan(level, goal, days, 15)
    for day in training_days(plan):
        assert {"push", "pull", "legs"} <= {exercise["movement_pattern"] for exercise in day["exercises"]}
        assert all(exercise["is_core"] for exercise in day["exercises"][:3])


def test_longer_budget_adds_volume_without_filling_all_available_time():
    short = fitted.generate_fitted_plan("experienced", "strength_gain", 3, 15)
    long = fitted.generate_fitted_plan("experienced", "strength_gain", 3, 180)
    assert sum(day["adaptation"]["planned_sets"] for day in training_days(long)) > sum(day["adaptation"]["planned_sets"] for day in training_days(short))
    assert all(day["estimated_minutes"] < 180 for day in training_days(long))


def test_training_objects_are_independent_across_cycles_and_requests():
    plan = fitted.generate_fitted_plan("experienced", "muscle_gain", 6, 60)
    first, repeated = training_days(plan)[0], training_days(plan)[3]
    before = deepcopy(repeated)
    first["exercises"][0]["sets"] = 999
    first["exercises"][0]["source_prescription"]["sets"] = 999
    assert repeated == before
    fresh = fitted.generate_fitted_plan("experienced", "muscle_gain", 6, 60)
    assert training_days(fresh)[0] == before | {"day": "训练日 1"}
    assert source._exercise("Barbell Bench Press")["sets"] == 4


@pytest.mark.parametrize(
    "reps,name,expected",
    [
        ("5 @ 70% 1RM起步", "Barbell Bench Press", 15),
        ("2（90%）", "Barbell Bench Press", 15),
        ("8-12", "Seated Cable Row", 36),
        ("10 each side", "Walking Lunge", 60),
        ("12", "Single-Arm Machine Row", 72),
        ("30-60 sec", "Plank", 60),
        ("12 + 10 + 5", "Seated Cable Row", 81),
        ("unrecognised", "Seated Cable Row", 60),
    ],
)
def test_execution_estimate_treats_loads_timed_holds_and_both_sides(reps, name, expected):
    assert fitted._execution_seconds({"reps": reps, "name": name}) == expected


def test_insufficient_minimum_budget_is_reported_instead_of_shortening_rest(monkeypatch):
    monkeypatch.setattr(fitted, "WARMUP_SECONDS", 1000)
    with pytest.raises(ValueError, match="增加单次时间"):
        fitted.generate_fitted_plan("beginner", "muscle_gain", 1, 15)


def test_original_engine_hash_stays_equal_to_extraction_manifest():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "references/gympath-original/plan-engine-source.json").read_text(encoding="utf-8"))
    assert sha256((root / "backend/plan_engine.py").read_bytes()).hexdigest() == manifest["output"]["sha256"]


@pytest.mark.parametrize(
    "changes",
    [
        {"level": "invalid"}, {"goal": "general_fitness"}, {"days_per_week": 0},
        {"days_per_week": 8}, {"days_per_week": True}, {"days_per_week": 2.0},
        {"minutes_per_session": 14}, {"minutes_per_session": 181}, {"minutes_per_session": False},
    ],
)
def test_adapter_rejects_invalid_direct_calls(changes):
    arguments = {"level": "beginner", "goal": "health", "days_per_week": 2, "minutes_per_session": 30, **changes}
    with pytest.raises(ValueError):
        fitted.generate_fitted_plan(**arguments)
