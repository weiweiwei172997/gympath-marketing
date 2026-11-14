"""GymPath's original deterministic training-plan engine, extracted in isolation.

Only the dependency closure of generate_workout_plan is included. Source spans
and the single catalog boundary change are recorded in
references/gympath-original/plan-engine-source.json. This module has no account
storage, file reads, environment configuration, network calls or AI provider.
"""

from __future__ import annotations

from typing import Any


VALID_GOALS = {
    "muscle_gain",
    "strength_gain",
    "fat_loss",
    "general_fitness",
    "health",
}


DIRECT_TEACHING_VIDEOS = {
    "Goblet Squat": {
        "title": "哑铃高脚杯深蹲保姆级教程 练臀练腿",
        "creator": "成都摸高教练王洪林",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1964y1V7Q6/",
    },
    "Dumbbell Bench Press": {
        "title": "健身动作教程｜哑铃卧推｜练胸推荐！",
        "creator": "ALEX健身频道",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1LM411z7sS/",
    },
    "Lat Pulldown": {
        "title": "谭成义的对握高位下拉",
        "creator": "谭成义",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV13TZRBJEat/",
    },
    "Romanian Deadlift": {
        "title": "透视学动作：罗马尼亚硬拉详解",
        "creator": "凯圣王",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1qF6wBaEWu/",
    },
    "Seated Cable Row": {
        "title": "女生练背｜坐姿划船｜高位下拉",
        "creator": "凯圣王",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1gy4y1o72X/",
    },
    "Leg Press": {
        "title": "腿举？应该这样做！",
        "creator": "一个热爱健身的上班族",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1bV4y1H7N1/",
    },
    "Machine Chest Press": {
        "title": "悍马机坐姿推胸保姆教学",
        "creator": "波CZB",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1AUiRYxEPp/",
    },
    "Dumbbell Shoulder Press": {
        "title": "坐姿哑铃推肩详解",
        "creator": "凯圣王",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1uw411N7MC/",
    },
    "Cable Triceps Pressdown": {
        "title": "肱三头肌绳索下压保姆级教程",
        "creator": "ALEX健身频道",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1fjMyzZEt5/",
    },
    "Dumbbell Curl": {
        "title": "哑铃弯举这么做更有效",
        "creator": "ALEX健身频道",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1anmCYNEbK/",
    },
    "Back Squat": {
        "title": "新手增肌系列：小体重深蹲干货",
        "creator": "凯圣王",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1BD4y1B7Z9/",
    },
    "Barbell Bench Press": {
        "title": "透视学动作：卧推详解",
        "creator": "凯圣王",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1ZHzMBmEtj/",
    },
    "Deadlift": {
        "title": "从零基础到做好一个硬拉",
        "creator": "凯圣王",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1fu4y1w7en/",
    },
    "Pull-up": {
        "title": "新手4步从0到1解锁引体向上",
        "creator": "风一野",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1RX8bzeEjp/",
    },
    "Incline Dumbbell Press": {
        "title": "上斜哑铃卧推保姆级教程",
        "creator": "ALEX健身频道",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1Dg4y1d75K/",
    },
    "Lateral Raise": {
        "title": "侧平举，如何避免斜方肌借力",
        "creator": "一个热爱健身的上班族",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV15e4deGEtu/",
    },
    "Walking Lunge": {
        "title": "箭步蹲正确示范",
        "creator": "ALEX健身频道",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1rd4y1p7Zi/",
    },
    "Plank": {
        "title": "平板支撑详解",
        "creator": "凯圣王",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV14w411V7Yj/",
    },
    "Push-up": {
        "title": "标准俯卧撑教学",
        "creator": "小波健身",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1Ui4y1b7Xk/",
    },
    "Bodyweight Squat": {
        "title": "新手入门系列｜徒手深蹲",
        "creator": "倪华香Yoki",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1AS4y1o7Lp/",
    },
}


BEGINNER_SESSION_VIDEOS = {
    "Beginner Chest Shoulders Triceps": {
        "title": "新手四分化训练 1：胸 + 肩 + 三头",
        "creator": "用户指定训练视频",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1S8ArzREru/",
    },
    "Beginner Back Biceps": {
        "title": "新手四分化训练 2：背 + 二头",
        "creator": "用户指定训练视频",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1mwPMzZEg8/",
    },
    "Beginner Lower Body": {
        "title": "新手四分化训练 3：下肢",
        "creator": "用户指定训练视频",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV13nPFzCENK/",
    },
    "Beginner Shoulders Arms": {
        "title": "新手四分化训练 4：肩 + 手臂",
        "creator": "用户指定训练视频",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV192Nwz4E9n/",
    },
}


HEALTH_HOME_SESSION_VIDEOS = {
    "Home Upper Body": {
        "title": "居家上肢训练",
        "creator": "用户指定训练视频",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1L2cazNELf/",
    },
    "Home Lower Body": {
        "title": "居家下肢与腹肌训练",
        "creator": "用户指定训练视频",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1LbcWzyE64/",
    },
}


WARMUP_TEACHING_VIDEOS = {
    "Beginner Chest Shoulders Triceps": {
        "title": "新手必看胸部训练教学：热身 + 激活 + 递增组",
        "creator": "小林爱健体",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1ja4y1a7BN/",
    },
    "Beginner Back Biceps": {
        "title": "背部训练前不会热身？练背前热身动作讲解",
        "creator": "EP健身",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1Ra4y1A76E/",
    },
    "Beginner Lower Body": {
        "title": "4分钟下肢动态热身",
        "creator": "刘教练体能康复",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1Gm41117EZ/",
    },
    "Beginner Shoulders Arms": {
        "title": "肩部训练前热身动作：强化肩膀灵活性与稳定性",
        "creator": "古德体育",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1sM4m1Q7i9/",
    },
}


def recommend_training_split(level: str, goal: str, days_per_week: int) -> dict[str, Any]:
    """Recommend a training split based on level, goal, and weekly days."""
    if days_per_week < 1 or days_per_week > 7:
        raise ValueError("days_per_week must be between 1 and 7")

    normalized_level = _normalize_level(level)
    normalized_goal = _normalize_goal(goal)

    if normalized_goal == "health":
        effective_days = max(2, days_per_week)
        return {
            "split_name": "Home Upper Lower Health",
            "days": effective_days,
            "reason": "Health-focused users get a low-barrier home plan split into upper body and lower body/core sessions.",
            "notes": [
                "Alternate upper-body and lower-body sessions.",
                "Use bottles, a chair, or bodyweight when gym equipment is unavailable.",
                "Stop if joint pain feels sharp or worsening.",
            ],
        }

    if normalized_level == "beginner":
        return {
            "split_name": "Beginner Four-Day Split",
            "days": 4,
            "reason": "Beginners use a guided four-day split with fixed videos to reduce decision cost and follow a clear progression.",
            "notes": [
                "Follow the four sessions in order.",
                "Rest one day after the lower-body session before the shoulder and arms session.",
                "Keep loads conservative while learning movement patterns.",
            ],
        }

    if normalized_level == "restarting":
        return {
            "split_name": "Push Pull Legs Restart" if days_per_week <= 3 else "Upper Lower Restart",
            "days": days_per_week,
            "reason": "Restarting users need enough stimulus without making the first week feel punishing.",
            "notes": ["Start with fewer sets.", "Increase only after consistency returns."],
        }

    if days_per_week >= 5:
        return {
            "split_name": "Push Pull Legs",
            "days": days_per_week,
            "reason": "Experienced lifters can benefit from higher frequency and more specialization.",
            "notes": ["Track recovery.", "Use substitutions when a movement does not feel right."],
        }

    if days_per_week == 4:
        return {
            "split_name": "Upper Lower",
            "days": days_per_week,
            "reason": "Upper/lower training balances frequency, recovery, and progression.",
            "notes": ["Use progressive overload.", "Keep one or two reps in reserve on most sets."],
        }

    return {
        "split_name": "Push Pull Legs",
        "days": days_per_week,
        "reason": "Fewer weekly sessions can still rotate push, pull, and legs without a mixed whole-session template.",
        "notes": ["Rotate the next split day each session.", "Keep accessory work focused."],
    }


