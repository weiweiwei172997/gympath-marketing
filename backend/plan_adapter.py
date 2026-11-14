"""Fit a source-based training sequence to an available-time upper bound.

The extracted plan_engine is deliberately unchanged. This module composes a
new basic plan from its exercise definitions; it does not preserve a named
video routine or the original periodised progression instructions.
"""

from __future__ import annotations

from copy import deepcopy
from math import ceil
import re
from typing import Any

from . import plan_engine as source
from .locale_zh import localize_plan, translate_text


FREQUENCY_CAPS = {"beginner": 4, "restarting": 4, "experienced": 6}
SET_CAPS = {"beginner": 3, "restarting": 3, "experienced": 4}
WARMUP_SECONDS = 300
COOLDOWN_SECONDS = 120
TRANSITION_SECONDS = 45
ESTIMATION_NOTE = (
    "预计时间包含 5 分钟热身、2 分钟收尾、每个动作 45 秒准备和所列组间休息。"
    "按次数计算的动作估计为 3 秒/次，单侧动作计入两侧用时。"
    "实际节奏、排队、换器械或额外热身可能让用时更长，不保证在预计时间内完成。"
)


def _execution_seconds(exercise: dict[str, Any]) -> int:
    """Estimate one set conservatively, excluding load percentages.

    Source descriptions may contain ranges, timed holds, unilateral work or
    descending/drop sets. A percentage after @ (or in parentheses) is a load,
    never a repetition count. Unrecognised prescriptions get a minute per side.
    """
    reps = str(exercise["reps"]).split("@", 1)[0]
    reps = re.sub(r"[（(][^）)]*%[^）)]*[）)]", "", reps)
    reps = re.sub(r"\d+(?:\.\d+)?\s*%", "", reps)
    numbers = []
    for group in reps.split("+"):
        ranges = re.findall(r"(\d+(?:\.\d+)?)(?:\s*[-–]\s*(\d+(?:\.\d+)?))?", group)
        numbers.append(max((max(float(a), float(b or a)) for a, b in ranges), default=0))
    amount = sum(numbers) if "+" in reps else max(numbers, default=0)
    timed = bool(re.search(r"\bsec(?:ond)?s?\b|秒", reps, re.I))
    # Mixed alternatives such as '15 or 20-30 sec' use the longer bound.
    mixed_units = timed and bool(re.search(r"\bor\b|或", reps, re.I))
    seconds = amount if timed and not mixed_units else amount * 3
    if not amount:
        seconds = 60
    unilateral = bool(re.search(r"each side|each leg|每侧|左右", reps, re.I))
    unilateral = unilateral or str(exercise.get("name", "")).startswith(("Single-Arm", "Single-Leg"))
    return int(ceil(max(15, seconds) * (2 if unilateral else 1)))


def _breakdown(exercises: list[dict[str, Any]]) -> dict[str, int]:
    execution = sum(_execution_seconds(exercise) * exercise["sets"] for exercise in exercises)
    rests = sum(exercise["rest_seconds"] * (exercise["sets"] - 1) for exercise in exercises)
    transitions = TRANSITION_SECONDS * len(exercises)
    return {
        "warmup_seconds": WARMUP_SECONDS,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "exercise_seconds": execution,
        "rest_seconds": rests,
        "transition_seconds": transitions,
        "total_seconds": WARMUP_SECONDS + COOLDOWN_SECONDS + execution + rests + transitions,
    }


def _candidate(name: str, pattern: str, is_core: bool) -> dict[str, Any]:
    exercise = deepcopy(source._exercise(name))
    exercise["source_prescription"] = {
        key: deepcopy(exercise[key]) for key in ("name", "sets", "reps", "rest_seconds")
    }
    # Failure and pump targets have no bounded duration and are inappropriate
    # as mandatory instructions in this general visitor trial.
    if re.search(r"failure|pump|力竭|泵感", str(exercise["reps"]), re.I):
        exercise["reps"] = "8-12"
    original_notes = exercise["notes"]
    exercise["notes"] = translate_text(original_notes)
    exercise["notes_original"] = original_notes
    exercise["movement_pattern"] = pattern
    exercise["is_core"] = is_core
    exercise["phase"] = "基础动作" if is_core else "辅助动作"
    return exercise


