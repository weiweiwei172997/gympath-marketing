/* Native trial controller. Planning and display translations belong to the API. */
(function () {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const form = $("#trial-form");
  const fieldset = form.querySelector("fieldset");
  const button = $("#generate-plan");
  const errorBox = $("#trial-error");
  const status = $("#service-status");
  const result = $("#trial-result");
  const empty = $("#trial-empty");
  const printContent = $("#print-plan-content");
  const saveButton = $("#save-plan");
  const saveStatus = $("#save-status");
  let serviceReady = false;
  let currentPlan = null;
  let currentPreferences = null;
  let pending = false;
  let checking = false;
  let saving = false;
  let saved = false;
  let account = null;
  let accountChecked = false;

  class RequestError extends Error {
    constructor(message, unavailable = false) { super(message); this.unavailable = unavailable; }
  }
  function node(tag, className, copy) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (copy !== undefined) item.textContent = copy;
    return item;
  }
  function listOf(items, className) {
    const list = node("ul", className);
    items.forEach(copy => list.append(node("li", "", copy)));
    return list;
  }
  function serviceMessage(title, copy) {
    status.replaceChildren(node("strong", "", title), node("p", "", copy));
    if (serviceReady) return;
    const actions = node("div", "service-actions");
    const link = node("a", "text-link", "查看固定演示 ↗");
    link.href = "demo.html";
    const retry = node("button", "button button-quiet", checking ? "正在检查…" : "重新检查服务");
    retry.type = "button";
    retry.disabled = checking;
    retry.addEventListener("click", checkService);
    actions.append(link, retry);
    status.append(actions);
  }
  function clearPlan() {
    currentPlan = null;
    currentPreferences = null;
    saved = false;
    saveButton.disabled = true;
    saveButton.textContent = "保存到账号";
    saveStatus.replaceChildren();
    document.body.classList.remove("has-print-plan");
    result.hidden = true;
    empty.hidden = false;
    ["#plan-summary", "#trial-day-buttons", "#trial-day-content"].forEach(id => $(id).replaceChildren());
    printContent.replaceChildren();
  }
  function showError(copy, focus = false) {
    errorBox.textContent = copy;
    errorBox.hidden = false;
    if (focus) errorBox.focus();
  }
  async function request(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(path, { ...options, signal: controller.signal, cache: "no-store", credentials: options.credentials || "omit" });
      if (!(response.headers.get("content-type") || "").includes("application/json")) {
        throw new RequestError("暂时无法连接计划服务，请重试或查看固定演示。", true);
      }
      const data = await response.json();
      if (!response.ok) {
        if (response.status === 401) throw new RequestError("请先登录账号，再保存计划。");
        if (response.status === 403) throw new RequestError("登录状态需要刷新，请重新登录后再试。");
        if (response.status === 409) throw new RequestError("已保存 20 份计划，请在账号页删除不需要的计划后再试。");
        if (response.status === 422) throw new RequestError("请检查训练偏好和填写的数值。");
        if (response.status === 400) throw new RequestError("暂时无法生成计划。请增加时间或调整次数后再试。");
        throw new RequestError("生成失败，请稍后重试。", true);
      }
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new RequestError("服务响应超时，请重试或查看固定演示。", true);
      if (error instanceof TypeError) throw new RequestError("无法连接服务，请稍后重试。", true);
      if (error instanceof SyntaxError) throw new RequestError("无法读取计划，请重新检查服务。", true);
      throw error;
    } finally { clearTimeout(timeout); }
  }
  async function checkService() {
    if (checking || pending) return;
    if (!/^https?:$/.test(location.protocol)) {
      serviceMessage("需要启动本地服务", "请按源码中的 README 启动服务，再用 http://127.0.0.1:8081 打开本站。");
      return;
    }
    checking = true;
    serviceReady = false;
    fieldset.disabled = true;
    serviceMessage("正在连接…", "正在检查计划服务。");
    try {
      const health = await request("/api/health");
      if (health.service !== "gympath-local-trial" || !Array.isArray(health.capabilities) || !health.capabilities.includes("time-fit-v1")) {
        throw new RequestError("服务版本不匹配。请按源码中的 README 重启试用服务。", true);
      }
      serviceReady = true;
      fieldset.disabled = false;
      errorBox.hidden = true;
      serviceMessage("服务已连接", "可以填写偏好并生成计划。");
      checkAccount();
    } catch (error) {
      checking = false;
      serviceMessage("计划服务尚未连接", error.message);
    } finally { checking = false; }
  }
  function updateSaveStatus() {
    saveButton.disabled = !currentPlan || saving || saved;
    if (!currentPlan) return;
    if (saved) { saveButton.textContent = "已保存"; return; }
    saveButton.textContent = saving ? "正在保存…" : "保存到账号";
    saveStatus.replaceChildren();
    if (account?.user) {
      saveStatus.textContent = `已登录：${account.user.username}。点击保存后，可在账号页再次查看。`;
    } else {
      saveStatus.append(document.createTextNode(accountChecked ? "登录后可保存这份计划。 " : "保存前会检查登录状态。 "));
    }
    const link = node("a", "", account?.user ? "查看我的计划 ↗" : "注册 / 登录 ↗");
    link.href = "account.html?next=trial";
    saveStatus.append(link);
  }
  async function checkAccount() {
    try { account = await request("/api/auth/me", { credentials: "same-origin" }); }
    catch { account = null; }
    accountChecked = true;
    if (!saving && !saved) updateSaveStatus();
  }
  function teachingLink(rawUrl, label) {
    if (!rawUrl) return null;
    try {
      const url = new URL(rawUrl);
      const allowed = ["bilibili.com", "www.bilibili.com", "search.bilibili.com", "douyin.com", "www.douyin.com"];
      if (url.protocol !== "https:" || !allowed.includes(url.hostname)) return null;
      const copy = url.pathname.includes("BV1Qd4y1Z75J") ? "通用参考视频" : label;
      const link = node("a", "text-link teaching-link", copy + " ↗");
      link.href = url.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      return link;
    } catch { return null; }
  }
  function prescription(exercise) {
    const reps = /^\d+(?:\s*[-–]\s*\d+)?$/.test(exercise.reps) ? exercise.reps + " 次" : exercise.reps;
    return `${exercise.sets} 组 × ${reps} / 组间休息 ${exercise.rest_seconds} 秒`;
  }
  function durationDetails(day) {
    const box = node("details", "duration-details");
    box.append(node("summary", "", `预计约 ${day.estimated_minutes} 分钟 · 查看时间组成`));
    const d = day.duration_breakdown;
    const minutes = seconds => (seconds / 60).toFixed(1).replace(/\.0$/, "");
    box.append(listOf([
      `热身 ${minutes(d.warmup_seconds)} 分钟`,
      `动作执行约 ${minutes(d.exercise_seconds)} 分钟`,
      `组间休息 ${minutes(d.rest_seconds)} 分钟`,
      `动作准备与切换约 ${minutes(d.transition_seconds)} 分钟`,
      `收尾 ${minutes(d.cooldown_seconds)} 分钟`
    ], "duration-list"));
    box.append(node("p", "form-note", currentPlan.adaptation.estimation_note));
    return box;
  }
  function renderDay(index) {
    const day = currentPlan.weekly_schedule[index];
    const content = $("#trial-day-content");
    content.setAttribute("aria-labelledby", "trial-day-" + index);
    content.replaceChildren(node("h3", "day-title", day.focus || day.day));
    if (day.session_note) content.append(node("p", day.is_rest_day ? "rest-day" : "demo-lede", day.session_note));
    if (day.rest_note) content.append(node("p", "demo-lede", day.rest_note));
    const exercises = day.exercises || [];
    if (exercises.length) {
      content.append(durationDetails(day));
      const warmup = node("div", "warmup-strip");
      warmup.append(node("strong", "", "热身 / 约 5 分钟"), listOf(day.warmup, "trial-warmup"));
      content.append(warmup);
      const tools = node("div", "session-tools");
      const toggle = node("button", "button button-text", "展开本节全部动作");
      toggle.type = "button";
      const list = node("ol", "exercise-list");
      const updateToggle = () => {
        const allOpen = [...list.querySelectorAll("details")].every(item => item.open);
        toggle.textContent = allOpen ? "收起本节全部动作" : "展开本节全部动作";
        toggle.setAttribute("aria-expanded", String(allOpen));
      };
      toggle.addEventListener("click", () => {
        const open = [...list.querySelectorAll("details")].some(item => !item.open);
        list.querySelectorAll("details").forEach(item => { item.open = open; });
        updateToggle();
      });
      toggle.setAttribute("aria-expanded", "false");
      tools.append(toggle, node("span", "sample-label", `${exercises.length} 个动作 / ${day.adaptation.planned_sets} 组`));
      content.append(tools);
      exercises.forEach((exercise, order) => {
        const li = node("li");
        const details = node("details", "exercise-item");
        const summary = node("summary", "exercise-summary");
        const info = node("span", "exercise-info");
        info.append(node("strong", "exercise-name", exercise.name), node("span", "exercise-prescription", prescription(exercise)));
        summary.append(node("span", "exercise-count", String(order + 1).padStart(2, "0")), info);
        const detail = node("div", "exercise-detail");
        if (exercise.name_original) detail.append(node("p", "source-name", "英文名称 / " + exercise.name_original));
        if (exercise.target_muscle) detail.append(node("p", "", "主要锻炼部位 / " + exercise.target_muscle));
        if (exercise.notes) detail.append(node("p", "", exercise.notes));
        const link = teachingLink(exercise.teaching_url, "查看参考教学");
        if (link) detail.append(link);
        details.append(summary, detail);
        details.addEventListener("toggle", updateToggle);
        li.append(details);
        list.append(li);
      });
      content.append(list);
      if (day.rest_policy) content.append(node("p", "form-note", day.rest_policy));
      content.append(node("p", "form-note", "收尾：轻松走动 2 分钟。需要时延长热身或休息，不必赶着做完。"));
    }
    [...$("#trial-day-buttons").children].forEach((tab, i) => {
      tab.setAttribute("aria-selected", String(i === index));
      tab.tabIndex = i === index ? 0 : -1;
      tab.classList.toggle("is-active", i === index);
    });
  }
  function renderPrint(plan, preferences) {
    printContent.replaceChildren(node("p", "eyebrow", "GYMPATH / 训练计划"), node("h1", "", plan.split.split_name));
    printContent.append(node("p", "", `每周最多 ${preferences.days_per_week} 次，实际安排 ${plan.days_per_week} 次；每次可用 ${preferences.minutes_per_session} 分钟。`));
    printContent.append(node("p", "", plan.split.reason));
    printContent.append(listOf([...new Set([...plan.adaptation.notes, ...plan.split.notes])], "print-notes"));
    printContent.append(node("p", "", "部分参考视频包含其他动作，请按本站安排训练。"));
    printContent.append(node("p", "", plan.adaptation.estimation_note));
    plan.weekly_schedule.forEach(day => {
      const section = node("section", "print-session");
      section.append(node("h2", "", day.day + " / " + day.focus));
      if (day.session_note) section.append(node("p", "", day.session_note));
      if (day.is_rest_day) {
        if (day.rest_note) section.append(node("p", "", day.rest_note));
      } else {
        section.append(node("p", "", `预计约 ${day.estimated_minutes} 分钟，含5分钟热身和2分钟收尾。`));
        section.append(listOf(day.warmup, "print-warmup"));
        const exercises = node("ol", "print-exercises");
        day.exercises.forEach(exercise => {
          const item = node("li", "print-exercise");
          item.append(node("h3", "", exercise.name), node("p", "", prescription(exercise)), node("p", "", exercise.notes));
          if (exercise.target_muscle) item.append(node("p", "", "主要锻炼部位 / " + exercise.target_muscle));
          exercises.append(item);
        });
        section.append(exercises);
        if (day.rest_policy) section.append(node("p", "", day.rest_policy));
        section.append(listOf(day.cooldown, "print-cooldown"));
      }
      printContent.append(section);
    });
    printContent.append(node("p", "print-boundary", "计划未评估个人身体情况，不适用于医疗或伤病康复。出现锐痛或持续加重的不适时，请停止并寻求专业帮助。"));
    document.body.classList.add("has-print-plan");
  }
  function renderPlan(plan, preferences) {
    if (!Array.isArray(plan.weekly_schedule) || !plan.weekly_schedule.length || !plan.split || plan.adaptation?.version !== "time-fit-v1") {
      throw new RequestError("计划内容不完整，请重新检查服务。", true);
    }
    currentPlan = plan;
    currentPreferences = { ...preferences };
    const schedule = plan.weekly_schedule;
    const training = schedule.filter(day => !day.is_rest_day);
    if (!training.length || training.some(day => !Number.isFinite(day.estimated_minutes) || !day.duration_breakdown)) {
      throw new RequestError("计划缺少时间安排，请重新检查服务。", true);
    }
    const times = training.map(day => day.estimated_minutes);
    const min = Math.min(...times), max = Math.max(...times);
    const summary = $("#plan-summary");
    summary.replaceChildren(node("h3", "", plan.split.split_name), node("p", "", plan.split.reason));
    const metrics = node("dl", "plan-metrics");
    [["训练次数", plan.days_per_week + " 次"], ["每节预计", (min === max ? min : min + "–" + max) + " 分钟"], ["休息安排", schedule.length - training.length + " 次"]].forEach(([label, value]) => {
      const item = node("div");
      item.append(node("dt", "", label), node("dd", "", value));
      metrics.append(item);
    });
    summary.append(metrics, node("p", "form-note", `按每周最多 ${preferences.days_per_week} 次、每次可用 ${preferences.minutes_per_session} 分钟安排。`));
    const explanation = node("details", "fit-explanation");
    explanation.append(node("summary", "", "怎样安排训练和休息？"));
    explanation.append(listOf([...new Set([...plan.adaptation.notes, ...plan.split.notes])], "plan-notes"));
    explanation.append(node("p", "form-note", "部分参考视频包含其他动作，请按本站安排训练。"));
    summary.append(explanation);
    const tabs = $("#trial-day-buttons");
    tabs.replaceChildren();
    schedule.forEach((day, index) => {
      const tab = node("button", "day-button fitted-day-button");
      tab.append(node("span", "day-label", day.day), node("strong", "", day.focus), node("small", "", day.is_rest_day ? "轻松活动 / 休息" : `约 ${day.estimated_minutes} 分钟`));
      tab.type = "button";
      tab.id = "trial-day-" + index;
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-controls", "trial-day-content");
      tab.addEventListener("click", () => renderDay(index));
      tab.addEventListener("keydown", event => {
        let next;
        if (event.key === "Home") next = 0;
        else if (event.key === "End") next = schedule.length - 1;
        else if (["ArrowRight", "ArrowDown"].includes(event.key)) next = (index + 1) % schedule.length;
        else if (["ArrowLeft", "ArrowUp"].includes(event.key)) next = (index - 1 + schedule.length) % schedule.length;
        else return;
        event.preventDefault();
        renderDay(next);
        tabs.children[next].focus();
      });
      tabs.append(tab);
    });
    renderDay(0);
    renderPrint(plan, preferences);
    result.hidden = false;
    empty.hidden = true;
    updateSaveStatus();
    summary.focus({ preventScroll: true });
    if (matchMedia("(max-width: 800px)").matches) summary.scrollIntoView({ block: "start" });
  }
  function readPreferences() {
    const errors = [];
    const values = {};
    [["trial-days", 1, 7], ["trial-minutes", 15, 180]].forEach(([id, min, max]) => {
      const field = $("#" + id);
      const valid = field.value !== "" && Number.isInteger(field.valueAsNumber) && field.valueAsNumber >= min && field.valueAsNumber <= max;
      $("#" + id + "-error").textContent = valid ? "" : `请输入 ${min}–${max} 范围内的整数。`;
      if (valid) field.removeAttribute("aria-invalid");
      else { field.setAttribute("aria-invalid", "true"); errors.push(field); }
      values[field.name] = field.valueAsNumber;
    });
    if (errors.length) { errors[0].focus(); throw new RequestError("请修正标出的数值后再试。"); }
    return { level: $("#trial-level").value, goal: $("#trial-goal").value, ...values };
  }
  form.addEventListener("input", () => {
    if (pending || saving) return;
    clearPlan();
    errorBox.hidden = true;
    ["trial-days", "trial-minutes"].forEach(id => { $("#" + id + "-error").textContent = ""; $("#" + id).removeAttribute("aria-invalid"); });
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (pending || saving || !serviceReady) return;
    clearPlan();
    errorBox.hidden = true;
    let preferences;
    try { preferences = readPreferences(); } catch (error) { showError(error.message); return; }
    pending = true;
    fieldset.disabled = true;
    button.textContent = "正在生成…";
    form.setAttribute("aria-busy", "true");
    try {
      const plan = await request("/api/plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(preferences) });
      renderPlan(plan, preferences);
    } catch (error) {
      clearPlan();
      if (error.unavailable) {
        serviceReady = false;
        serviceMessage("服务暂不可用", "请重新检查服务，或先查看固定演示。");
      }
      showError(error.message, true);
    } finally {
      pending = false;
      fieldset.disabled = !serviceReady;
      form.removeAttribute("aria-busy");
      button.replaceChildren(document.createTextNode("生成训练计划 "), node("span", "", "↗"));
    }
  });
  saveButton.addEventListener("click", async () => {
    if (!currentPlan || !currentPreferences || pending || saving || saved) return;
    saving = true;
    fieldset.disabled = true;
    saveButton.disabled = true;
    saveButton.textContent = "正在保存…";
    saveStatus.textContent = "正在检查账号并保存计划。";
    try {
      const session = await request("/api/auth/me", { credentials: "same-origin" });
      account = session;
      accountChecked = true;
      if (!session.user || !session.csrf_token) {
        saving = false;
        updateSaveStatus();
        return;
      }
      await request("/api/plans", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrf_token },
        body: JSON.stringify({ preferences: currentPreferences })
      });
      saved = true;
      saveButton.textContent = "已保存";
      saveStatus.replaceChildren(document.createTextNode("已保存到账号。 "));
      const link = node("a", "", "查看我的计划 ↗");
      link.href = "account.html";
      saveStatus.append(link);
    } catch (error) {
      saveStatus.textContent = error.message;
      const link = node("a", "", " 前往账号页 ↗");
      link.href = "account.html";
      saveStatus.append(link);
    } finally {
      saving = false;
      saveButton.disabled = saved || !currentPlan;
      if (!saved) saveButton.textContent = "保存到账号";
      fieldset.disabled = !serviceReady;
    }
  });
  $("#print-plan").addEventListener("click", () => { if (currentPlan) window.print(); });
  checkService();
}());
