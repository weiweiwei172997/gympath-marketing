"""Chinese display copy for GymPath's extracted deterministic plans.

The rule engine remains the source of exercises, sets, repetitions and links.
These exact translations cover its automatic plans; unrecognised text is left
unchanged rather than guessed. Machine identifiers and video metadata are not
translated. This module has no I/O and never mutates the supplied plan.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


SPLIT_NAMES = {
    "Advanced Linear Strength": "进阶线性力量训练",
    "Beginner AB Linear Strength": "新手 A/B 线性力量训练",
    "Beginner Four-Day Split": "新手四分化训练",
    "Home Upper Lower Health": "居家上肢与下肢健康训练",
    "Push Pull Legs": "推、拉、腿三分化训练",
    "Push Pull Legs Restart": "恢复训练：推、拉、腿三分化",
    "Tan Chengyi Beginner Follow Along": "谭成义新手跟练",
    "Tan Chengyi Kaisheng Three-Day Split": "谭成义与凯圣王三分化训练",
    "Universal 5x5 Strength Split": "通用 5×5 力量分化训练",
    "Upper Lower": "上肢与下肢分化训练",
    "Upper Lower Restart": "恢复训练：上肢与下肢分化",
    "Orange Three-Phase Hypertrophy": "橙子三阶段增肌训练",
}

FOCUS_NAMES = {
    "Beginner Back Biceps": "新手：背部与肱二头肌",
    "Beginner Chest Shoulders Triceps": "新手：胸部、肩部与肱三头肌",
    "Beginner Lower Body": "新手：下肢",
    "Beginner Recovery Day": "新手恢复日",
    "Beginner Shoulders Arms": "新手：肩部与手臂",
    "Home Lower Body": "居家下肢与核心",
    "Home Upper Body": "居家上肢",
    "Legs": "腿部",
    "Lower A": "下肢 A",
    "Lower B": "下肢 B",
    "Pull": "拉力训练",
    "Push": "推力训练",
    "Upper A": "上肢 A",
    "Upper B": "上肢 B",
    "Rest Day": "恢复日",
}

EXERCISE_NAMES = {
    "Arm-Reach Crunch": "伸臂卷腹",
    "Assisted Pull-up": "辅助引体向上",
    "Back Extension": "背伸（山羊挺身）",
    "Back Squat": "杠铃后蹲",
    "Barbell Bench Press": "杠铃卧推",
    "Barbell Curl": "杠铃弯举",
    "Barbell Front Raise": "杠铃前平举",
    "Barbell Overhead Press": "杠铃推举",
    "Bench Dips": "凳上臂屈伸",
    "Bent-Over Dumbbell Row": "俯身哑铃划船",
    "Bent-Over Dumbbell Reverse Fly": "俯身哑铃反向飞鸟",
    "Bodyweight Squat": "徒手深蹲",
    "Bottle Front Raise": "水瓶前平举",
    "Bottle Lateral Raise": "水瓶侧平举",
    "Bulgarian Split Squat": "保加利亚分腿蹲",
    "Cable Curl": "绳索弯举",
    "Cable Crunch": "绳索卷腹",
    "Cable Face Pull": "绳索面拉",
    "Cable Fly": "绳索飞鸟",
    "Cable Triceps Pressdown": "绳索肱三头肌下压",
    "Chair Hip Hinge": "椅子辅助髋铰链",
    "Chin-up": "反握引体向上",
    "Close-Grip Seated Cable Row": "窄握坐姿绳索划船",
    "Deadlift": "硬拉",
    "Deficit Deadlift": "垫高站位硬拉",
    "Dips": "双杠臂屈伸",
    "Dumbbell Bench Press": "哑铃卧推",
    "Dumbbell Curl": "哑铃弯举",
    "Dumbbell Shoulder Press": "哑铃推肩",
    "Elevated Calf Raise": "垫高提踵",
    "Front Raise": "前平举",
    "Front Squat": "杠铃前蹲",
    "Goblet Squat": "高脚杯深蹲",
    "Groin Mobility Split Squat": "腹股沟活动分腿蹲",
    "Hip Adduction Machine / Copenhagen Plank": "髋内收器械 / 哥本哈根平板支撑",
    "Hip Thrust": "臀推",
    "Hammer Dumbbell Curl": "哑铃锤式弯举",
    "Incline Barbell Bench Press": "上斜杠铃卧推",
    "Incline Barbell Triceps Extension": "上斜杠铃肱三头肌臂屈伸",
    "Incline Bench Lateral Raise": "上斜凳侧平举",
    "Incline Dumbbell Press": "上斜哑铃卧推",
    "Incline Machine Chest Press": "上斜器械推胸",
    "Incline Push-up": "上斜俯卧撑",
    "Kneeling Ab Wheel": "跪姿健腹轮",
    "Kneeling Cable Crunch": "跪姿绳索卷腹",
    "Landmine Press": "地雷杆推举",
    "Lat Pulldown": "高位下拉",
    "Lateral Raise": "侧平举",
    "Leg Press": "腿举",
    "Lying Triceps Extension": "仰卧肱三头肌臂屈伸",
    "Machine Chest Press": "器械推胸",
    "Machine Fly": "器械飞鸟",
    "Machine Shoulder Press": "器械推肩",
    "Neutral-Grip Pulldown": "对握高位下拉",
    "Open-Elbow Seated Row": "展肘坐姿划船",
    "Overhead Cable Triceps Extension": "绳索过头肱三头肌臂屈伸",
    "Pendlay Row": "潘德雷划船",
    "Plate Crunch": "杠铃片负重卷腹",
    "Plank": "平板支撑",
    "Pull-up": "正握引体向上",
    "Push-up": "俯卧撑",
    "Rear Delt Bottle Raise": "水瓶三角肌后束平举",
    "Reverse Pec Deck": "反向蝴蝶机飞鸟",
    "Reverse-Grip Lat Pulldown": "反握高位下拉",
    "Reverse-Grip Machine Row": "反握器械划船",
    "Romanian Deadlift": "罗马尼亚硬拉",
    "Rotational Lunge": "转体弓步蹲",
    "Seated Cable Row": "坐姿绳索划船",
    "Seated Overhead Press": "坐姿推举",
    "Seated Reverse Fly": "坐姿反向飞鸟",
    "Seated Lateral Raise": "坐姿侧平举",
    "Seal Row": "海豹划船（俯卧凳上划船）",
    "Shoulder Stability Drill": "肩部稳定训练",
    "Side Cable Crunch": "侧向绳索卷腹",
    "Single-Arm Cable Pulldown": "单臂绳索下拉",
    "Single-Arm Machine Row": "单臂器械划船",
    "Single-Arm Seated Cable Row": "单臂坐姿绳索划船",
    "Single-Leg Dumbbell Romanian Deadlift": "单腿哑铃罗马尼亚硬拉",
    "Single-Leg Hamstring Activation": "单腿腘绳肌激活",
    "Standing Calf Raise": "站姿提踵",
    "Straight-Arm Pulldown": "直臂下拉",
    "Straight-Leg Barbell Bench Press": "直腿杠铃卧推",
    "T-Bar Row": "T 杆划船",
    "Walking Lunge": "行走箭步蹲",
    "Wall Sit": "靠墙静蹲",
    "Y-Raise Lateral Raise": "Y 字侧平举",
}

TARGET_MUSCLES = {
    "Abs": "腹肌",
    "Adductors": "内收肌",
    "Arms": "手臂",
    "Back": "背部",
    "Biceps": "肱二头肌",
    "Biceps / Brachialis": "肱二头肌 / 肱肌",
    "Calves": "小腿",
    "Chest": "胸部",
    "Chest / Triceps": "胸部 / 肱三头肌",
    "Core": "核心",
    "Core / Back": "核心 / 背部",
    "Front Delts": "三角肌前束",
    "Glutes / Hips": "臀部 / 髋部",
    "Glutes / Quads": "臀部 / 股四头肌",
    "Hamstrings": "腘绳肌（大腿后侧）",
    "Hips / Adductors": "髋部 / 内收肌",
    "Lats": "背阔肌",
    "Legs": "腿部",
    "Posterior Chain": "身体后侧肌群",
    "Quads": "股四头肌",
    "Rear Delts": "三角肌后束",
    "Shoulders": "肩部",
    "Side Delts": "三角肌中束",
    "Triceps": "肱三头肌",
    "Upper Back": "上背部",
    "Upper Chest": "上胸部",
}

WARMUP_TEXT = {
    "3-5 min easy cardio": "3–5 分钟轻松有氧",
    "5 min easy rower": "5 分钟轻松划船机",
    "5 min incline walk or bike": "5 分钟坡度步行或骑车",
    "5 min upper-body cardio": "5 分钟上肢有氧",
    "Adductor rockbacks": "内收肌后坐活动",
    "Ankle rocks": "踝关节前后活动",
    "Band chest openers": "弹力带胸部打开",
    "Band external rotations": "弹力带肩外旋",
    "Band pull-aparts": "弹力带拉开",
    "Bench press ramp-up sets": "卧推递增热身组",
    "Bodyweight lunges": "徒手弓步蹲",
    "Bodyweight squat ramp-up": "徒手深蹲递增热身",
    "Bodyweight squats": "徒手深蹲",
    "Cable fly warm-up set": "绳索飞鸟热身组",
    "Calf ankle rocks": "小腿与踝关节前后活动",
    "Dynamic joint circles": "动态关节绕环",
    "Face pull warm-up set": "面拉热身组",
    "Glute bridges": "臀桥",
    "Hip circles": "髋关节绕环",
    "Hip hinge rehearsal": "髋铰链动作练习",
    "Light cable row ramp-up sets": "轻重量绳索划船递增热身组",
    "Light overhead press ramp-up sets": "轻重量推举递增热身组",
    "Light shoulder circles": "轻松肩部绕环",
    "Rocking Plank": "前后摇动平板支撑",
    "Scapular push-ups": "肩胛俯卧撑",
    "Shoulder blade depression drills": "肩胛下沉练习",
    "Straight-arm pulldown warm-up": "直臂下拉热身",
    "Two light ramp-up sets": "两组轻重量递增热身",
    "Wrist preparation": "腕关节热身",
}

INSTRUCTION_TEXT = {
    "Avoid hip swing and keep wrists stacked.": "避免髋部摆动，保持手腕对齐。",
    "Avoid swinging and squeeze at the top.": "不要晃动身体借力，弯举到顶部时收紧上臂。",
    "Brace before each rep and keep balance mid-foot.": "每次下蹲前绷紧腹部，重心保持在脚掌中部。",
    "Brace hard and keep the bar path close.": "收紧核心，让杠铃运行轨迹靠近身体。",
    "Choose a load you can control.": "选择能控制的重量。",
    "Curl through the abs.": "由腹肌带动卷起。",
    "Choose the machine or Copenhagen plank based on control and comfort.": "根据控制能力与舒适度，选择器械或哥本哈根平板支撑。",
    "Drive elbows back and pause briefly.": "将手肘向后拉，拉到身侧后稍作停顿。",
    "Elevate the feet or use a bed/chair setup based on control.": "根据控制能力垫高双脚，或利用床、椅子辅助。",
    "Elevate the forefoot and use slow lowering with a quick rise.": "前脚掌站在稳固的垫高处，脚跟缓慢下降，再较快抬起。",
    "Hinge at hips and keep the back neutral.": "向后推髋，上身前倾，背部保持自然平直。",
    "Hinge on one leg and keep hips square.": "单腿做髋铰链动作，保持髋部平正。",
    "Hold a stable knee angle.": "保持膝关节角度稳定。",
    "Hold the plate under control.": "控制握持杠铃片。",
    "Keep a straight line and control the bottom.": "身体保持一条直线，缓慢下放，不要塌腰。",
    "Keep arms nearly straight and drive the bar toward the thighs.": "双臂接近伸直，将横杆向大腿方向拉动。",
    "Keep elbows pinned and control the return.": "手肘保持在身体两侧，下压后缓慢回到起点。",
    "Keep elbows pointed forward and stretch the long head under control.": "手肘朝前，在控制范围内拉伸肱三头肌长头。",
    "Keep elbows still and control the return.": "保持手肘不动，控制回程。",
    "Keep ribs down and glutes lightly squeezed.": "不要挺起胸口或塌腰，腹部和臀部轻轻绷紧。",
    "Keep reps controlled.": "控制每次动作。",
    "Keep shoulder blades stable.": "肩胛贴稳靠垫，推起时不要耸肩。",
    "Keep shoulders down and squeeze the chest without shrugging.": "保持肩部下沉，收紧胸部，避免耸肩。",
    "Keep shoulders packed and press along the machine path.": "保持肩部稳定，沿器械轨迹推起。",
    "Keep the bar close and brace hard.": "让杠铃靠近身体，并收紧核心。",
    "Keep the load conservative.": "使用保守的重量。",
    "Keep the load strict.": "保持负重动作规范。",
    "Keep the handle close to the body.": "保持把手靠近身体。",
    "Keep torso quiet and pull the elbow toward the hip.": "保持躯干稳定，将手肘拉向髋部。",
    "Keep torso tall and knees tracking over toes.": "胸口朝前，膝盖沿脚尖方向弯曲。",
    "Lead with elbows and avoid heavy swinging.": "手肘带动双臂向两侧抬起，不要晃动身体借力。",
    "Move smoothly and keep feet planted.": "平稳下蹲和站起，全程脚掌贴地。",
    "Open from the rear delts and avoid shrugging.": "用三角肌后束带动打开，避免耸肩。",
    "Open the elbows to bias upper back.": "手肘向外打开，侧重上背部。",
    "Pause at the top and control the stretch at the bottom.": "顶端停顿，控制底部拉伸。",
    "Press from a stable seated position.": "保持稳定坐姿再推起。",
    "Press smoothly without leaning back.": "平稳向上推起哑铃，上身不要后仰。",
    "Pull elbows down and avoid shrugging.": "将手肘向下拉，肩膀不要耸起。",
    "Pull through the elbows and pause without leaning back.": "以手肘带动拉动并停顿，避免后仰。",
    "Pull toward the face with elbows high and external rotation.": "手肘抬高，配合外旋向面部拉动。",
    "Raise through the elbows with a light household load.": "用轻水瓶或哑铃，手肘带动双臂向两侧抬起。",
    "Raise under control without leaning back.": "控制抬起，避免后仰。",
    "Raise under control.": "控制抬起动作。",
    "Reach arms upward and keep the movement small enough to protect the low back.": "双臂向上伸，只轻轻卷起上背，不用腰部猛拉。",
    "Reset each rep from the floor.": "每次动作都从地面重新开始。",
    "Rotate with control and keep the front knee tracking well.": "控制转体，保持前侧膝盖轨迹稳定。",
    "Set shoulder blades and use a consistent touch point.": "肩胛贴稳卧推凳，每次让杠铃落在胸部同一位置。",
    "Step long enough to stay balanced.": "步幅足够长，保持平衡。",
    "Train each side evenly.": "两侧均衡训练。",
    "Use a chair or bench and adjust foot position for difficulty.": "利用椅子或长凳，通过调整脚的位置改变难度。",
    "Use a chair or wall for support and keep tension in the hip.": "用椅子或墙面扶稳，向后推髋，上身缓慢前倾。",
    "Use a comfortable angle and controlled reps.": "选择舒服的凳面角度，平稳推起和下放哑铃。",
    "Use a chest-supported setup.": "采用胸部支撑姿势。",
    "Use a controllable stretch.": "将拉伸保持在能控制的范围。",
    "Use a controlled depth without hip rounding.": "下放到能控制的深度，臀部和下背不要离开靠垫。",
    "Use a controlled full range.": "在控制下完成全幅度动作。",
    "Use a controlled grip.": "保持握法可控。",
    "Use a controlled machine path.": "沿器械轨迹受控完成动作。",
    "Use a controlled range.": "将动作保持在能控制的范围。",
    "Use a kneeling setup and keep range controllable.": "采用跪姿，将动作幅度保持在能控制的范围。",
    "Use a light object and focus on the back-side stretch.": "使用轻物品，注意身体后侧的拉伸。",
    "Use a light load.": "使用轻重量。",
    "Use a neutral grip if the shoulder feels stressed.": "肩部感觉有压力时采用对握。",
    "Use a small range at first and build hip comfort.": "开始时采用小幅度，逐步适应髋部活动。",
    "Use a stable machine path.": "沿稳定的器械轨迹完成动作。",
    "Use a stable kneeling setup.": "保持稳定跪姿。",
    "Use a stable shoulder position and controlled range.": "肩膀贴稳卧推凳，只在能平稳控制的幅度内推起和下放。",
    "Use assistance if needed.": "需要时使用辅助。",
    "Use bottles or light dumbbells and stop when the rear delts lose control.": "使用水瓶或轻哑铃，三角肌后束无法控制时停止。",
    "Use dumbbells, bottles, or another safe household load.": "可用轻哑铃或握得稳的水瓶，向后拉起，再缓慢放下。",
    "Use full control and avoid swinging.": "全程控制，避免摆动。",
    "Use light controlled reps.": "以轻重量完成受控动作。",
    "Use light dumbbells.": "使用轻哑铃。",
    "Use one side at a time.": "每次训练一侧。",
    "Use neutral grip.": "使用对握。",
    "Use steady bar speed.": "保持杠铃速度平稳。",
    "Use the bench to limit cheating.": "利用长凳限制借力。",
    "Use the programmed percentage.": "采用计划指定的重量百分比。",
    "Use the requested percent-based load.": "采用指定百分比对应的负重。",
    "Use support if balance limits output.": "平衡影响动作表现时使用支撑。",
    "Beginners use a guided four-day split with fixed videos to reduce decision cost and follow a clear progression.": "新手使用带固定视频的四分化训练，减少选择成本，并按清晰的顺序推进。",
    "Experienced lifters can benefit from higher frequency and more specialization.": "有经验的训练者可采用更高频率与更细的训练分工。",
    "Fewer weekly sessions can still rotate push, pull, and legs without a mixed whole-session template.": "每周训练次数较少时，仍可依次轮换推、拉、腿训练，不需要采用混合全身模板。",
    "Health-focused users get a low-barrier home plan split into upper body and lower body/core sessions.": "以健康为目标的用户使用入门门槛较低的居家计划，分为上肢和下肢与核心训练。",
    "Restarting users need enough stimulus without making the first week feel punishing.": "恢复训练的用户需要足够的刺激，同时避免第一周过于吃力。",
    "Upper/lower training balances frequency, recovery, and progression.": "上肢与下肢分化兼顾训练频率、恢复和进阶。",
    "Alternate upper-body and lower-body sessions.": "交替进行上肢与下肢训练。",
    "Follow the four sessions in order.": "按顺序完成四次训练。",
    "Increase only after consistency returns.": "恢复规律训练后再增加训练量。",
    "Keep accessory work focused.": "辅助训练保持重点集中。",
    "Keep loads conservative while learning movement patterns.": "学习动作模式时使用保守的重量。",
    "Keep one or two reps in reserve on most sets.": "大多数组保留一至两次余力。",
    "Rest one day after the lower-body session before the shoulder and arms session.": "下肢训练后休息一天，再进行肩部与手臂训练。",
    "Rotate the next split day each session.": "每次训练推进到下一个分化训练日。",
    "Start with fewer sets.": "从较少的组数开始。",
    "Stop if joint pain feels sharp or worsening.": "关节出现尖锐或加重的疼痛时停止。",
    "Track recovery.": "记录恢复情况。",
    "Use bottles, a chair, or bodyweight when gym equipment is unavailable.": "没有健身器械时使用水瓶、椅子或自重。",
    "Use progressive overload.": "采用渐进超负荷。",
    "Use substitutions when a movement does not feel right.": "某个动作感觉不合适时使用替代动作。",
    "Beginner four-day split: back and biceps. Start by feeling the lats before heavy pulling.": "新手四分化：背部与肱二头肌。进行较大重量拉力训练前，先体会背阔肌发力。",
    "Beginner four-day split: chest, shoulders, and triceps. Learn the video sequence before adding load.": "新手四分化：胸部、肩部与肱三头肌。先学习视频中的动作顺序，再增加负重。",
    "Beginner four-day split: lower body. Keep balance and joint control ahead of load.": "新手四分化：下肢。先保持平衡与关节控制，再考虑负重。",
    "Beginner four-day split: shoulders and arms. Keep shoulder positions stable and avoid swinging.": "新手四分化：肩部与手臂。保持肩部位置稳定，避免摆动。",
    "Recovery day: no hard training.": "恢复日：不进行高强度训练。",
    "Short session: prioritize the first three exercises and keep execution focused.": "较短的训练：优先完成前三个动作，集中完成训练。",
    "Use steady progression and adjust if fatigue or pain rises.": "稳步进阶，疲劳或疼痛增加时调整。",
    "Rest one day after the lower-body session. Keep steps easy, sleep enough, and do light mobility only if it feels good.": "下肢训练后休息一天。轻松步行、保证睡眠，仅在感觉舒适时做轻度活动。",
    "GymPath gives fitness education, not medical diagnosis. Stop for sharp or worsening pain.": "GymPath 提供健身教育，不提供医疗诊断。出现尖锐或加重的疼痛时停止。",
}

REP_TEXT = {
    "10 + 10 to failure": "10 次 + 10 次至力竭",
    "12 + 10 to failure + 5": "12 次 + 10 次至力竭 + 5 次",
    "12 or near failure": "12 次或接近力竭",
    "15 or 20-30 sec": "15 次或 20–30 秒",
    "about 24": "约 24 次",
    "near failure": "接近力竭",
    "until back has a clear pump": "至背部有明显泵感",
}

# Only display fields participate. Enum keys such as level, goal, plan_type,
# teaching URLs and metadata describing a source keep their original values.
DISPLAY_FIELDS = frozenset({
    "split_name", "reason", "notes", "day", "focus", "warmup", "name",
    "reps", "target_muscle", "substitutions", "session_note", "rest_note",
    "rest_policy", "safety_note", "learning_points", "strength_note",
})

TEXT_ZH = {
    **SPLIT_NAMES,
    **FOCUS_NAMES,
    **EXERCISE_NAMES,
    **TARGET_MUSCLES,
    **WARMUP_TEXT,
    **INSTRUCTION_TEXT,
    **REP_TEXT,
}


def translate_text(value: str) -> str:
    """Translate a known display string; retain unknown source text exactly."""
    if value in TEXT_ZH:
        return TEXT_ZH[value]
    match = re.fullmatch(r"Day ([1-9][0-9]*)", value)
    if match:
        return f"训练日 {match[1]}"
    match = re.fullmatch(r"([0-9]+(?:-[0-9]+)?) each side", value)
    if match:
        return f"每侧 {match[1]} 次"
    match = re.fullmatch(r"([0-9]+(?:-[0-9]+)?) sec", value)
    if match:
        return f"{match[1]} 秒"
    return value


def localize_plan(
    plan: dict[str, Any], *, preserve_original: bool = False
) -> dict[str, Any]:
    """Return a Chinese display copy while retaining the engine's data values.

    Optional ``<field>_original`` entries preserve changed scalar display text
    beside the translation, e.g. ``name_original``. They are absent by default.
    Lists are translated without changing their order or adding extra entries.
    """
    result = deepcopy(plan)

    def translate_fields(item: Any) -> None:
        if isinstance(item, list):
            for child in item:
                translate_fields(child)
        elif isinstance(item, dict):
            for field, value in list(item.items()):
                if field in DISPLAY_FIELDS and isinstance(value, str):
                    translated = translate_text(value)
                    item[field] = translated
                    if preserve_original and translated != value:
                        item.setdefault(f"{field}_original", value)
                elif field in DISPLAY_FIELDS and isinstance(value, list):
                    item[field] = [
                        translate_text(child) if isinstance(child, str) else child
                        for child in value
                    ]
                    translate_fields(item[field])
                else:
                    translate_fields(value)

    translate_fields(result)
    return result