def generate_workout_plan(
    level: str,
    goal: str,
    days_per_week: int,
    minutes_per_session: int = 60,
    strength_plan_type: str = "auto",
    muscle_gain_plan_type: str = "auto",
) -> dict[str, Any]:
    """Generate a simple weekly training plan."""
    if minutes_per_session < 15:
        raise ValueError("minutes_per_session must be at least 15")
    if days_per_week < 1 or days_per_week > 7:
        raise ValueError("days_per_week must be between 1 and 7")

    normalized_level = _normalize_level(level)
    normalized_goal = _normalize_goal(goal)
    if normalized_goal == "health":
        split = recommend_training_split(normalized_level, normalized_goal, days_per_week)
        effective_days = int(split["days"])
        return enrich_workout_plan(
            {
                "level": normalized_level,
                "goal": normalized_goal,
                "days_per_week": effective_days,
                "minutes_per_session": minutes_per_session,
                "split": split,
                "weekly_schedule": _health_home_schedule(effective_days, minutes_per_session),
                "safety_note": "GymPath gives fitness education, not medical diagnosis. Stop for sharp or worsening pain.",
            },
        )

    if normalized_goal == "strength_gain":
        return enrich_workout_plan(
            _strength_workout_plan(
                level=normalized_level,
                days_per_week=days_per_week,
                minutes_per_session=minutes_per_session,
                strength_plan_type=strength_plan_type,
            ),
        )
    if normalized_goal == "muscle_gain":
        return enrich_workout_plan(
            _muscle_gain_workout_plan(
                level=normalized_level,
                days_per_week=days_per_week,
                minutes_per_session=minutes_per_session,
                muscle_gain_plan_type=muscle_gain_plan_type,
            ),
        )

    split = recommend_training_split(normalized_level, normalized_goal, days_per_week)
    if normalized_level == "beginner":
        weekly_schedule = _beginner_four_day_schedule(minutes_per_session)
        return enrich_workout_plan(
            {
                "level": normalized_level,
                "goal": normalized_goal,
                "days_per_week": 4,
                "minutes_per_session": minutes_per_session,
                "split": split,
                "weekly_schedule": weekly_schedule,
                "safety_note": "GymPath gives fitness education, not medical diagnosis. Stop for sharp or worsening pain.",
            },
        )

    templates = _plan_templates(normalized_level, normalized_goal, split["split_name"])
    max_exercises = 4 if minutes_per_session < 50 else 5 if minutes_per_session < 75 else 6

    weekly_schedule: list[dict[str, Any]] = []
    for index in range(days_per_week):
        template = templates[index % len(templates)]
        exercises = [_exercise(name) for name in template["exercises"][:max_exercises]]
        weekly_schedule.append(
            {
                "day": f"Day {index + 1}",
                "focus": template["focus"],
                "warmup": _warmup_for_focus(template["focus"]),
                "exercises": exercises,
                "rest_policy": _session_rest_policy(exercises),
                "session_note": _session_note(normalized_level, normalized_goal, minutes_per_session),
            }
        )

    return enrich_workout_plan(
        {
            "level": normalized_level,
            "goal": normalized_goal,
            "days_per_week": days_per_week,
            "minutes_per_session": minutes_per_session,
            "split": split,
            "weekly_schedule": weekly_schedule,
            "safety_note": "GymPath gives fitness education, not medical diagnosis. Stop for sharp or worsening pain.",
        },
    )