def _blueprints(level: str, goal: str, days: int) -> tuple[str, list[dict[str, Any]], int]:
    """Return complete templates, never a truncated push/pull/legs week."""
    home = goal == "health"
    advanced_strength = goal == "strength_gain" and level == "experienced"
    squat = "Back Squat" if advanced_strength else "Goblet Squat"
    press = "Barbell Bench Press" if advanced_strength else "Dumbbell Bench Press"

    def day(focus: str, core: list[tuple[str, str]], extra: list[tuple[str, str]]) -> dict[str, Any]:
        return {
            "focus": focus,
            "exercises": [_candidate(name, pattern, True) for name, pattern in core]
            + [_candidate(name, pattern, False) for name, pattern in extra],
        }

    if days <= 2 or days == 3 and (home or level != "experienced"):
        if home:
            templates = [
                day("居家全身 A：腿、胸、背", [("Bodyweight Squat", "legs"), ("Push-up", "push"), ("Bent-Over Dumbbell Row", "pull")], [("Arm-Reach Crunch", "core"), ("Bottle Lateral Raise", "push")]),
                day("居家全身 B：臀腿、胸、背", [("Chair Hip Hinge", "legs"), ("Push-up", "push"), ("Bent-Over Dumbbell Row", "pull")], [("Bodyweight Squat", "legs"), ("Arm-Reach Crunch", "core")]),
            ]
        else:
            templates = [
                day("全身 A：腿、胸、背", [(squat, "legs"), (press, "push"), ("Seated Cable Row", "pull")], [("Romanian Deadlift", "legs"), ("Plank", "core")]),
                day("全身 B：臀腿、胸、背", [("Romanian Deadlift", "legs"), ("Machine Chest Press", "push"), ("Lat Pulldown", "pull")], [("Leg Press", "legs"), ("Plank", "core")]),
            ]
        return "居家全身训练 A/B" if home else "全身训练 A/B", templates, 1

    if days == 4 or home:
        if home:
            templates = [
                day("居家上肢：胸、背", [("Push-up", "push"), ("Bent-Over Dumbbell Row", "pull")], [("Bottle Lateral Raise", "push"), ("Arm-Reach Crunch", "core")]),
                day("居家下肢：腿、臀", [("Bodyweight Squat", "legs"), ("Chair Hip Hinge", "legs")], [("Elevated Calf Raise", "legs"), ("Arm-Reach Crunch", "core")]),
            ]
        else:
            templates = [
                day("上肢 A：卧推、划船", [(press, "push"), ("Seated Cable Row", "pull")], [("Dumbbell Shoulder Press", "push"), ("Lat Pulldown", "pull"), ("Cable Triceps Pressdown", "push")]),
                day("下肢 A：深蹲、硬拉", [(squat, "legs"), ("Romanian Deadlift", "legs")], [("Leg Press", "legs"), ("Plank", "core")]),
                day("上肢 B：上斜卧推、高位下拉", [("Incline Dumbbell Press", "push"), ("Lat Pulldown", "pull")], [("Machine Chest Press", "push"), ("Lateral Raise", "push"), ("Dumbbell Curl", "pull")]),
                day("下肢 B：腿举、硬拉", [("Leg Press", "legs"), ("Romanian Deadlift", "legs")], [("Goblet Squat", "legs"), ("Plank", "core")]),
            ]
        return "居家上下肢训练" if home else "上下肢训练", templates, 2

    templates = [
        day("推：胸部、肩部", [("Barbell Bench Press", "push"), ("Dumbbell Shoulder Press", "push")], [("Incline Dumbbell Press", "push"), ("Lateral Raise", "push"), ("Cable Triceps Pressdown", "push")]),
        day("拉：背部", [("Seated Cable Row", "pull"), ("Lat Pulldown", "pull")], [("Romanian Deadlift", "legs"), ("Dumbbell Curl", "pull")]),
        day("腿：深蹲、硬拉", [("Back Squat", "legs"), ("Romanian Deadlift", "legs")], [("Leg Press", "legs"), ("Plank", "core")]),
    ]
    return "推拉腿训练", templates, 3


def _fit_day(template: dict[str, Any], level: str, minutes: int) -> dict[str, Any]:
    candidates = deepcopy(template["exercises"])
    limits = {exercise["name"]: min(exercise["sets"], SET_CAPS[level]) for exercise in candidates}
    selected = [deepcopy(exercise) for exercise in candidates if exercise["is_core"]]
    for exercise in selected:
        exercise["sets"] = 1
    budget = minutes * 60
    if _breakdown(selected)["total_seconds"] > budget:
        raise ValueError("可用时间不足以完成基础动作、热身和休息，请增加单次时间。")

    def add_sets(group: list[dict[str, Any]]) -> None:
        while True:
            changed = False
            for exercise in group:
                if exercise["sets"] >= limits[exercise["name"]]:
                    continue
                exercise["sets"] += 1
                if _breakdown(selected)["total_seconds"] <= budget:
                    changed = True
                else:
                    exercise["sets"] -= 1
            if not changed:
                break

    add_sets(selected)
    for candidate in candidates:
        if candidate["is_core"]:
            continue
        candidate["sets"] = 1
        selected.append(candidate)
        if _breakdown(selected)["total_seconds"] > budget:
            selected.pop()
    add_sets([exercise for exercise in selected if not exercise["is_core"]])
    breakdown = _breakdown(selected)
    return {
        "focus": template["focus"],
        "warmup": ["先热身 5 分钟：轻松走动，活动关节，再用轻重量练习本节动作。需要时延长热身。"],
        "cooldown": ["收尾 2 分钟：轻松走动，调整呼吸。"],
        "exercises": selected,
        "rest_policy": source._session_rest_policy(selected),
        "session_note": "按顺序完成动作，留出余力，在姿势失稳前结束每组。疼痛或动作失控时停止。",
        "learning_points": ["每组留出还能完成 2–3 次的余力。", "排队、额外热身或动作节奏较慢时，用时会更长。"],
        "minutes_target": minutes,
        "estimated_minutes": ceil(breakdown["total_seconds"] / 60),
        "duration_breakdown": breakdown,
        "adaptation": {
            "source_sets": sum(exercise["source_prescription"]["sets"] for exercise in candidates),
            "planned_sets": sum(exercise["sets"] for exercise in selected),
            "removed_exercises": len(candidates) - len(selected),
        },
    }


