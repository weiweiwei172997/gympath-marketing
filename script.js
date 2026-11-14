/* GymPath marketing layer: small, dependency-free controllers for the static site. */
(function () {
  "use strict";

  const planData = {
    start: {
      kicker: "STARTER / DAY 01", duration: "固定示例", title: "健身入门",
      description: "从热身、深蹲和俯卧撑开始，练习基本动作。",
      previewItems: ["全身热身", "杯式深蹲", "斜板俯卧撑"],
      days: [
        { label: "开始", title: "练习基本动作", warmup: "轻松走动 5 分钟，再用轻重量或徒手熟悉今天的动作。", exercises: [
          ["杯式深蹲", "2 组 × 8 次", "休息 90 秒", "脚掌贴地，缓慢下蹲到能控制的位置，再站起。选择能保持动作稳定的重量。"],
          ["斜板俯卧撑", "2 组 × 6–8 次", "休息 90 秒", "双手撑在稳固台面上，身体保持直线，缓慢屈肘下降再推起。"]
        ]},
        { label: "移动", title: "练习躯干与髋部控制", warmup: "轻柔活动肩、髋和踝，各 30 秒。", exercises: [
          ["鸟狗式", "2 组 × 6 次 / 侧", "休息 60 秒", "四肢撑地，缓慢伸出对侧手脚，保持躯干稳定，再收回。"],
          ["臀桥", "2 组 × 10 次", "休息 60 秒", "脚掌贴地，抬起髋部并停留一秒，避免过度挺腰。"]
        ]},
        { label: "恢复", title: "轻松活动与休息", warmup: "散步或轻松骑行 10 分钟，以能正常说话的强度为准。", exercises: [
          ["轻松步行", "10–20 分钟", "保持可交谈强度", "放慢步速，保持能正常说话的强度。"],
          ["呼吸与活动度", "5 分钟", "缓慢呼吸", "缓慢呼吸，轻柔活动肩和髋；出现不适就停止。"]
        ]}
      ]
    },
    strength: {
      kicker: "FOUNDATION / DAY 01", duration: "固定示例", title: "基础力量",
      description: "用基础动作练习力量，保持动作稳定，每组留出余力。",
      previewItems: ["关节热身", "高脚杯深蹲", "哑铃划船"],
      days: [
        { label: "基础", title: "全身力量练习", warmup: "轻松走动 5 分钟，再用轻重量或徒手练习动作 2 轮。", exercises: [
          ["高脚杯深蹲", "3 组 × 6 次", "休息 120 秒", "保持躯干和脚掌稳定；每组结束时保留可控余力。"],
          ["哑铃划船", "3 组 × 8 次 / 侧", "休息 90 秒", "保持背部稳定，把哑铃拉向髋部，再缓慢放下，避免摆动借力。"]
        ]},
        { label: "推拉", title: "上肢推拉练习", warmup: "先做肩胛活动和轻重量推拉各 8 次。", exercises: [
          ["斜板俯卧撑", "3 组 × 6–10 次", "休息 90 秒", "选择稳固的支撑面和合适高度，最后两次仍应保持身体直线。"],
          ["弹力带下拉", "3 组 × 10 次", "休息 90 秒", "确认弹力带固定牢靠，肩膀远离耳朵，屈肘下拉再缓慢还原。"]
        ]},
        { label: "恢复", title: "轻松活动与回顾", warmup: "散步 10 分钟，补充水分，观察身体状态。", exercises: [
          ["低强度有氧", "12–20 分钟", "保持可交谈强度", "选择散步或轻松骑行，保持能正常说话的强度。"],
          ["训练记录回顾", "2 分钟", "记下动作感受", "记下动作、次数、疲劳程度和不适情况。"]
        ]}
      ]
    },
    recovery: {
      kicker: "RESET / DAY 01", duration: "固定示例", title: "恢复训练",
      description: "从轻量动作开始，逐步恢复训练。",
      previewItems: ["轻松热身", "坐姿起立", "墙面俯卧撑"],
      days: [
        { label: "重启", title: "轻量动作练习", warmup: "慢走 5 分钟，配合几次自然深呼吸。", exercises: [
          ["坐姿起立", "2 组 × 6 次", "休息 90 秒", "选择稳固椅子，脚掌贴地，缓慢站起再坐下；不适时停止。"],
          ["墙面俯卧撑", "2 组 × 6 次", "休息 90 秒", "双手撑墙，缓慢屈肘靠近墙面再推回；调整站距，保持动作可控。"]
        ]},
        { label: "活动", title: "步行与轻柔活动", warmup: "做踝、髋、肩的轻柔活动，各 30 秒。", exercises: [
          ["轻松步行", "10 分钟", "保持可交谈强度", "放慢步速，保持能正常说话的强度。"],
          ["猫牛式", "2 组 × 6 次", "缓慢呼吸", "四肢撑地，随呼吸轻轻拱背和还原，不强行增加幅度。"]
        ]},
        { label: "观察", title: "回顾训练后的感受", warmup: "坐下，做几次慢呼吸，回顾今天的感觉。", exercises: [
          ["身体感受检查", "3 分钟", "安静休息", "留意呼吸、疲劳和不适是否恢复；不适持续或加重时停止训练并寻求专业帮助。"],
          ["简单记录", "2 分钟", "记录疲劳和不适", "记下“轻松 / 一般 / 不适”以及不适部位。"]
        ]}
      ]
    }
  };

  // DOM helpers only deal with text and locally authored data, never raw HTML inputs.
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const setText = (selector, value) => { $(selector).textContent = value; };
  const safePlanKey = key => Object.prototype.hasOwnProperty.call(planData, key) ? key : "start";
  function element(tag, className, copy) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (copy !== undefined) node.textContent = copy;
    return node;
  }
  function clearResult(result) {
    result.hidden = true;
    result.replaceChildren();
  }

  // All tab sets share arrow-key navigation, selected state and a single Tab stop.
  function bindTabs(tabs, attribute, onSelect) {
    const select = (key, focus = false) => {
      tabs.forEach(tab => {
        const active = tab.dataset[attribute] === String(key);
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
        if (active && focus) tab.focus();
      });
      onSelect(key);
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => select(tab.dataset[attribute]));
      tab.addEventListener("keydown", event => {
        const changes = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 };
        let next;
        if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else if (changes[event.key]) next = (index + changes[event.key] + tabs.length) % tabs.length;
        else return;
        event.preventDefault();
        select(tabs[next].dataset[attribute], true);
      });
    });
    return select;
  }

  function initNavigation() {
    const toggle = $(".menu-toggle");
    const nav = $("#site-nav");
    if (!toggle || !nav) return;
    const setOpen = open => {
      nav.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", String(open));
      toggle.textContent = open ? "关闭" : "菜单";
    };
    toggle.addEventListener("click", () => setOpen(!nav.classList.contains("is-open")));
    $$("a", nav).forEach(link => link.addEventListener("click", () => setOpen(false)));
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && nav.classList.contains("is-open")) {
        setOpen(false);
        toggle.focus();
      }
    });
    window.matchMedia("(min-width: 801px)").addEventListener("change", () => setOpen(false));
  }

  function initPreview() {
    const panel = $("#preview-panel");
    if (!panel) return;
    const select = bindTabs($$("[data-preview]"), "preview", rawKey => {
      const key = safePlanKey(rawKey);
      const plan = planData[key];
      setText("#preview-kicker", plan.kicker);
      setText("#preview-duration", plan.duration);
      setText("#preview-title-text", plan.title);
      setText("#preview-description", plan.description);
      $("#preview-items").replaceChildren(...plan.previewItems.map(copy => element("span", "", copy)));
      $("#preview-link").href = "demo.html?plan=" + key;
      panel.setAttribute("aria-labelledby", "preview-" + key);
    });
    select("start");
  }

  function renderDay(day) {
    const label = element("p", "sample-label", "固定示例安排");
    const title = element("h3", "day-title", day.title);
    const warmup = element("div", "warmup-strip");
    warmup.append(element("strong", "", "先热身"), element("p", "", day.warmup));
    const list = element("ol", "exercise-list");
    day.exercises.forEach((entry, index) => {
      const item = element("li");
      const details = element("details", "exercise-item");
      const summary = element("summary", "exercise-summary");
      const info = element("span", "exercise-info");
      info.append(element("strong", "exercise-name", entry[0]), element("span", "exercise-prescription", entry[1] + " / " + entry[2]));
      summary.append(element("span", "exercise-count", String(index + 1).padStart(2, "0")), info);
      details.append(summary, element("p", "exercise-detail", entry[3]));
      item.append(details);
      list.append(item);
    });
    $("#day-panel").replaceChildren(label, title, warmup, list);
  }

  function initPlanDemo() {
    let currentPlan = "start";
    const dayTabs = $$("[data-day]");
    const selectDay = bindTabs(dayTabs, "day", value => {
      const index = Number(value);
      renderDay(planData[currentPlan].days[index]);
      $("#day-panel").setAttribute("aria-labelledby", "day-tab-" + index);
      setText("#plan-kicker", planData[currentPlan].kicker.replace("01", String(index + 1).padStart(2, "0")));
      clearResult($("#feedback-result"));
    });
    const selectPlan = bindTabs($$("[data-plan]"), "plan", rawKey => {
      currentPlan = safePlanKey(rawKey);
      const plan = planData[currentPlan];
      setText("#plan-heading", plan.title);
      setText("#plan-description", plan.description);
      setText("#plan-duration", plan.duration);
      $("#plan-panel").setAttribute("aria-labelledby", "plan-tab-" + currentPlan);
      dayTabs.forEach((tab, index) => $("span", tab).textContent = plan.days[index].label);
      selectDay("0");
    });
    selectPlan(safePlanKey(new URLSearchParams(location.search).get("plan")));
  }

  // This rule is deliberately an educational example, not the old Python engine.
  function feedbackExample(level, discomfort) {
    if (discomfort === "pain") return { state: "is-caution", title: "停止训练，检查不适", copy: "出现锐痛、麻木、放射痛或持续加重的不适时，请停止相关动作，并寻求专业帮助。" };
    if (level >= 8 || discomfort === "tired") return { state: "is-adjustment", title: "下次减少训练量", copy: "反馈示例：下次缩短训练或减少组数，恢复后再逐步增加。" };
    return { state: "", title: "先保持当前训练量", copy: "反馈示例：下次训练前检查疲劳和不适情况，再决定是否增加难度。" };
  }

  function initFeedback() {
    const form = $("#feedback-form");
    const result = $("#feedback-result");
    const fatigue = $("#fatigue");
    form.addEventListener("input", () => {
      setText("#fatigue-output", fatigue.value + " / 10");
      clearResult(result);
    });
    form.addEventListener("submit", event => {
      event.preventDefault();
      const outcome = feedbackExample(Number(fatigue.value), $("#discomfort").value);
      result.className = "feedback-result " + outcome.state;
      result.replaceChildren(element("strong", "feedback-title", outcome.title), element("p", "", outcome.copy), element("p", "sample-label", "反馈流程示例 / 不提交、不保存信息"));
      result.hidden = false;
    });
    $("fieldset", form).disabled = false;
  }

  // Page-specific controllers can be understood and changed independently.
  initNavigation();
  initPreview();
  if ($(".demo-page")) { initPlanDemo(); initFeedback(); }
  document.documentElement.classList.add("js-enabled");
}());