def enrich_workout_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Return an independent plan dictionary without optional catalog metadata.

    The marketing trial retains original training prescriptions and teaching
    links. The complete exercise catalog is outside this stage's scope.
    """
    return dict(plan)


def _normalize_goal(goal: str) -> str:
    normalized = goal.lower().strip().replace("-", "_").replace(" ", "_")
    aliases = {
        "gain_muscle": "muscle_gain",
        "build_muscle": "muscle_gain",
        "strength": "strength_gain",
        "lose_fat": "fat_loss",
        "weight_loss": "fat_loss",
        "fitness": "general_fitness",
        "general": "general_fitness",
        "healthy": "health",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in VALID_GOALS:
        raise ValueError(f"Unsupported goal: {goal}")
    return normalized


def _normalize_level(level: str) -> str:
    normalized = level.lower().strip().replace("-", "_").replace(" ", "_")
    aliases = {
        "new": "beginner",
        "novice": "beginner",
        "intermediate": "restarting",
        "inconsistent": "restarting",
        "restart": "restarting",
        "advanced": "experienced",
        "veteran": "experienced",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"beginner", "restarting", "experienced"}:
        raise ValueError(f"Unsupported level: {level}")
    return normalized


MIN_REST_SECONDS = 120


LONG_REST_SECONDS = 180


HEAVY_REST_EXERCISES = {
    "Back Squat",
    "Barbell Bench Press",
    "Deadlift",
    "Pull-up",
    "Romanian Deadlift",
    "Single-Leg Dumbbell Romanian Deadlift",
    "Walking Lunge",
    "Rotational Lunge",
    "Leg Press",
    "Incline Machine Chest Press",
    "Barbell Overhead Press",
}


def _recommended_rest_seconds(name: str, requested_rest_seconds: int) -> int:
    rest_seconds = max(int(requested_rest_seconds), MIN_REST_SECONDS)
    if name in HEAVY_REST_EXERCISES:
        return max(rest_seconds, LONG_REST_SECONDS)
    return rest_seconds


def _exercise(
    name: str,
    *,
    sets_override: int | None = None,
    reps_override: str | None = None,
    rest_override: int | None = None,
    note_override: str | None = None,
    phase: str | None = None,
    teaching_video: dict[str, str] | None = None,
) -> dict[str, Any]:
    library = {
        "Cable Fly": ("4", "12", 60, "Chest", "Keep shoulders down and squeeze the chest without shrugging."),
        "Goblet Squat": ("3", "8-12", 90, "Legs", "Keep torso tall and knees tracking over toes."),
        "Dumbbell Bench Press": ("3", "8-12", 90, "Chest", "Use a stable shoulder position and controlled range."),
        "Lat Pulldown": ("3", "10-12", 75, "Back", "Pull elbows down and avoid shrugging."),
        "Romanian Deadlift": ("3", "8-10", 120, "Hamstrings", "Hinge at hips and keep the back neutral."),
        "Seated Cable Row": ("3", "10-12", 75, "Back", "Drive elbows back and pause briefly."),
        "Single-Arm Seated Cable Row": ("4", "12", 75, "Back", "Keep torso quiet and pull the elbow toward the hip."),
        "Close-Grip Seated Cable Row": ("4", "12", 75, "Back", "Pull through the elbows and pause without leaning back."),
        "Straight-Arm Pulldown": ("4", "12-15", 60, "Lats", "Keep arms nearly straight and drive the bar toward the thighs."),
        "Leg Press": ("3", "10-15", 90, "Legs", "Use a controlled depth without hip rounding."),
        "Machine Chest Press": ("3", "8-12", 90, "Chest", "Keep shoulder blades stable."),
        "Incline Machine Chest Press": ("4", "12", 90, "Upper Chest", "Keep shoulders packed and press along the machine path."),
        "Dumbbell Shoulder Press": ("3", "8-12", 90, "Shoulders", "Press smoothly without leaning back."),
        "Seated Overhead Press": ("3", "8-12", 120, "Shoulders", "Press from a stable seated position."),
        "Barbell Overhead Press": ("4", "12", 120, "Shoulders", "Brace hard and keep the bar path close."),
        "Pendlay Row": ("5", "5", 150, "Back", "Reset each rep from the floor."),
        "Chin-up": ("3", "5-8", 120, "Back", "Use a controlled full range."),
        "Overhead Cable Triceps Extension": ("4", "12", 60, "Triceps", "Keep elbows pointed forward and stretch the long head under control."),
        "Cable Triceps Pressdown": ("2", "10-15", 60, "Arms", "Keep elbows pinned and control the return."),
        "Dumbbell Curl": ("2", "10-15", 60, "Arms", "Avoid swinging and squeeze at the top."),
        "Cable Curl": ("4", "12", 60, "Biceps", "Keep elbows still and control the return."),
        "Barbell Curl": ("4", "12", 60, "Biceps", "Avoid hip swing and keep wrists stacked."),
        "Back Squat": ("4", "5-8", 150, "Legs", "Brace before each rep and keep balance mid-foot."),
        "Barbell Bench Press": ("4", "5-8", 150, "Chest", "Set shoulder blades and use a consistent touch point."),
        "Deadlift": ("3", "3-5", 180, "Posterior Chain", "Keep the bar close and brace hard."),
        "Pull-up": ("3", "6-10", 120, "Back", "Use full control and avoid swinging."),
        "Incline Dumbbell Press": ("3", "8-12", 90, "Upper Chest", "Use a comfortable angle and controlled reps."),
        "Lateral Raise": ("3", "12-20", 45, "Shoulders", "Lead with elbows and avoid heavy swinging."),
        "Seated Reverse Fly": ("4", "12", 60, "Rear Delts", "Open from the rear delts and avoid shrugging."),
        "Cable Face Pull": ("4", "10", 60, "Rear Delts", "Pull toward the face with elbows high and external rotation."),
        "Front Raise": ("4", "10", 60, "Front Delts", "Raise under control without leaning back."),
        "Barbell Front Raise": ("3", "10-12", 60, "Front Delts", "Raise under control."),
        "Machine Fly": ("3", "10-12", 75, "Chest", "Use a stable machine path."),
        "Shoulder Stability Drill": ("3", "12-15", 60, "Shoulders", "Use light controlled reps."),
        "Back Extension": ("3", "12-15", 75, "Posterior Chain", "Use a controlled range."),
        "Wall Sit": ("3", "45-60 sec", 60, "Legs", "Hold a stable knee angle."),
        "Hip Adduction Machine / Copenhagen Plank": ("4", "15 or 20-30 sec", 60, "Adductors", "Choose the machine or Copenhagen plank based on control and comfort."),
        "Single-Leg Dumbbell Romanian Deadlift": ("3", "12 each side", 90, "Hamstrings", "Hinge on one leg and keep hips square."),
        "Walking Lunge": ("3", "10 each side", 90, "Legs", "Step long enough to stay balanced."),
        "Rotational Lunge": ("3", "10 each side", 75, "Legs", "Rotate with control and keep the front knee tracking well."),
        "Standing Calf Raise": ("3", "15", 60, "Calves", "Pause at the top and control the stretch at the bottom."),
        "Plank": ("3", "30-60 sec", 45, "Core", "Keep ribs down and glutes lightly squeezed."),
        "Push-up": ("3", "6-15", 60, "Chest", "Keep a straight line and control the bottom."),
        "Bodyweight Squat": ("3", "10-20", 60, "Legs", "Move smoothly and keep feet planted."),
        "Incline Push-up": ("4", "near failure", 120, "Upper Chest", "Elevate the feet or use a bed/chair setup based on control."),
        "Rear Delt Bottle Raise": ("4", "near failure", 120, "Rear Delts", "Use bottles or light dumbbells and stop when the rear delts lose control."),
        "Bottle Lateral Raise": ("4", "near failure", 120, "Side Delts", "Raise through the elbows with a light household load."),
        "Bottle Front Raise": ("4", "near failure", 120, "Front Delts", "Use a neutral grip if the shoulder feels stressed."),
        "Bench Dips": ("4", "about 24", 120, "Triceps", "Use a chair or bench and adjust foot position for difficulty."),
        "Kneeling Ab Wheel": ("4", "near failure", 120, "Core / Back", "Use a kneeling setup and keep range controllable."),
        "Bent-Over Dumbbell Row": ("4", "until back has a clear pump", 120, "Back", "Use dumbbells, bottles, or another safe household load."),
        "Arm-Reach Crunch": ("4", "near failure", 120, "Abs", "Reach arms upward and keep the movement small enough to protect the low back."),
        "Single-Leg Hamstring Activation": ("4", "10 each side", 120, "Hamstrings", "Use a light object and focus on the back-side stretch."),
        "Chair Hip Hinge": ("4", "15-16 each side", 120, "Glutes / Hips", "Use a chair or wall for support and keep tension in the hip."),
        "Groin Mobility Split Squat": ("3", "10-12 each side", 120, "Hips / Adductors", "Use a small range at first and build hip comfort."),
        "Elevated Calf Raise": ("4", "20", 120, "Calves", "Elevate the forefoot and use slow lowering with a quick rise."),
        "Dips": ("4", "12 or near failure", 120, "Chest / Triceps", "Use assistance if needed."),
        "Lying Triceps Extension": ("4", "15", 120, "Triceps", "Use a controllable stretch."),
        "Y-Raise Lateral Raise": ("3", "10 + 10 to failure", 120, "Side Delts", "Use light dumbbells."),
        "Single-Arm Cable Pulldown": ("4", "12 + 10 to failure + 5", 120, "Lats", "Use one side at a time."),
        "Neutral-Grip Pulldown": ("4", "12-8", 120, "Back", "Choose a load you can control."),
        "Single-Arm Machine Row": ("4", "10", 120, "Back", "Train each side evenly."),
        "Open-Elbow Seated Row": ("4", "15-12", 120, "Upper Back", "Open the elbows to bias upper back."),
        "Bulgarian Split Squat": ("4", "10", 120, "Glutes / Quads", "Use support if balance limits output."),
        "Front Squat": ("3", "15", 150, "Quads", "Keep the load conservative."),
        "Straight-Leg Barbell Bench Press": ("4", "8", 150, "Chest", "Use the requested percent-based load."),
        "Incline Barbell Bench Press": ("4", "8", 150, "Upper Chest", "Use steady bar speed."),
        "Seal Row": ("4", "10", 120, "Back", "Use a chest-supported setup."),
        "Reverse-Grip Machine Row": ("4", "10", 120, "Back", "Keep the handle close to the body."),
        "Reverse-Grip Lat Pulldown": ("4", "10-13", 120, "Lats", "Use a controlled grip."),
        "Bent-Over Dumbbell Reverse Fly": ("4", "12", 120, "Rear Delts", "Use a light load."),
        "Reverse Pec Deck": ("4", "10-12", 120, "Rear Delts", "Use a controlled machine path."),
        "Incline Bench Lateral Raise": ("4", "10", 120, "Side Delts", "Use the bench to limit cheating."),
        "Seated Lateral Raise": ("4", "12-15", 120, "Side Delts", "Keep the load strict."),
        "Hammer Dumbbell Curl": ("4", "10", 120, "Biceps / Brachialis", "Use neutral grip."),
        "Incline Barbell Triceps Extension": ("4", "10", 120, "Triceps", "Use a controllable stretch."),
        "Cable Crunch": ("4", "12-15", 120, "Core", "Curl through the abs."),
        "Plate Crunch": ("4", "12-15", 120, "Core", "Hold the plate under control."),
        "Deficit Deadlift": ("3", "3", 180, "Posterior Chain", "Use the programmed percentage."),
        "T-Bar Row": ("4", "10", 120, "Back", "Keep reps controlled."),
        "Kneeling Cable Crunch": ("4", "15", 120, "Core", "Use a stable kneeling setup."),
        "Side Cable Crunch": ("4", "12", 120, "Core", "Train each side evenly."),
    }
    sets, reps, rest, muscle, notes = library[name]
    selected_video = teaching_video or _teaching_video(name)
    requested_rest = rest_override if rest_override is not None else rest
    rest_seconds = _recommended_rest_seconds(name, int(requested_rest))
    exercise = {
        "name": name,
        "sets": sets_override if sets_override is not None else int(sets),
        "reps": reps_override or reps,
        "rest_seconds": rest_seconds,
        "target_muscle": muscle,
        "notes": note_override or notes,
        "teaching_url": selected_video["url"],
        "substitutions": _default_substitutions(name),
    }
    if phase:
        exercise["phase"] = phase
    return exercise


def _muscle_gain_workout_plan(
    *,
    level: str,
    days_per_week: int,
    minutes_per_session: int,
    muscle_gain_plan_type: str,
) -> dict[str, Any]:
    selected = _normalize_muscle_gain_plan_type(muscle_gain_plan_type, level)
    if selected == "tan_chengyi_beginner_follow":
        split = {
            "split_name": "Tan Chengyi Beginner Follow Along",
            "days": 4,
            "reason": "把原来的新手增肌计划命名为谭成义新手跟练，用固定四次训练降低决策成本。",
            "notes": ["按视频顺序执行。", "下肢后休息一天。", "先学会动作顺序，再逐步增加重量。"],
        }
        schedule = _beginner_four_day_schedule(minutes_per_session)
    elif selected == "tan_kaisheng_three_split":
        split = {
            "split_name": "Tan Chengyi Kaisheng Three-Day Split",
            "days": 3,
            "reason": "三分化线性增肌计划：胸肩三头、背后束二头、臀腿后链，适合想更像健身房训练的人。",
            "notes": ["每周按三天循环。", "先完成规定组次，再考虑加重量。", "动作感受差时优先替换同部位动作。"],
        }
        schedule = _tan_kaisheng_three_split_schedule(minutes_per_session)
    else:
        split = {
            "split_name": "Orange Three-Phase Hypertrophy",
            "days": 5,
            "reason": "橙子增肌计划按肌肥大、增肌增力、增力三个阶段推进，适合想用周期训练突破的人。",
            "notes": ["先跑完第一阶段三周。", "第二阶段提高卧推和深蹲强度。", "第三阶段用更高百分比转化力量。"],
        }
        schedule = _orange_hypertrophy_schedule(minutes_per_session)

    return {
        "level": level,
        "goal": "muscle_gain",
        "days_per_week": split["days"],
        "minutes_per_session": minutes_per_session,
        "split": split,
        "muscle_gain_plan": _muscle_gain_plan_brief(selected),
        "weekly_schedule": schedule,
        "safety_note": "GymPath gives fitness education, not medical diagnosis. Stop for sharp or worsening pain.",
    }


def _normalize_muscle_gain_plan_type(plan_type: str, level: str) -> str:
    normalized = plan_type.lower().strip().replace("-", "_").replace(" ", "_")
    aliases = {
        "auto": "",
        "beginner": "tan_chengyi_beginner_follow",
        "tan_chengyi": "tan_chengyi_beginner_follow",
        "tan_chengyi_beginner": "tan_chengyi_beginner_follow",
        "three_split": "tan_kaisheng_three_split",
        "tan_kaisheng": "tan_kaisheng_three_split",
        "tan_chengyi_kaisheng": "tan_kaisheng_three_split",
        "orange": "orange_hypertrophy",
        "orange_bulk": "orange_hypertrophy",
    }
    normalized = aliases.get(normalized, normalized)
    if not normalized:
        if level == "beginner":
            return "tan_chengyi_beginner_follow"
        return "tan_kaisheng_three_split"
    if normalized not in {"tan_chengyi_beginner_follow", "tan_kaisheng_three_split", "orange_hypertrophy"}:
        raise ValueError(f"Unsupported muscle gain plan type: {plan_type}")
    return normalized


def _muscle_day(
    *,
    day: str,
    focus: str,
    exercises: list[tuple[str, str, int, str, int]],
    session_note: str,
    warmup: list[str],
    learning_points: list[str] | None = None,
    minutes_target: int,
) -> dict[str, Any]:
    built_exercises = [
        _exercise(
            name,
            sets_override=sets,
            reps_override=reps,
            rest_override=rest,
            phase=phase,
        )
        for phase, name, sets, reps, rest in exercises
    ]
    day_plan = {
        "day": day,
        "focus": focus,
        "warmup": warmup,
        "exercises": built_exercises,
        "rest_policy": _session_rest_policy(built_exercises),
        "session_note": session_note,
        "minutes_target": minutes_target,
    }
    if learning_points:
        day_plan["learning_points"] = learning_points
    return day_plan


def _program_rest_day(day: str, note: str) -> dict[str, Any]:
    return {
        "day": day,
        "focus": "恢复日",
        "is_rest_day": True,
        "rest_note": note,
        "session_note": "Recovery day: no hard training.",
        "warmup": [],
        "exercises": [],
    }


def _tan_kaisheng_three_split_schedule(minutes_per_session: int) -> list[dict[str, Any]]:
    return [
        _muscle_day(
            day="训练日 1",
            focus="胸 + 三角肌中束 + 三头肌",
            warmup=["5 min upper-body cardio", "Band chest openers", "Bench press ramp-up sets"],
            session_note="三分化线性训练：胸、三角肌中束、三头肌。卧推先热身，再进入正式递减次数组。",
            learning_points=["卧推完成规定次数后，下次优先小幅加重量。", "侧平举用力竭组补足三角肌中束刺激。"],
            minutes_target=minutes_per_session,
            exercises=[
                ("主项", "Barbell Bench Press", 4, "15热身 + 12-10-8正式", 150),
                ("主项", "Incline Dumbbell Press", 4, "12", 120),
                ("主项", "Dips", 4, "12或力竭", 120),
                ("辅项", "Lying Triceps Extension", 4, "15", 120),
                ("辅项", "Y-Raise Lateral Raise", 3, "10 + 10力竭", 120),
            ],
        ),
        _muscle_day(
            day="训练日 2",
            focus="背 + 三角肌后束 + 二头肌",
            warmup=["5 min easy rower", "Straight-arm pulldown warm-up", "Light cable row ramp-up sets"],
            session_note="三分化线性训练：背、后束、二头。先用单侧下拉找背阔，再进入划船和弯举。",
            learning_points=["背部训练先找目标肌肉，再加重量。", "划船和下拉都完成后，再用弯举补二头。"],
            minutes_target=minutes_per_session,
            exercises=[
                ("主项", "Single-Arm Cable Pulldown", 4, "12 + 10力竭 + 5", 120),
                ("主项", "Neutral-Grip Pulldown", 4, "12-8", 120),
                ("主项", "Single-Arm Machine Row", 4, "10", 120),
                ("主项", "Open-Elbow Seated Row", 4, "15-12", 120),
                ("辅项", "Cable Curl", 3, "12", 120),
            ],
        ),
        _muscle_day(
            day="训练日 3",
            focus="臀 + 股四头肌 + 腘绳肌",
            warmup=["5 min incline walk or bike", "Hip circles", "Bodyweight lunges", "Bodyweight squat ramp-up"],
            session_note="三分化线性训练：臀、股四头肌、腘绳肌。以单腿控制和髋膝稳定为主。",
            learning_points=["单腿动作先保证平衡。", "硬拉类动作放在能控制后链张力的重量。"],
            minutes_target=minutes_per_session,
            exercises=[
                ("主项", "Single-Leg Dumbbell Romanian Deadlift", 4, "12", 120),
                ("主项", "Bulgarian Split Squat", 4, "10", 120),
                ("主项", "Front Squat", 3, "15", 150),
                ("主项", "Romanian Deadlift", 3, "12", 150),
                ("辅项", "Back Extension", 3, "8", 120),
            ],
        ),
    ]


def _orange_hypertrophy_schedule(minutes_per_session: int) -> list[dict[str, Any]]:
    phase_one = [
        _muscle_day(
            day="第一阶段 第一天",
            focus="胸",
            warmup=["5 min upper-body cardio", "Band chest openers", "Bench press ramp-up sets"],
            session_note="第一阶段肌肥大训练：胸部，连续三周，注意控制动作和重量。",
            learning_points=["第一阶段以70%左右重量完成容量。", "每组都保留稳定动作质量。"],
            minutes_target=minutes_per_session,
            exercises=[
                ("第一阶段", "Straight-Leg Barbell Bench Press", 4, "8（70%）", 150),
                ("第一阶段", "Incline Barbell Bench Press", 4, "8", 150),
                ("第一阶段", "Incline Dumbbell Press", 4, "10", 120),
                ("第一阶段", "Machine Fly", 4, "10", 120),
            ],
        ),
        _muscle_day(
            day="第一阶段 第二天",
            focus="背部",
            warmup=["5 min easy rower", "Straight-arm pulldown warm-up", "Light row ramp-up sets"],
            session_note="第一阶段肌肥大训练：背部，优先稳定划船和下拉容量。",
            minutes_target=minutes_per_session,
            exercises=[
                ("第一阶段", "Seal Row", 4, "10", 120),
                ("第一阶段", "Reverse-Grip Machine Row", 4, "10", 120),
                ("第一阶段", "Neutral-Grip Pulldown", 4, "10-12", 120),
                ("第一阶段", "Reverse-Grip Lat Pulldown", 4, "10-13", 120),
            ],
        ),
        _muscle_day(
            day="第一阶段 第三天",
            focus="肩膀",
            warmup=["5 min upper-body cardio", "Band external rotations", "Face pull warm-up set"],
            session_note="第一阶段肌肥大训练：肩膀，注意控制，不追求甩大重量。",
            minutes_target=minutes_per_session,
            exercises=[
                ("第一阶段", "Bent-Over Dumbbell Reverse Fly", 4, "12", 120),
                ("第一阶段", "Reverse Pec Deck", 4, "10-12", 120),
                ("第一阶段", "Incline Bench Lateral Raise", 4, "10", 120),
                ("第一阶段", "Seated Lateral Raise", 4, "12-15", 120),
            ],
        ),
        _program_rest_day("第一阶段 第四天", "休息一天，准备胸和手臂训练。"),
        _muscle_day(
            day="第一阶段 第五天",
            focus="胸 + 手臂",
            warmup=["5 min upper-body cardio", "Bench press ramp-up sets", "Light curl and pressdown warm-up"],
            session_note="第一阶段肌肥大训练：胸和手臂，卧推按极限72.5%左右安排。",
            minutes_target=minutes_per_session,
            exercises=[
                ("第一阶段", "Straight-Leg Barbell Bench Press", 4, "8（极限72.5%）", 150),
                ("第一阶段", "Hammer Dumbbell Curl", 4, "10", 120),
                ("第一阶段", "Incline Barbell Triceps Extension", 4, "10", 120),
                ("第一阶段", "Barbell Curl", 4, "10", 120),
                ("第一阶段", "Cable Triceps Pressdown", 4, "10", 120),
            ],
        ),
        _muscle_day(
            day="第一阶段 第六天",
            focus="腿 + 核心",
            warmup=["5 min incline walk or bike", "Hip circles", "Bodyweight squat ramp-up"],
            session_note="第一阶段肌肥大训练：深蹲和罗马尼亚硬拉按70%左右重量完成容量。",
            minutes_target=minutes_per_session,
            exercises=[
                ("第一阶段", "Back Squat", 4, "8（70%）", 150),
                ("第一阶段", "Romanian Deadlift", 4, "8", 150),
                ("核心", "Cable Crunch", 4, "12", 120),
                ("核心", "Plate Crunch", 4, "12-15", 120),
            ],
        ),
        _program_rest_day("第一阶段 第七天", "休息一天，完成第一阶段循环。"),
    ]

    phase_two = [
        _muscle_day(
            day="第二阶段 第一天",
            focus="胸 + 肩中束",
            warmup=["5 min upper-body cardio", "Bench press ramp-up sets", "Lateral raise warm-up set"],
            session_note="第二阶段增肌增力：卧推先做83%低次数，再做72.5%容量组。",
            learning_points=["卧推专项第一周从83%开始。", "后续每周按计划提高百分比。"],
            minutes_target=minutes_per_session,
            exercises=[
                ("第二阶段", "Barbell Bench Press", 3, "4（83%）", 180),
                ("第二阶段", "Barbell Bench Press", 3, "7（72.5%）", 150),
                ("第二阶段", "Lateral Raise", 4, "10-12", 120),
                ("第二阶段", "Seated Lateral Raise", 4, "10-12", 120),
            ],
        ),
        _muscle_day(
            day="第二阶段 第二天",
            focus="背部 + 肩后束",
            warmup=["5 min easy rower", "Hip hinge ramp-up", "Light pulldown warm-up"],
            session_note="第二阶段增肌增力：超程硬拉从65%开始，每次增加5公斤。",
            minutes_target=minutes_per_session,
            exercises=[
                ("第二阶段", "Deficit Deadlift", 3, "3（65%，每次+5kg）", 180),
                ("第二阶段", "T-Bar Row", 4, "10", 120),
                ("第二阶段", "Neutral-Grip Pulldown", 4, "10", 120),
                ("第二阶段", "Bent-Over Dumbbell Reverse Fly", 4, "12", 120),
                ("第二阶段", "Reverse Pec Deck", 4, "10", 120),
            ],
        ),
        _program_rest_day("第二阶段 第三天", "休息一天，保留神经和关节恢复空间。"),
        _muscle_day(
            day="第二阶段 第四天",
            focus="胸 + 手臂",
            warmup=["5 min upper-body cardio", "Bench press ramp-up sets", "Arm warm-up sets"],
            session_note="第二阶段增肌增力：第二个卧推训练日提高到84%，再补手臂容量。",
            minutes_target=minutes_per_session,
            exercises=[
                ("第二阶段", "Barbell Bench Press", 3, "4（84%）", 180),
                ("第二阶段", "Barbell Bench Press", 3, "7（72.5%）", 150),
                ("第二阶段", "Hammer Dumbbell Curl", 4, "10", 120),
                ("第二阶段", "Incline Barbell Triceps Extension", 4, "10", 120),
                ("第二阶段", "Cable Triceps Pressdown", 4, "12", 120),
            ],
        ),
        _muscle_day(
            day="第二阶段 第五天",
            focus="腿 + 核心",
            warmup=["5 min incline walk or bike", "Bodyweight squat ramp-up", "Cable crunch warm-up set"],
            session_note="第二阶段增肌增力：深蹲先做83%低次数，再做72.5%容量组。",
            minutes_target=minutes_per_session,
            exercises=[
                ("第二阶段", "Back Squat", 3, "4（83%）", 180),
                ("第二阶段", "Back Squat", 3, "7（72.5%）", 150),
                ("核心", "Kneeling Cable Crunch", 4, "15", 120),
                ("核心", "Plate Crunch", 4, "12-15", 120),
            ],
        ),
        _program_rest_day("第二阶段 第六至七天", "休息2天。卧推专项：第1-3周83%-88%，第4周减载，第5-7周90%-95%，第8周减载后测极限。"),
    ]

    phase_three = [
        _muscle_day(
            day="第三阶段 第一天",
            focus="胸",
            warmup=["5 min upper-body cardio", "Bench press ramp-up sets", "Incline press warm-up set"],
            session_note="第三阶段增力：卧推进入90%低次数，再用78%回补容量。",
            learning_points=["卧推专项从87%开始，每周增加1.5%。", "后半程进入单次冲刺前必须安排减载。"],
            minutes_target=minutes_per_session,
            exercises=[
                ("第三阶段", "Barbell Bench Press", 3, "2（90%）", 180),
                ("第三阶段", "Barbell Bench Press", 3, "5（78%）", 150),
                ("第三阶段", "Incline Dumbbell Press", 3, "8", 120),
                ("第三阶段", "Seated Lateral Raise", 3, "10-12", 120),
            ],
        ),
        _muscle_day(
            day="第三阶段 第二天",
            focus="背部 + 后束",
            warmup=["5 min easy rower", "Hip hinge ramp-up", "Light row warm-up sets"],
            session_note="第三阶段增力：硬拉和划船维持高质量输出，后束补容量。",
            minutes_target=minutes_per_session,
            exercises=[
                ("第三阶段", "Deficit Deadlift", 3, "3", 180),
                ("第三阶段", "T-Bar Row", 4, "10", 120),
                ("第三阶段", "Neutral-Grip Pulldown", 4, "10", 120),
                ("第三阶段", "Reverse Pec Deck", 4, "12", 120),
            ],
        ),
        _program_rest_day("第三阶段 第三天", "休息一天，准备第二个卧推训练日。"),
        _muscle_day(
            day="第三阶段 第四天",
            focus="胸 + 手臂",
            warmup=["5 min upper-body cardio", "Bench press ramp-up sets", "Arm warm-up sets"],
            session_note="第三阶段增力：第二个卧推日继续高强度，手臂只做必要容量。",
            minutes_target=minutes_per_session,
            exercises=[
                ("第三阶段", "Barbell Bench Press", 3, "2（90%）", 180),
                ("第三阶段", "Barbell Bench Press", 3, "5", 150),
                ("第三阶段", "Barbell Curl", 4, "10", 120),
                ("第三阶段", "Cable Triceps Pressdown", 4, "12", 120),
            ],
        ),
        _muscle_day(
            day="第三阶段 第五天",
            focus="腿 + 核心",
            warmup=["5 min incline walk or bike", "Bodyweight squat ramp-up", "Core warm-up"],
            session_note="第三阶段增力：深蹲用83%低次数和78%回补容量。",
            minutes_target=minutes_per_session,
            exercises=[
                ("第三阶段", "Back Squat", 3, "2（83%）", 180),
                ("第三阶段", "Back Squat", 3, "5（78%）", 150),
                ("核心", "Kneeling Cable Crunch", 4, "15", 120),
                ("核心", "Side Cable Crunch", 4, "12", 120),
            ],
        ),
        _program_rest_day("第三阶段 第六至七天", "休息2天。卧推专项：第1-3周87%-94.5%，第4周减载，第5-7周97.5%-102.5%，第8周测极限后减载。"),
    ]

    return phase_one + phase_two + phase_three


def _muscle_gain_plan_brief(plan_type: str) -> dict[str, Any]:
    briefs = {
        "tan_chengyi_beginner_follow": {
            "title": "谭成义新手跟练",
            "audience": "刚开始增肌、需要直接照视频练、不想自己排计划的新手。",
            "source_basis": "原新手四分化计划重命名为谭成义新手跟练。",
            "logic_points": ["固定四次训练降低选择成本。", "胸肩三头、背二头、下肢、肩手臂按顺序推进。", "下肢后插入休息日。"],
            "progression_rules": ["先完成视频动作顺序。", "动作稳定后再小幅加重量。", "训练反馈太累时减少组数或延长周期。"],
            "warnings": ["明显疼痛时不要硬顶。", "新手先学动作，不把重量当成唯一目标。"],
        },
        "tan_kaisheng_three_split": {
            "title": "谭成义+凯圣王三分化",
            "audience": "想进入健身房分化训练、追求增肌和线性进步的用户。",
            "source_basis": "来自用户提供的视频总结：三分化线性训练计划。",
            "logic_points": ["训练日1练胸、三角肌中束、三头。", "训练日2练背、三角肌后束、二头。", "训练日3练臀、股四头肌、腘绳肌。"],
            "progression_rules": ["每周循环三天。", "规定组次能稳定完成后再加重量。", "单侧动作左右都要完成同样质量。"],
            "warnings": ["双杠臂屈伸可退阶。", "力竭组只放在计划指定动作上，不要每个动作都硬力竭。"],
        },
        "orange_hypertrophy": {
            "title": "橙子增肌计划",
            "audience": "已经能稳定训练，想用阶段化计划同时提升维度和力量的人。",
            "source_basis": "来自用户提供的视频总结：三阶段力量训练计划。",
            "logic_points": ["第一阶段三周肌肥大。", "第二阶段三周增肌增力。", "第三阶段两周增力。", "卧推专项按百分比逐周推进并安排减载。"],
            "progression_rules": ["第一阶段使用70%-72.5%左右容量。", "第二阶段卧推从83%推进到88%，后续减载再冲90%-95%。", "第三阶段从87%双次推进，后续进入单次高百分比。"],
            "warnings": ["百分比训练必须基于真实可控极限，不要虚报1RM。", "第4周和第8周减载不能省。", "状态崩盘时先减载。"],
        },
    }
    return briefs[plan_type]


def _strength_workout_plan(
    *,
    level: str,
    days_per_week: int,
    minutes_per_session: int,
    strength_plan_type: str,
) -> dict[str, Any]:
    selected = _normalize_strength_plan_type(strength_plan_type, level)
    if selected == "beginner_ab_linear":
        split = {
            "split_name": "Beginner AB Linear Strength",
            "days": min(max(days_per_week, 2), 4),
            "reason": "小白先用 A/B 轮换学习深蹲、卧推、硬拉、实力推，练一休一，动作质量优先于重量。",
            "notes": ["从空杆开始。", "完成标准后线性加重。", "动作质量是上重量的前提。"],
        }
        schedule = _beginner_ab_strength_schedule(split["days"])
        strength_plan = _strength_plan_brief("beginner_ab_linear")
    elif selected == "advanced_linear_5x5":
        split = {
            "split_name": "Advanced Linear Strength",
            "days": min(max(days_per_week, 3), 5),
            "reason": "老手或重训者用 70% 1RM 起步、每周线性递增，并用轻训日和减载管理疲劳。",
            "notes": ["每周至少两次主项。", "一次正常推进，一次轻训。", "疲劳上来先砍三小项。"],
        }
        schedule = _advanced_linear_strength_schedule(split["days"])
        strength_plan = _strength_plan_brief("advanced_linear_5x5")
    else:
        split = {
            "split_name": "Universal 5x5 Strength Split",
            "days": min(max(days_per_week, 3), 6),
            "reason": "5x5 兼顾力量与肌肥大，用推、拉、蹲三分化覆盖主项与辅助训练。",
            "notes": ["储备周 RPE7-8。", "转化周 RPE8-9.5。", "每次最多加 2.5kg。"],
        }
        schedule = _universal_5x5_strength_schedule(split["days"])
        strength_plan = _strength_plan_brief("universal_5x5_split")

    return {
        "level": level,
        "goal": "strength_gain",
        "days_per_week": split["days"],
        "minutes_per_session": minutes_per_session,
        "split": split,
        "strength_plan": strength_plan,
        "weekly_schedule": schedule,
        "safety_note": "力量训练需要动作学习。明显疼痛、动作失控或恢复崩盘时，应停止硬顶并寻求合格教练帮助。",
    }


def _normalize_strength_plan_type(strength_plan_type: str, level: str) -> str:
    normalized = strength_plan_type.lower().strip().replace("-", "_").replace(" ", "_")
    aliases = {
        "auto": "",
        "beginner": "beginner_ab_linear",
        "beginner_ab": "beginner_ab_linear",
        "ab_linear": "beginner_ab_linear",
        "advanced": "advanced_linear_5x5",
        "advanced_linear": "advanced_linear_5x5",
        "linear_5x5": "advanced_linear_5x5",
        "universal": "universal_5x5_split",
        "universal_5x5": "universal_5x5_split",
        "five_by_five": "universal_5x5_split",
    }
    normalized = aliases.get(normalized, normalized)
    if not normalized:
        if level == "beginner":
            return "beginner_ab_linear"
        if level == "experienced":
            return "advanced_linear_5x5"
        return "universal_5x5_split"
    if normalized not in {"beginner_ab_linear", "advanced_linear_5x5", "universal_5x5_split"}:
        raise ValueError(f"Unsupported strength plan type: {strength_plan_type}")
    return normalized


def _strength_exercise(
    name: str,
    sets: int,
    reps: str,
    *,
    phase: str = "主项",
    rest: int = 180,
    note: str = "",
) -> dict[str, Any]:
    exercise = _exercise(name, sets_override=sets, reps_override=reps, rest_override=rest, note_override=note, phase=phase)
    if note:
        exercise["strength_note"] = note
    return exercise


def _strength_day(day: str, focus: str, exercises: list[dict[str, Any]], session_note: str, learning_points: list[str]) -> dict[str, Any]:
    return {
        "day": day,
        "focus": focus,
        "warmup": _warmup_for_focus(focus),
        "exercises": exercises,
        "rest_policy": _session_rest_policy(exercises),
        "session_note": session_note,
        "learning_points": learning_points,
    }


def _beginner_ab_strength_schedule(days: int) -> list[dict[str, Any]]:
    templates = [
        (
            "A轮：深蹲 + 卧推 + 硬拉",
            [
                _strength_exercise("Back Squat", 5, "5", note="从空杆开始；完成 5x5 后，第 5 组能做 7 次再加重。"),
                _strength_exercise("Barbell Bench Press", 5, "5", note="上肢加重标准为 2.5kg。"),
                _strength_exercise("Deadlift", 3, "5", note="硬拉 3x5；平台期不要简单套 5x8，单独降低疲劳。"),
            ],
            "A轮强调深蹲、卧推、硬拉的基础动作模式；训练后休息一天。",
        ),
        (
            "B轮：深蹲 + 实力推 + 硬拉",
            [
                _strength_exercise("Back Squat", 5, "5", note="下肢加重标准为 5kg。"),
                _strength_exercise("Barbell Overhead Press", 5, "5", note="上肢加重标准为 2.5kg。"),
                _strength_exercise("Deadlift", 3, "5", note="硬拉保持低容量高质量。"),
            ],
            "B轮用实力推补齐垂直推力量；A/B 轮换，练一休一。",
        ),
    ]
    schedule = []
    for index in range(days):
        focus, exercises, note = templates[index % 2]
        schedule.append(
            _strength_day(
                f"Day {index + 1}",
                focus,
                exercises,
                note,
                ["动作质量优先于训练重量。", "22法则：5x5完成后，第五组做7次即可加重。", "卡住1-2周后进入退行储备。"],
            )
        )
    return schedule


def _advanced_linear_strength_schedule(days: int) -> list[dict[str, Any]]:
    templates = [
        (
            "卧推正常推进",
            [
                _strength_exercise("Barbell Bench Press", 5, "5 @ 70% 1RM起步", note="每周递增 2.5%。"),
                _strength_exercise("Pendlay Row", 5, "5", phase="三小项", note="疲劳高时优先砍掉三小项。"),
                _strength_exercise("Chin-up", 3, "5-8", phase="三小项"),
            ],
        ),
        (
            "深蹲正常推进",
            [
                _strength_exercise("Back Squat", 5, "5 @ 70% 1RM起步", note="每周递增 2.5%。"),
                _strength_exercise("Barbell Overhead Press", 5, "5", phase="三小项"),
                _strength_exercise("Romanian Deadlift", 3, "8", phase="辅助"),
            ],
        ),
        (
            "卧推轻训",
            [
                _strength_exercise("Barbell Bench Press", 5, "5 @ 正常日70%", note="轻训是主动划水，不是偷懒。"),
                _strength_exercise("Seated Cable Row", 4, "8-10", phase="辅助"),
                _strength_exercise("Barbell Overhead Press", 3, "5 @ 轻重量", phase="三小项"),
            ],
        ),
        (
            "硬拉正常推进 + 深蹲轻训",
            [
                _strength_exercise("Deadlift", 3, "3-5 @ 70% 1RM起步", note="硬拉单独管理疲劳。"),
                _strength_exercise("Back Squat", 3, "5 @ 正常日70%", note="轻训帮助维持技术频率。"),
                _strength_exercise("Pendlay Row", 3, "5", phase="三小项"),
            ],
        ),
        (
            "主项补强日",
            [
                _strength_exercise("Barbell Bench Press", 3, "3 @ 当周推进重量", note="5x5失败后可降为3x3继续推进。"),
                _strength_exercise("Back Squat", 3, "3 @ 当周推进重量", note="注意保留余量，避免力竭。"),
                _strength_exercise("Pull-up", 3, "5-8", phase="三小项"),
            ],
        ),
    ]
    schedule = []
    for index in range(days):
        focus, exercises = templates[index % len(templates)]
        schedule.append(
            _strength_day(
                f"Day {index + 1}",
                focus,
                exercises,
                "老手线性增力：低开、每周递增、轻训维持频率，3-5周后按状态减载。",
                ["5x5无法完成时降为3x3，再到2x2，最后到5x1。", "热情连续下滑3天或睡眠异常，立即减载。", "疲劳积累时优先砍三小项，保三大项。"],
            )
        )
    return schedule


def _universal_5x5_strength_schedule(days: int) -> list[dict[str, Any]]:
    templates = [
        (
            "推日：卧推5x5",
            [
                _strength_exercise("Barbell Bench Press", 5, "5", note="不要用5RM做5x5，建议用8RM重量开始。"),
                _strength_exercise("Seated Overhead Press", 3, "8-10", phase="辅项"),
                _strength_exercise("Barbell Front Raise", 3, "10-12", phase="辅项"),
                _strength_exercise("Machine Fly", 3, "10-12", phase="辅项"),
                _strength_exercise("Straight-Arm Pulldown", 3, "12", phase="辅项"),
                _strength_exercise("Shoulder Stability Drill", 3, "12-15", phase="辅项"),
            ],
            ["前三周储备周 RPE7-8，第四周转化周 RPE8-9.5。", "每次最多加 2.5kg。"],
        ),
        (
            "拉日：罗马尼亚硬拉5x5",
            [
                _strength_exercise("Romanian Deadlift", 5, "5", note="新手不优先传统硬拉，用罗马尼亚硬拉建立后侧链。"),
                _strength_exercise("Seated Cable Row", 4, "8-10", phase="辅项"),
                _strength_exercise("Lat Pulldown", 4, "8-10", phase="辅项"),
                _strength_exercise("Close-Grip Seated Cable Row", 3, "10-12", phase="辅项"),
                _strength_exercise("Back Extension", 3, "12-15", phase="辅项"),
            ],
            ["5次训练同时刺激力量与维度。", "恢复不足时神经疲劳会影响力量表现。"],
        ),
        (
            "蹲日：深蹲5x5",
            [
                _strength_exercise("Back Squat", 5, "5", note="重量是检验动作质量的工具，不是目的。"),
                _strength_exercise("Walking Lunge", 3, "8-10 each side", phase="辅项"),
                _strength_exercise("Goblet Squat", 3, "10-12", phase="辅项"),
                _strength_exercise("Wall Sit", 3, "45-60 sec", phase="辅项"),
            ],
            ["新手练1-2天休1天，有经验者练3天休1天。", "拉伸、饮食、睡眠一起决定超量恢复。"],
        ),
    ]
    schedule = []
    for index in range(days):
        focus, exercises, learning_points = templates[index % 3]
        schedule.append(
            _strength_day(
                f"Day {index + 1}",
                focus,
                exercises,
                "全人群5x5：用四周小周期管理强度，兼顾力量、神经适应和肌肥大。",
                learning_points,
            )
        )
    return schedule


def _strength_plan_brief(plan_type: str) -> dict[str, Any]:
    briefs = {
        "beginner_ab_linear": {
            "title": "小白A/B轮线性力量",
            "audience": "健身小白、动作基础薄弱者、长期停滞但还没建立力量模型的人。",
            "source_basis": "来自视频总结：先学底层逻辑，再执行A/B轮换。",
            "logic_points": [
                "核心动作是深蹲、卧推、硬拉、实力推。",
                "从空杆开始，动作质量优先于训练重量。",
                "训练安排是A/B轮换，练一休一。",
            ],
            "progression_rules": [
                "深蹲/卧推5x5，硬拉3x5。",
                "22法则：完成5x5后，第五组能做7次才加重。",
                "上肢每次加2.5kg，下肢每次加5kg。",
            ],
            "stall_strategy": [
                "前期持续线性加重，不急着减载。",
                "重量卡住1-2周后，进入退行储备。",
                "下调重量做高次数，例如5x8；硬拉单独处理。",
            ],
            "warnings": ["建议找合格教练学习基础动作模式。", "错误动作会导致伤病和停滞。"],
        },
        "advanced_linear_5x5": {
            "title": "老手线性5x5增力",
            "audience": "长期训练者、力量停滞者、重训者。",
            "source_basis": "来自视频总结：储备期后用线性计划把肌肉和容量转化为力量。",
            "logic_points": [
                "核心项目是三大项：深蹲、硬拉、卧推；三小项：实力推、潘德伦划船、引体向上。",
                "增力计划的核心是每周必须增加重量。",
                "用1RM计算起始重量，从70%极限重量低开。",
            ],
            "progression_rules": [
                "除硬拉外，主项采用5x5。",
                "每周递增2.5%。",
                "每周至少训练两次主项：一次正常推进，一次轻训；轻训为主项重量的7折。",
            ],
            "stall_strategy": [
                "3-5周后根据状态减载，重量降到80%或容量砍半。",
                "5x5无法完成时降到3x3，继续线性推进。",
                "再困难可降为2x2直至5x1；最后一组感受余量，避免力竭。",
            ],
            "warnings": ["训练热情连续下滑3天以上或睡眠异常，立即减载。", "疲劳积累时优先砍三小项，保证三大项推进。"],
        },
        "universal_5x5_split": {
            "title": "全人群5x5三分化",
            "audience": "想用5x5提高力量和维度的新手、熟练者、重启训练者。",
            "source_basis": "来自视频总结：5x5兼顾力量与肌肥大，适合作为储备到转化的核心结构。",
            "logic_points": [
                "4x4神经疲劳大且容量不足，6x6训练量偏大，5x5居中。",
                "力量提升来自协调性适应、神经适应、肌肉横截面积增加。",
                "不要用5RM做5x5，推荐用8RM重量开始。",
            ],
            "progression_rules": [
                "四周周期：前三周储备周，第四周转化周。",
                "储备周RPE7-8，转化周RPE8-9.5。",
                "根据RPE变化调整重量，每次最多增加2.5kg。",
            ],
            "stall_strategy": [
                "辅助训练用于补短板，不要抢主项恢复。",
                "神经疲劳明显时优先恢复睡眠、饮食和放松。",
            ],
            "warnings": ["新手不推荐传统硬拉，优先罗马尼亚硬拉。", "盲目追重量会破坏动作质量。"],
        },
    }
    return briefs[plan_type]


def _plan_templates(level: str, goal: str, split_name: str) -> list[dict[str, Any]]:
    if goal == "health":
        return [
            {"focus": "Home Upper Body", "exercises": ["Push-up", "Incline Push-up", "Bench Dips", "Arm-Reach Crunch"]},
            {"focus": "Home Lower Body", "exercises": ["Single-Leg Hamstring Activation", "Bulgarian Split Squat", "Elevated Calf Raise", "Arm-Reach Crunch"]},
        ]

    if "Upper Lower" in split_name:
        return [
            {"focus": "Upper A", "exercises": ["Barbell Bench Press", "Seated Cable Row", "Dumbbell Shoulder Press", "Lat Pulldown", "Cable Triceps Pressdown"]},
            {"focus": "Lower A", "exercises": ["Back Squat", "Romanian Deadlift", "Leg Press", "Walking Lunge", "Plank"]},
            {"focus": "Upper B", "exercises": ["Incline Dumbbell Press", "Pull-up", "Machine Chest Press", "Lateral Raise", "Dumbbell Curl"]},
            {"focus": "Lower B", "exercises": ["Deadlift", "Goblet Squat", "Leg Press", "Romanian Deadlift", "Plank"]},
        ]

    return [
        {"focus": "Push", "exercises": ["Barbell Bench Press", "Incline Dumbbell Press", "Dumbbell Shoulder Press", "Lateral Raise", "Cable Triceps Pressdown"]},
        {"focus": "Pull", "exercises": ["Pull-up", "Seated Cable Row", "Lat Pulldown", "Romanian Deadlift", "Dumbbell Curl"]},
        {"focus": "Legs", "exercises": ["Back Squat", "Leg Press", "Romanian Deadlift", "Walking Lunge", "Plank"]},
    ]


def _health_home_schedule(days_per_week: int, minutes_per_session: int) -> list[dict[str, Any]]:
    session_specs = [
        {
            "focus": "Home Upper Body",
            "session_note": "居家上肢：胸、肩、手臂、背部和核心。没有哑铃时可用水瓶或安全重物。",
            "video": HEALTH_HOME_SESSION_VIDEOS["Home Upper Body"],
            "warmup": ["Rocking Plank", "Wrist preparation", "Light shoulder circles"],
            "learning_points": [
                "俯卧撑按能力选择标准、前撑或垫高变式。",
                "肩部动作优先用轻重量，做到后束、中束、前束都有感觉。",
                "每个动作以接近力竭为主，但关节疼痛时立刻降阶。",
            ],
            "exercises": [
                ("胸部", "Push-up", 4, "near failure", 120),
                ("上胸", "Incline Push-up", 4, "near failure", 120),
                ("肩后束", "Rear Delt Bottle Raise", 4, "near failure", 120),
                ("肩中束", "Bottle Lateral Raise", 4, "near failure", 120),
                ("肩前束", "Bottle Front Raise", 4, "near failure", 120),
                ("肱三头", "Bench Dips", 4, "about 24", 120),
                ("核心/背部", "Kneeling Ab Wheel", 4, "near failure", 120),
                ("背部", "Bent-Over Dumbbell Row", 4, "until back has a clear pump", 120),
                ("腹部", "Arm-Reach Crunch", 4, "near failure", 120),
            ],
        },
        {
            "focus": "Home Lower Body",
            "session_note": "居家下肢与腹肌：后侧链、臀腿、髋关节、小腿和核心。没有器械时用水瓶或背包装重物。",
            "video": HEALTH_HOME_SESSION_VIDEOS["Home Lower Body"],
            "warmup": ["Hip hinge rehearsal", "Ankle rocks", "Bodyweight squats"],
            "learning_points": [
                "先激活大腿后侧和髋关节，再做保加利亚蹲。",
                "小腿训练用慢下快起，前脚掌踩实。",
                "腹肌动作以能控制腰部为前提，不追求大幅度。",
            ],
            "exercises": [
                ("后侧激活", "Single-Leg Hamstring Activation", 4, "10 each side", 120),
                ("臀髋", "Chair Hip Hinge", 4, "15-16 each side", 120),
                ("腿部", "Bulgarian Split Squat", 4, "10 each side", 120),
                ("髋/腹股沟", "Groin Mobility Split Squat", 3, "10-12 each side", 120),
                ("小腿", "Elevated Calf Raise", 4, "20", 120),
                ("核心/背部", "Kneeling Ab Wheel", 4, "near failure", 120),
                ("腹部", "Arm-Reach Crunch", 4, "near failure", 120),
            ],
        },
    ]

    schedule: list[dict[str, Any]] = []
    for index in range(days_per_week):
        spec = session_specs[index % len(session_specs)]
        exercises = [
            _exercise(
                exercise_name,
                sets_override=sets,
                reps_override=reps,
                rest_override=rest,
                phase=phase,
                teaching_video=spec["video"],
            )
            for phase, exercise_name, sets, reps, rest in spec["exercises"]
        ]
        schedule.append(
            {
                "day": f"Day {index + 1}",
                "focus": spec["focus"],
                "warmup": spec["warmup"],
                "session_video_url": spec["video"]["url"],
                "warmup_video_url": spec["video"]["url"],
                "exercises": exercises,
                "rest_policy": _session_rest_policy(exercises),
                "session_note": spec["session_note"],
                "learning_points": spec["learning_points"],
                "minutes_target": minutes_per_session,
            }
        )
    return schedule


def _beginner_four_day_schedule(minutes_per_session: int) -> list[dict[str, Any]]:
    session_specs = [
        {
            "day": "Day 1",
            "focus": "Beginner Chest Shoulders Triceps",
            "session_note": "Beginner four-day split: chest, shoulders, and triceps. Learn the video sequence before adding load.",
            "warmup": [
                "5 min upper-body cardio",
                "Band chest openers",
                "Scapular push-ups",
                "Cable fly warm-up set",
                "Bench press ramp-up sets",
            ],
            "exercises": [
                ("main", "Cable Fly", 4, "12", 60),
                ("main", "Barbell Bench Press", 6, "10", 120),
                ("main", "Incline Machine Chest Press", 4, "12", 90),
                ("accessory", "Barbell Overhead Press", 4, "12", 120),
                ("accessory", "Overhead Cable Triceps Extension", 4, "12", 60),
            ],
        },
        {
            "day": "Day 2",
            "focus": "Beginner Back Biceps",
            "session_note": "Beginner four-day split: back and biceps. Start by feeling the lats before heavy pulling.",
            "warmup": [
                "5 min easy rower",
                "Shoulder blade depression drills",
                "Straight-arm pulldown warm-up",
                "Light cable row ramp-up sets",
            ],
            "exercises": [
                ("main", "Straight-Arm Pulldown", 4, "12-15", 60),
                ("main", "Single-Arm Seated Cable Row", 4, "12", 75),
                ("main", "Pull-up", 4, "10", 120),
                ("main", "Close-Grip Seated Cable Row", 4, "12", 75),
                ("main", "Lat Pulldown", 4, "12", 75),
                ("main", "Barbell Curl", 4, "12", 60),
            ],
        },
        {
            "day": "Day 3",
            "focus": "Beginner Lower Body",
            "session_note": "Beginner four-day split: lower body. Keep balance and joint control ahead of load.",
            "warmup": [
                "5 min incline walk or bike",
                "Hip circles",
                "Adductor rockbacks",
                "Bodyweight lunges",
                "Calf ankle rocks",
            ],
            "exercises": [
                ("main", "Hip Adduction Machine / Copenhagen Plank", 4, "15 or 20-30 sec", 60),
                ("main", "Single-Leg Dumbbell Romanian Deadlift", 3, "12 each side", 90),
                ("main", "Walking Lunge", 4, "12 each side", 90),
                ("main", "Rotational Lunge", 3, "10 each side", 75),
                ("main", "Standing Calf Raise", 3, "15", 60),
            ],
        },
        {
            "day": "Rest Day",
            "focus": "Beginner Recovery Day",
            "is_rest_day": True,
            "rest_note": "Rest one day after the lower-body session. Keep steps easy, sleep enough, and do light mobility only if it feels good.",
            "session_note": "Recovery day: no hard training.",
            "warmup": [],
            "exercises": [],
        },
        {
            "day": "Day 4",
            "focus": "Beginner Shoulders Arms",
            "session_note": "Beginner four-day split: shoulders and arms. Keep shoulder positions stable and avoid swinging.",
            "warmup": [
                "5 min upper-body cardio",
                "Band external rotations",
                "Face pull warm-up set",
                "Light overhead press ramp-up sets",
            ],
            "exercises": [
                ("main", "Seated Reverse Fly", 4, "12", 60),
                ("main", "Barbell Overhead Press", 5, "10", 120),
                ("main", "Cable Face Pull", 4, "10", 60),
                ("main", "Front Raise", 4, "10", 60),
                ("main", "Overhead Cable Triceps Extension", 4, "12", 60),
                ("main", "Cable Curl", 4, "12", 60),
            ],
        },
    ]

    schedule: list[dict[str, Any]] = []
    for spec in session_specs:
        if spec.get("is_rest_day"):
            schedule.append(dict(spec))
            continue

        focus = str(spec["focus"])
        session_video = BEGINNER_SESSION_VIDEOS[focus]
        warmup_video = WARMUP_TEACHING_VIDEOS[focus]
        exercises = [
            _exercise(
                exercise_name,
                sets_override=sets,
                reps_override=reps,
                rest_override=rest,
                phase="主项" if phase == "main" else "辅项",
                teaching_video=session_video,
            )
            for phase, exercise_name, sets, reps, rest in spec["exercises"]
        ]
        schedule.append(
            {
                "day": spec["day"],
                "focus": focus,
                "warmup": spec["warmup"],
                "warmup_video_url": warmup_video["url"],
                "session_video_url": session_video["url"],
                "exercises": exercises,
                "rest_policy": _session_rest_policy(exercises),
                "session_note": spec["session_note"],
                "minutes_target": minutes_per_session,
            }
        )
    return schedule


def _warmup_for_focus(focus: str) -> list[str]:
    lower_focus = focus.lower()
    base = ["3-5 min easy cardio", "Dynamic joint circles", "Two light ramp-up sets"]
    if "upper" in lower_focus or "push" in lower_focus or "pull" in lower_focus:
        return base + ["Band pull-aparts", "Scapular push-ups"]
    if "lower" in lower_focus or "legs" in lower_focus:
        return base + ["Glute bridges", "Bodyweight squats"]
    return base + ["Bodyweight squats", "Band pull-aparts"]


def _session_rest_policy(exercises: list[dict[str, Any]]) -> str:
    longest_rest = max((int(exercise.get("rest_seconds", MIN_REST_SECONDS)) for exercise in exercises), default=MIN_REST_SECONDS)
    if longest_rest >= LONG_REST_SECONDS:
        return "本日休息规则：所有动作组间至少 2 分钟；大重量复合动作按 3 分钟以上，先保证下一组动作质量。"
    return "本日休息规则：所有动作组间至少 2 分钟，先保证动作质量和目标肌肉感受。"


def _session_note(level: str, goal: str, minutes_per_session: int) -> str:
    if minutes_per_session < 45:
        return "Short session: prioritize the first three exercises and keep execution focused."
    if level == "beginner":
        return "Technique first. Stop sets with 1-3 reps in reserve."
    if goal == "strength_gain":
        return "Put compound lifts first and keep reps powerful."
    return "Use steady progression and adjust if fatigue or pain rises."


def _teaching_video(name: str) -> dict[str, str]:
    return DIRECT_TEACHING_VIDEOS.get(
        name,
        {
            "title": "凯圣王新手增肌系列",
            "creator": "凯圣王",
            "platform": "Bilibili",
            "url": "https://www.bilibili.com/video/BV1Qd4y1Z75J/",
        },
    )


def _default_substitutions(name: str) -> list[str]:
    substitutions = {
        "Barbell Bench Press": ["Dumbbell Bench Press", "Machine Chest Press"],
        "Back Squat": ["Goblet Squat", "Leg Press"],
        "Deadlift": ["Romanian Deadlift", "Hip Thrust"],
        "Dumbbell Shoulder Press": ["Machine Shoulder Press", "Landmine Press"],
        "Pull-up": ["Lat Pulldown", "Assisted Pull-up"],
    }
    return substitutions.get(name, [])