def _recovery(index: int) -> dict[str, Any]:
    return {
        "day": f"休息日 {index}", "focus": "休息与轻松活动", "is_rest_day": True,
        "rest_note": "至少休息一天，再继续训练。一周内安排不下时顺延，不压缩休息。",
        "session_note": "保持轻松活动；疲劳或疼痛未缓解时继续休息。",
        "warmup": [], "exercises": [], "estimated_minutes": 0,
        "duration_breakdown": {key: 0 for key in ("warmup_seconds", "cooldown_seconds", "exercise_seconds", "rest_seconds", "transition_seconds", "total_seconds")},
        "adaptation": {"source_sets": 0, "planned_sets": 0, "removed_exercises": 0},
    }


def generate_fitted_plan(level: str, goal: str, days_per_week: int, minutes_per_session: int) -> dict[str, Any]:
    """Return a local trial sequence without modifying the source module."""
    if level not in FREQUENCY_CAPS or goal not in {"muscle_gain", "strength_gain", "fat_loss", "health"}:
        raise ValueError("请选择可用的训练水平与目标。")
    if type(days_per_week) is not int or not 1 <= days_per_week <= 7:
        raise ValueError("每周最多训练次数需为 1–7 的整数。")
    if type(minutes_per_session) is not int or not 15 <= minutes_per_session <= 180:
        raise ValueError("单次时间需为 15–180 分钟的整数。")

    frequency_cap = FREQUENCY_CAPS[level]
    scheduled = min(days_per_week, frequency_cap)
    split_name, templates, recovery_interval = _blueprints(level, goal, scheduled)
    goal_note = {
        "muscle_gain": "以基础力量动作锻炼主要肌群，保持动作稳定。",
        "strength_gain": "练习基础力量动作，先掌握动作，再逐步增加重量。",
        "fat_loss": "以力量训练为主，不估算热量消耗，也不保证减脂效果。",
        "health": "使用自重、水瓶或轻哑铃进行居家训练。",
    }[goal]
    notes = [
        "组数按时间和水平调整，组间休息不缩短。根据身体恢复情况减少训练量。",
        "按顺序训练并留出休息日。一周内安排不下时顺延，不压缩休息。",
        "教学视频的完整训练量可能更大，请以本站列出的组数和休息时间为准。",
    ]
    if scheduled < days_per_week:
        notes.insert(0, f"你选择每周最多 {days_per_week} 次。当前训练水平的试用上限为 {frequency_cap} 次，本次安排 {scheduled} 次。")

    schedule = []
    recovery_count = 0
    for index in range(scheduled):
        fitted = _fit_day(templates[index % len(templates)], level, minutes_per_session)
        fitted["day"] = f"训练日 {index + 1}"
        schedule.append(fitted)
        if (index + 1) % recovery_interval == 0 or index == scheduled - 1:
            recovery_count += 1
            schedule.append(_recovery(recovery_count))

    plan = {
        "level": level, "goal": goal,
        "days_per_week": scheduled, "minutes_per_session": minutes_per_session,
        "split": {"split_name": split_name, "days": scheduled, "reason": goal_note, "notes": notes},
        "weekly_schedule": schedule,
        "safety_note": "此计划未评估个人身体情况，不是医疗或康复建议。出现锐痛或持续加重的不适时停止，并寻求专业帮助。",
        "adaptation": {
            "version": "time-fit-v1", "requested_days": days_per_week,
            "scheduled_days": scheduled, "frequency_cap": frequency_cap,
            "requested_minutes": minutes_per_session, "notes": notes,
            "estimation_note": ESTIMATION_NOTE,
        },
        "source_metadata": {
            "module": "backend.plan_engine", "symbol": "_exercise",
            "reference_manifest": "references/gympath-original/plan-engine-source.json",
            "scope": "Recomposed exercise definitions, teaching links and original rests; no original named programme or progression rules.",
        },
    }
    localized = localize_plan(plan, preserve_original=True)
    # The translator walks nested display fields. Source prescriptions are
    # provenance, so restore their exact English source values after display
    # localisation; name_original remains alongside the visible action name.
    for original_day, translated_day in zip(plan["weekly_schedule"], localized["weekly_schedule"]):
        for original_exercise, translated_exercise in zip(original_day["exercises"], translated_day["exercises"]):
            translated_exercise["source_prescription"] = deepcopy(original_exercise["source_prescription"])
    return localized
