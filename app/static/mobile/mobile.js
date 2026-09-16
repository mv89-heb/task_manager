(() => {
  const $ = (id) => document.getElementById(id);
  const state = { status: "", search: "", sort: "due_date" };
  const statusLabels = { TODO: "לביצוע", IN_PROGRESS: "בטיפול", DONE: "בוצעה" };
  const priorityLabels = { CRITICAL: "קריטית", HIGH: "גבוהה", MEDIUM: "בינונית", LOW: "נמוכה" };
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

  function show(view) {
    $("login-view").classList.toggle("hidden", view !== "login");
    $("app-view").classList.toggle("hidden", view !== "app");
  }

  async function api(url, options = {}) {
    const response = await fetch(url, { credentials: "same-origin", ...options });
    if (response.status === 401) {
      show("login");
      throw new Error("AUTH");
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Request failed");
    return data;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;","\"":"&quot;"}[c]));
  }

  function formatDate(value) {
    if (!value) return "ללא תאריך יעד";
    return new Intl.DateTimeFormat("he-IL", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(`${value}T00:00:00`));
  }

  function renderTasks(tasks) {
    const list = $("task-list");
    list.innerHTML = "";
    $("empty").classList.toggle("hidden", tasks.length !== 0);
    for (const task of tasks) {
      const card = document.createElement("article");
      card.className = `task ${task.is_overdue ? "overdue" : ""}`;
      const nextStatus = task.status === "TODO" ? "IN_PROGRESS" : task.status === "IN_PROGRESS" ? "DONE" : "TODO";
      const actionLabel = nextStatus === "IN_PROGRESS" ? "התחל" : nextStatus === "DONE" ? "סמן בוצע" : "החזר לביצוע";
      const priorityClass = task.priority === "CRITICAL" || task.priority === "HIGH" ? "high" : task.priority === "MEDIUM" ? "medium" : "low";
      card.innerHTML = `
        <div class="task-head">
          <div class="task-title">${escapeHtml(task.title)}</div>
          <span class="badge ${priorityClass}">${escapeHtml(priorityLabels[task.priority] || task.priority)}</span>
        </div>
        ${task.description ? `<div class="task-description">${escapeHtml(task.description)}</div>` : ""}
        <div class="task-meta">
          <span>${escapeHtml(statusLabels[task.status] || task.status)}</span>
          <span>•</span><span>יעד: ${escapeHtml(formatDate(task.due_date))}</span>
          ${task.assignee ? `<span>•</span><span>${escapeHtml(task.assignee)}</span>` : ""}
          ${task.department ? `<span>•</span><span>${escapeHtml(task.department)}</span>` : ""}
        </div>
        ${task.can_edit ? `<div class="task-actions"><button data-task-id="${task.id}" data-next-status="${nextStatus}" class="${nextStatus === "DONE" ? "done" : ""}">${actionLabel}</button></div>` : ""}
      `;
      list.appendChild(card);
    }
  }

  async function loadTasks() {
    $("loading").classList.remove("hidden");
    try {
      const params = new URLSearchParams({ sort: state.sort, limit: "200" });
      if (state.status && state.status !== "OVERDUE") params.set("status", state.status);
      if (state.search) params.set("search", state.search);
      const data = await api(`/api/mobile/tasks?${params}`);
      let tasks = data.tasks;
      if (state.status === "OVERDUE") tasks = tasks.filter((task) => task.is_overdue);
      renderTasks(tasks);
      $("count-todo").textContent = data.counts.todo;
      $("count-progress").textContent = data.counts.in_progress;
      $("count-done").textContent = data.counts.done;
      $("count-overdue").textContent = data.counts.overdue;
    } finally {
      $("loading").classList.add("hidden");
    }
  }

  async function loadSession() {
    try {
      const data = await api("/api/mobile/me");
      if (!data.authenticated) return show("login");
      $("user-label").textContent = `${data.user.username} · ${data.user.role_label}${data.user.department ? ` · ${data.user.department}` : ""}`;
      $("must-change").classList.toggle("hidden", !data.user.must_change_password);
      show("app");
      await loadTasks();
    } catch (error) {
      if (error.message !== "AUTH") console.error(error);
    }
  }

  $("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    $("login-error").textContent = "";
    const body = new URLSearchParams({ username: $("username").value.trim(), password: $("password").value, remember_me: $("remember").checked ? "1" : "0" });
    try {
      const response = await fetch("/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": csrfToken },
        body,
      });
      if (!response.ok) throw new Error("login");
      window.location.reload();
    } catch {
      $("login-error").textContent = "שם משתמש או סיסמה לא נכונים.";
    }
  });

  $("logout").addEventListener("click", async () => {
    await fetch("/logout", { credentials: "same-origin" });
    show("login");
  });

  document.querySelectorAll(".stats button").forEach((button) => {
    button.addEventListener("click", () => {
      state.status = state.status === button.dataset.status ? "" : button.dataset.status;
      loadTasks();
    });
  });

  $("search").addEventListener("input", (event) => {
    clearTimeout(window.__taskSearchTimer);
    state.search = event.target.value.trim();
    window.__taskSearchTimer = setTimeout(loadTasks, 250);
  });

  $("sort").addEventListener("change", (event) => {
    state.sort = event.target.value;
    loadTasks();
  });

  $("task-list").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-task-id]");
    if (!button) return;
    button.disabled = true;
    try {
      await api(`/api/mobile/tasks/${button.dataset.taskId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: button.dataset.nextStatus }),
      });
      await loadTasks();
    } catch (error) {
      if (error.message !== "AUTH") alert("לא ניתן לעדכן את המשימה.");
    } finally {
      button.disabled = false;
    }
  });

  loadSession();
})();
