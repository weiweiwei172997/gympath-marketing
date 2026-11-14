/* Account sessions use server cookies; credentials and CSRF tokens stay out of browser storage. */
(function () {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const form = $("#auth-form");
  const fieldset = form.querySelector("fieldset");
  const authTabs = [...document.querySelectorAll("[data-auth]")];
  const submit = $("#auth-submit");
  const username = $("#account-username");
  const password = $("#account-password");
  const confirm = $("#account-confirm");
  const message = $("#account-message");
  const errorBox = $("#account-error");
  const service = $("#account-service");
  let mode = "register";
  let user = null;
  let csrfToken = null;
  let serviceReady = false;
  let checking = false;
  let authBusy = false;
  let plansBusy = false;
  let logoutBusy = false;
  let plans = [];
  let selectedId = null;
  let deletingId = null;
  let confirmingId = null;
  let sessionGeneration = 0;

  class ApiError extends Error {
    constructor(copy, status = 0) { super(copy); this.status = status; }
  }
  function node(tag, className, copy) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (copy !== undefined) item.textContent = String(copy);
    return item;
  }
  function clearMessages() { message.hidden = true; errorBox.hidden = true; }
  function showMessage(copy) { errorBox.hidden = true; message.textContent = copy; message.hidden = false; }
  function showSignedInMessage(copy) {
    showMessage(copy);
    const link = node("a", "text-link", new URLSearchParams(location.search).get("next") === "trial" ? "返回训练计划 ↗" : "去生成计划 ↗");
    link.href = "trial.html";
    message.append(document.createTextNode(" "), link);
  }
  function showError(copy, focus = false) {
    message.hidden = true; errorBox.textContent = copy; errorBox.hidden = false;
    if (focus) errorBox.focus();
  }
  function serviceMessage(title, copy, retry = false) {
    service.replaceChildren(node("strong", "", title), node("p", "", copy));
    if (!retry) return;
    const actions = node("div", "service-actions");
    const example = node("a", "text-link", "查看固定示例 ↗");
    example.href = "demo.html";
    const button = node("button", "button button-quiet", checking ? "正在连接…" : "重新连接");
    button.type = "button"; button.disabled = checking;
    button.addEventListener("click", checkSession);
    actions.append(example, button); service.append(actions);
  }
  async function request(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(path, { ...options, credentials: "same-origin", cache: "no-store", signal: controller.signal });
      if (response.status === 204) return null;
      const isJson = (response.headers.get("content-type") || "").includes("application/json");
      const data = isJson ? await response.json() : null;
      if (!response.ok) {
        const fallbacks = {
          400: "填写内容有误，请检查后重试。", 401: "用户名或密码不正确，或登录已过期。",
          403: "登录状态已变化，请重新连接后再试。", 404: "这份计划已不存在，请刷新列表。",
          409: "这个用户名已被使用，请换一个。", 413: "提交内容过长，请缩短后重试。",
          422: "填写内容不符合要求，请检查用户名和密码。", 429: "操作过于频繁，请稍后再试。"
        };
        const detail = typeof data?.detail === "string" ? data.detail : typeof data?.message === "string" ? data.message : "";
        const copy = fallbacks[response.status] || "账号服务暂时不可用，请稍后重试。";
        // Server errors are handled by status; do not display raw technical details.
        throw new ApiError(response.status < 500 && detail && /[\u4e00-\u9fff]/.test(detail) ? detail : copy, response.status);
      }
      if (!isJson) throw new ApiError("账号服务尚未连接。请重新连接，或先查看固定示例。");
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new ApiError("连接超时，请稍后重试。也可以先查看固定示例。");
      if (error instanceof TypeError) throw new ApiError("无法连接账号服务，请重新连接，或先查看固定示例。");
      if (error instanceof SyntaxError) throw new ApiError("账号服务返回了无法读取的内容，请重新连接。");
      throw error;
    } finally { clearTimeout(timeout); }
  }
  function clearFieldErrors() {
    [username, password, confirm].forEach(field => {
      field.removeAttribute("aria-invalid");
      $("#" + field.id + "-error").textContent = "";
    });
  }
  function setBusy() {
    fieldset.disabled = !serviceReady || authBusy || checking;
    authTabs.forEach(tab => { tab.disabled = authBusy; });
    $("#logout-button").disabled = !serviceReady || checking || logoutBusy || plansBusy || deletingId !== null;
    $("#refresh-plans").disabled = !serviceReady || checking || plansBusy || logoutBusy || deletingId !== null;
    document.querySelectorAll("[data-plan-delete]").forEach(button => {
      button.disabled = !serviceReady || checking || plansBusy || logoutBusy || deletingId !== null;
    });
  }
  function selectMode(next, focus = false) {
    if (authBusy) return;
    mode = next;
    clearFieldErrors(); clearMessages(); password.value = ""; confirm.value = "";
    const registering = mode === "register";
    $("#confirm-password-field").hidden = !registering;
    confirm.required = registering;
    password.autocomplete = registering ? "new-password" : "current-password";
    password.minLength = registering ? 8 : 1;
    $("#account-password-note").textContent = registering
      ? "至少 8 个字符，包含字母和数字。"
      : "请输入注册时设置的密码。";
    $("#auth-title").textContent = registering ? "创建你的账号" : "登录你的账号";
    $("#account-data-note").textContent = registering
      ? "用户名和密码会提交给 GymPath，用于创建账号。计划仅在点击“保存到账号”后保存。"
      : "登录后可以查看已保存的计划。新计划仅在点击“保存到账号”后保存。";
    submit.replaceChildren(document.createTextNode(registering ? "创建账号 " : "登录 "), node("span", "", "↗"));
    authTabs.forEach(tab => {
      const active = tab.dataset.auth === mode;
      tab.classList.toggle("is-active", active); tab.setAttribute("aria-selected", String(active)); tab.tabIndex = active ? 0 : -1;
      if (active) { $("#auth-panel").setAttribute("aria-labelledby", tab.id); if (focus) tab.focus(); }
    });
  }
  function validSession(data) {
    return data && (data.user === null || (typeof data.user === "object" && typeof data.user.username === "string" && data.user.id !== undefined && typeof data.csrf_token === "string" && data.csrf_token.length));
  }
  function applySession(data) {
    if (!validSession(data)) throw new ApiError("账号状态无法读取，请重新连接。");
    sessionGeneration += 1;
    user = data.user; csrfToken = user ? data.csrf_token : null;
    $("#auth-layout").hidden = Boolean(user); $("#account-dashboard").hidden = !user;
    if (user) {
      $("#account-identity").textContent = "当前账号：" + user.username;
      serviceMessage("已登录", "计划仅在主动保存后存入你的账号。");
    } else {
      plans = []; selectedId = null; confirmingId = null;
      $("#saved-plans-list").replaceChildren(); resetPlanView();
      serviceMessage("账号服务已连接", "可以注册新账号，或登录已有账号。");
    }
    setBusy();
  }
  async function checkSession() {
    if (checking || authBusy || logoutBusy || deletingId !== null) return;
    checking = true; serviceReady = false; setBusy();
    serviceMessage("正在连接账号服务…", "正在确认登录状态。");
    try {
      const data = await request("/api/auth/me");
      serviceReady = true; applySession(data); clearMessages();
      if (user) await loadPlans();
    } catch (error) {
      serviceReady = false; checking = false;
      serviceMessage("账号服务尚未连接", error.message, true);
    } finally { checking = false; setBusy(); }
  }
  function readCredentials() {
    clearFieldErrors();
    const name = username.value.trim();
    const errors = [];
    const invalidate = (field, copy) => { field.setAttribute("aria-invalid", "true"); $("#" + field.id + "-error").textContent = copy; errors.push(field); };
    if (!/^[\u4e00-\u9fffA-Za-z0-9_-]{2,20}$/.test(name)) invalidate(username, "请输入 2–20 个字符，只用中文、字母、数字、_ 或 -。");
    const count = [...password.value].length;
    if (!count) invalidate(password, "请输入密码。");
    else if (count > 128 || new TextEncoder().encode(password.value).length > 256) invalidate(password, "密码过长，请缩短后重试。");
    else if (mode === "register" && (count < 8 || !/[A-Za-z]/.test(password.value) || !/[0-9]/.test(password.value))) invalidate(password, "密码至少 8 个字符，并包含字母和数字。");
    if (mode === "register" && confirm.value !== password.value) invalidate(confirm, "两次密码不一致，请重新输入。");
    if (errors.length) { errors[0].focus(); return null; }
    return { username: name, password: password.value };
  }
  function resetPlanView() {
    $("#saved-plan-title").textContent = "计划详情";
    $("#saved-plan-content").replaceChildren(node("p", "demo-lede", "选择一份已保存的计划查看。"));
  }
  function preferenceCopy(preferences) {
    if (!preferences || typeof preferences !== "object") return "";
    const levels = { beginner: "新手", restarting: "恢复训练", experienced: "有经验" };
    const goals = { muscle_gain: "增肌", strength_gain: "增强力量", fat_loss: "减脂", health: "居家活动" };
    return [levels[preferences.level], goals[preferences.goal], Number.isFinite(preferences.days_per_week) ? `每周最多 ${preferences.days_per_week} 次` : "", Number.isFinite(preferences.minutes_per_session) ? `每次 ${preferences.minutes_per_session} 分钟` : ""].filter(Boolean).join(" · ");
  }
  function dateCopy(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  }
  function planTitle(saved) { return typeof saved.title === "string" && saved.title ? saved.title : "训练计划"; }
  function renderLibrary() {
    const list = $("#saved-plans-list"); list.replaceChildren();
    $("#saved-plans-state").hidden = plans.length > 0;
    $("#saved-plans-state").textContent = plans.length ? "" : "还没有保存的计划。先生成一份，再点击“保存到账号”。";
    plans.forEach(saved => {
      const item = node("li", "saved-plan-card");
      if (saved.id === selectedId) item.classList.add("is-selected");
      item.append(node("h4", "", planTitle(saved)));
      const created = dateCopy(saved.created_at); if (created) item.append(node("p", "saved-plan-date", "保存于 " + created));
      const preferences = preferenceCopy(saved.preferences); if (preferences) item.append(node("p", "saved-plan-preferences", preferences));
      const actions = node("div", "saved-plan-actions");
      const open = node("button", "button account-open-button", saved.id === selectedId ? "正在查看" : "查看计划");
      open.type = "button"; open.setAttribute("aria-expanded", String(saved.id === selectedId)); open.setAttribute("aria-controls", "saved-plan-content");
      open.disabled = deletingId !== null || logoutBusy;
      open.addEventListener("click", () => { selectedId = saved.id; confirmingId = null; renderLibrary(); renderSavedPlan(saved, true); });
      const remove = node("button", "button button-text", "删除"); remove.type = "button"; remove.disabled = !serviceReady || checking || plansBusy || deletingId !== null || logoutBusy;
      remove.dataset.planDelete = "true";
      remove.id = "saved-plan-delete-" + saved.id;
      remove.setAttribute("aria-label", "删除计划：" + planTitle(saved));
      remove.addEventListener("click", () => { confirmingId = saved.id; renderLibrary(); $("#saved-plan-confirm-" + saved.id)?.focus(); });
      actions.append(open, remove); item.append(actions);
      if (confirmingId === saved.id) {
        const confirmation = node("div", "saved-plan-confirmation");
        confirmation.append(node("p", "", "删除后无法恢复这份计划。确认删除？"));
        const yes = node("button", "button account-button-dark", deletingId === saved.id ? "正在删除…" : "确认删除");
        yes.type = "button"; yes.id = "saved-plan-confirm-" + saved.id; yes.disabled = !serviceReady || checking || plansBusy || deletingId !== null;
        yes.dataset.planDelete = "true";
        yes.addEventListener("click", () => deletePlan(saved));
        const no = node("button", "button button-text", "取消"); no.type = "button"; no.disabled = deletingId !== null;
        no.addEventListener("click", () => { confirmingId = null; renderLibrary(); document.getElementById("saved-plan-delete-" + saved.id)?.focus(); });
        confirmation.append(yes, no); item.append(confirmation);
      }
      list.append(item);
    });
  }
  function copyList(items, className = "") {
    const list = node("ul", className);
    if (Array.isArray(items)) items.filter(value => typeof value === "string").forEach(value => list.append(node("li", "", value)));
    return list;
  }
  function teachingLink(rawUrl) {
    try {
      const url = new URL(rawUrl);
      const allowed = ["bilibili.com", "www.bilibili.com", "search.bilibili.com", "douyin.com", "www.douyin.com"];
      if (url.protocol !== "https:" || !allowed.includes(url.hostname)) return null;
      const label = url.pathname.includes("BV1Qd4y1Z75J") ? "通用参考视频" : "查看参考教学";
      const link = node("a", "text-link teaching-link", label + " ↗");
      link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer";
      return link;
    } catch { return null; }
  }
  function renderSavedPlan(saved, focus = false) {
    const content = $("#saved-plan-content"); content.replaceChildren();
    $("#saved-plan-title").textContent = planTitle(saved);
    const plan = saved.plan;
    if (!plan || !Array.isArray(plan.weekly_schedule) || !plan.weekly_schedule.length) {
      content.append(node("p", "demo-lede", "这份计划内容不完整。你可以重新生成并保存一份计划。")); return;
    }
    const preferences = preferenceCopy(saved.preferences); if (preferences) content.append(node("p", "demo-lede", preferences));
    if (typeof plan.split?.reason === "string") content.append(node("p", "demo-lede", plan.split.reason));
    content.append(node("p", "form-note", "按顺序训练并留出休息日。一周内安排不下时顺延，不压缩休息。预计用时可能因实际节奏、排队或额外热身增加。"));
    content.append(node("p", "form-note", "部分参考视频包含其他动作，请按本站安排训练。"));
    plan.weekly_schedule.forEach((day, index) => {
      if (!day || typeof day !== "object") return;
      const section = node("details", "saved-session"); section.open = index === 0;
      const summary = node("summary", "saved-session-summary");
      const title = node("span", "");
      title.append(node("strong", "", day.day || (day.is_rest_day ? "休息日" : "训练日")), node("span", "", day.focus || ""));
      summary.append(title, node("span", "saved-session-time", day.is_rest_day ? "至少休息一天" : Number.isFinite(day.estimated_minutes) ? `预计 ${day.estimated_minutes} 分钟` : ""));
      section.append(summary);
      const body = node("div", "saved-session-body");
      if (day.session_note) body.append(node("p", "demo-lede", day.session_note));
      if (day.is_rest_day) {
        if (day.rest_note) body.append(node("p", "demo-lede", day.rest_note));
      } else {
        const warmup = node("div", "warmup-strip");
        warmup.append(node("strong", "", "先热身"), copyList(day.warmup, "saved-plan-warmup")); body.append(warmup);
        const exercises = node("ol", "exercise-list");
        if (Array.isArray(day.exercises)) day.exercises.forEach((exercise, order) => {
          if (!exercise || typeof exercise !== "object") return;
          const li = node("li"); const details = node("details", "exercise-item");
          const heading = node("summary", "exercise-summary"); const info = node("span", "exercise-info");
          const rawReps = String(exercise.reps ?? ""); const reps = /^\d+(?:\s*[-–]\s*\d+)?$/.test(rawReps) ? rawReps + " 次" : rawReps;
          info.append(node("strong", "exercise-name", exercise.name || "动作"), node("span", "exercise-prescription", `${exercise.sets} 组 × ${reps} / 组间休息 ${exercise.rest_seconds} 秒`));
          heading.append(node("span", "exercise-count", String(order + 1).padStart(2, "0")), info);
          const detail = node("div", "exercise-detail");
          if (exercise.target_muscle) detail.append(node("p", "", "主要锻炼部位：" + exercise.target_muscle));
          if (exercise.notes) detail.append(node("p", "", exercise.notes));
          const link = teachingLink(exercise.teaching_url);
          if (link) detail.append(link);
          details.append(heading, detail); li.append(details); exercises.append(li);
        });
        body.append(exercises);
        if (day.rest_policy) body.append(node("p", "form-note", day.rest_policy));
        if (Array.isArray(day.cooldown) && day.cooldown.length) {
          const cooldown = node("div", "saved-plan-cooldown"); cooldown.append(node("strong", "", "收尾"), copyList(day.cooldown)); body.append(cooldown);
        }
      }
      section.append(body); content.append(section);
    });
    content.append(node("p", "form-note", "计划未评估个人身体情况，不适用于医疗或伤病康复。出现锐痛或持续加重的不适时，请停止并寻求专业帮助。"));
    if (focus) { $("#saved-plan-title").focus({ preventScroll: true }); if (matchMedia("(max-width: 800px)").matches) $("#saved-plan-title").scrollIntoView({ block: "start" }); }
  }
  async function sessionExpired(copy) {
    applySession({ user: null, csrf_token: null }); selectMode("login"); showError(copy, true);
  }
  async function loadPlans() {
    if (!user || !serviceReady || plansBusy || logoutBusy || deletingId !== null) return;
    const generation = sessionGeneration;
    plansBusy = true; setBusy();
    $("#saved-plans-state").hidden = false; $("#saved-plans-state").textContent = "正在读取计划…";
    try {
      const data = await request("/api/plans");
      if (generation !== sessionGeneration) return;
      if (!Array.isArray(data?.plans)) throw new ApiError("无法读取已保存的计划，请刷新列表。");
      plans = data.plans.filter(saved => saved && saved.id !== undefined);
      if (selectedId !== null && !plans.some(saved => saved.id === selectedId)) { selectedId = null; resetPlanView(); }
      renderLibrary();
      const selected = plans.find(saved => saved.id === selectedId); if (selected) renderSavedPlan(selected);
    } catch (error) {
      if (generation !== sessionGeneration) return;
      if (error.status === 401) { await sessionExpired("登录已过期，请重新登录后查看计划。"); }
      else { $("#saved-plans-state").hidden = false; $("#saved-plans-state").textContent = "暂时无法读取计划，请点击“刷新列表”。"; showError(error.message); }
    } finally { plansBusy = false; setBusy(); }
  }
  async function deletePlan(saved) {
    if (!serviceReady || checking || deletingId !== null || plansBusy || logoutBusy || !user || !csrfToken) return;
    deletingId = saved.id; clearMessages(); setBusy(); renderLibrary();
    try {
      await request("/api/plans/" + encodeURIComponent(saved.id), { method: "DELETE", headers: { "X-CSRF-Token": csrfToken } });
      plans = plans.filter(plan => plan.id !== saved.id); confirmingId = null;
      if (selectedId === saved.id) { selectedId = null; resetPlanView(); }
      showMessage("计划已删除。");
    } catch (error) {
      if (error.status === 401) await sessionExpired("登录已过期，请重新登录后删除计划。");
      else if (error.status === 403) { serviceReady = false; confirmingId = null; showError("登录状态已变化，请重新连接账号后再删除。"); serviceMessage("需要重新确认登录状态", "重新连接后，再管理计划。", true); }
      else showError(error.message, true);
    } finally {
      deletingId = null; setBusy(); renderLibrary();
      if (user && !plans.some(plan => plan.id === saved.id)) {
        const next = $("#saved-plans-list .account-open-button");
        (next || $("#refresh-plans")).focus();
      }
    }
  }
  authTabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectMode(tab.dataset.auth));
    tab.addEventListener("keydown", event => {
      let next;
      if (event.key === "Home") next = 0;
      else if (event.key === "End") next = authTabs.length - 1;
      else if (["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)) next = (index + 1) % authTabs.length;
      else return;
      event.preventDefault(); selectMode(authTabs[next].dataset.auth, true);
    });
  });
  form.addEventListener("input", event => {
    clearMessages(); const field = event.target;
    if ([username, password, confirm].includes(field)) { field.removeAttribute("aria-invalid"); $("#" + field.id + "-error").textContent = ""; }
  });
  form.addEventListener("submit", async event => {
    event.preventDefault(); if (authBusy || !serviceReady) return;
    clearMessages(); const credentials = readCredentials(); if (!credentials) return;
    authBusy = true; setBusy(); form.setAttribute("aria-busy", "true"); submit.textContent = mode === "register" ? "正在创建…" : "正在登录…";
    try {
      const data = await request("/api/auth/" + mode, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(credentials) });
      if (!data?.user) throw new ApiError("登录状态无法读取，请重新连接。");
      applySession(data); password.value = ""; confirm.value = "";
      showSignedInMessage(mode === "register" ? "账号已创建，你已登录。" : "登录成功。");
      $("#account-heading").focus({ preventScroll: true }); await loadPlans();
    } catch (error) { showError(error.message, true); }
    finally { authBusy = false; setBusy(); form.removeAttribute("aria-busy"); submit.replaceChildren(document.createTextNode(mode === "register" ? "创建账号 " : "登录 "), node("span", "", "↗")); }
  });
  $("#refresh-plans").addEventListener("click", () => { clearMessages(); loadPlans(); });
  $("#logout-button").addEventListener("click", async () => {
    if (!serviceReady || checking || logoutBusy || plansBusy || deletingId !== null || !user || !csrfToken) return;
    logoutBusy = true; setBusy(); clearMessages(); renderLibrary(); $("#logout-button").textContent = "正在退出…";
    try {
      await request("/api/auth/logout", { method: "POST", headers: { "X-CSRF-Token": csrfToken } });
      applySession({ user: null, csrf_token: null }); selectMode("login"); showMessage("已退出登录。"); username.focus();
    } catch (error) {
      if (error.status === 401) { applySession({ user: null, csrf_token: null }); selectMode("login"); showMessage("已退出登录。"); }
      else { showError(error.message, true); if (error.status === 403) { serviceReady = false; serviceMessage("需要重新确认登录状态", "重新连接后，再退出登录。", true); } }
    } finally { logoutBusy = false; $("#logout-button").textContent = "退出登录"; setBusy(); renderLibrary(); }
  });
  checkSession();
}());
