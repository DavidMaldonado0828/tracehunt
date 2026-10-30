"use strict";

// El estado compartido vive en un solo objeto para que cambiar de sesión limpie
// de forma atómica identidad, cachés, vistas y temporizadores.
const appState = {
  token: null,
  user: null,
  users: [],
  usersById: new Map(),
  usersLoaded: false,
  alerts: [],
  alertCursor: null,
  selectedAlertId: null,
  selectedAlert: null,
  selectedHistory: [],
  activeTab: "alerts-view",
  defaultStatus: "",
  alertTimer: null,
  noticeTimer: null,
  requestCount: 0,
  buttonsBeforeRequest: new Map(),
  sessionVersion: 0,
  alertLoadInProgress: false,
  dom: {},
};

const TOKEN_KEY = "tracehunt_access_token";

function reportVisibleError(message) {
  const text = message || "Ocurrió un error inesperado.";
  const globalTarget = document.getElementById("global-notice");
  const loginTarget = document.getElementById("login-notice");
  const appPanel = document.getElementById("app-panel");
  const appIsVisible = appPanel?.hidden === false;
  const target = appIsVisible ? globalTarget : (loginTarget || globalTarget);
  if (target) {
    // Si la inicialización falla antes de resetSession(), mostramos el login para
    // que el aviso no quede atrapado dentro de una sección oculta.
    if (!appIsVisible) {
      const loginPanel = document.getElementById("login-panel");
      if (loginPanel) loginPanel.hidden = false;
      if (appPanel) appPanel.hidden = true;
    }
    target.textContent = text;
    target.className = "notice error";
    target.hidden = false;
    return;
  }
  const fallback = document.createElement("div");
  fallback.className = "notice error runtime-notice";
  fallback.setAttribute("role", "alert");
  fallback.textContent = text;
  document.body.append(fallback);
}

function requiredElement(id) {
  const element = document.getElementById(id);
  if (!element) {
    const error = new Error(`No se encontró el elemento requerido: ${id}`);
    reportVisibleError(error.message);
    throw error;
  }
  return element;
}

function cacheDom() {
  const ids = [
    "login-panel", "login-form", "login-notice", "email", "password", "app-panel",
    "global-notice", "main-tabs", "account-name", "account-email", "account-role",
    "logout-button", "users-tab", "alerts-view", "simulator-view", "users-view",
    "alert-filters", "status-filter", "severity-filter", "clear-alert-filters",
    "alert-scope", "alert-rows", "alert-count", "alert-detail", "load-more",
    "refresh-alerts", "alerts-updated-at", "users-notice", "user-rows",
    "create-user-form", "refresh-users", "simulation-form", "simulation-result",
    "period-start", "period-end",
  ];
  ids.forEach((id) => { appState.dom[id] = requiredElement(id); });
  appState.dom.tabs = [...document.querySelectorAll(".tab")];
  appState.dom.views = [...document.querySelectorAll(".view")];
  // Esta columna solo aporta contexto adicional al administrador; si un HTML
  // servido desde una imagen anterior aún no la incluye, no debe impedir el login.
  appState.dom.ownerHeading = document.getElementById("alert-owner-heading");
  appState.dom.updatedAt = requiredElement("alerts-updated-at");
}

function el(id) {
  const element = appState.dom[id];
  if (!element) throw new Error(`No se encontró el elemento requerido: ${id}`);
  return element;
}

function setNotice(target, message, type = "error") {
  target.textContent = message;
  target.className = `notice ${type}`;
  target.hidden = !message;
}

function clearNotice(target) {
  target.textContent = "";
  target.hidden = true;
}

function clearTemporaryNotice() {
  if (appState.noticeTimer !== null) {
    window.clearTimeout(appState.noticeTimer);
    appState.noticeTimer = null;
  }
}

function showTemporaryNotice(message, type = "success") {
  clearTemporaryNotice();
  setNotice(el("global-notice"), message, type);
  appState.noticeTimer = window.setTimeout(() => {
    clearNotice(el("global-notice"));
    appState.noticeTimer = null;
  }, 5000);
}

function setBusy(started) {
  appState.requestCount += started ? 1 : -1;
  appState.requestCount = Math.max(0, appState.requestCount);
  if (appState.requestCount > 0 && appState.buttonsBeforeRequest.size === 0) {
    document.querySelectorAll("button").forEach((button) => {
      appState.buttonsBeforeRequest.set(button, button.disabled);
      button.disabled = true;
    });
  } else if (appState.requestCount === 0 && appState.buttonsBeforeRequest.size > 0) {
    appState.buttonsBeforeRequest.forEach((wasDisabled, button) => {
      if (button.isConnected) button.disabled = wasDisabled;
    });
    appState.buttonsBeforeRequest.clear();
  }
}

function parseApiError(payload, statusCode) {
  const detail = payload?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (typeof item === "string") return item;
      return item?.msg || item?.message || JSON.stringify(item);
    }).join(" · ");
  }
  if (typeof detail === "string") return detail;
  return `La solicitud falló (${statusCode}).`;
}

async function apiRequest(path, options = {}) {
  const requestVersion = appState.sessionVersion;
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (appState.token) headers.set("Authorization", `Bearer ${appState.token}`);
  if (options.body !== undefined) headers.set("Content-Type", "application/json");

  setBusy(true);
  try {
    const response = await fetch(path, { ...options, headers });
    const raw = await response.text();
    let payload = null;
    if (raw) {
      try { payload = JSON.parse(raw); } catch { payload = null; }
    }
    if (response.status === 401 && path !== "/auth/login") {
      resetSession("La sesión venció o dejó de ser válida. Inicia sesión otra vez.");
      throw new Error("La sesión venció o dejó de ser válida.");
    }
    if (requestVersion !== appState.sessionVersion && path !== "/auth/login") {
      throw new Error("La sesión cambió durante la solicitud.");
    }
    if (!response.ok) throw new Error(parseApiError(payload, response.status));
    return payload;
  } catch (error) {
    if (error instanceof TypeError) throw new Error("No se pudo conectar con la API.");
    throw error;
  } finally {
    setBusy(false);
  }
}

const Api = {
  get(path) { return apiRequest(path); },
  post(path, body, headers = {}) {
    return apiRequest(path, { method: "POST", headers, body: JSON.stringify(body) });
  },
  patch(path, body) {
    return apiRequest(path, { method: "PATCH", body: JSON.stringify(body) });
  },
};

function emptyRow(target, columns, message) {
  target.replaceChildren();
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.className = "empty-cell";
  cell.colSpan = columns;
  cell.textContent = message;
  row.append(cell);
  target.append(row);
}

function renderEmptyDetail(message = "Selecciona una alerta") {
  const panel = el("alert-detail");
  panel.replaceChildren();
  const empty = document.createElement("div");
  empty.className = "empty-state";
  const icon = document.createElement("span");
  icon.className = "empty-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "⌕";
  const title = document.createElement("h2");
  title.textContent = message;
  const copy = document.createElement("p");
  copy.className = "muted";
  copy.textContent = "El detalle y el historial aparecerán aquí.";
  empty.append(icon, title, copy);
  panel.append(empty);
}

function renderEmptySimulation(message = "Aún no has ejecutado ninguna simulación.") {
  const panel = el("simulation-result");
  panel.replaceChildren();
  const empty = document.createElement("div");
  empty.className = "empty-state";
  const title = document.createElement("h2");
  title.textContent = "Resultado";
  const copy = document.createElement("p");
  copy.className = "muted";
  copy.textContent = message;
  empty.append(title, copy);
  panel.append(empty);
}

function stopTimers() {
  if (appState.alertTimer !== null) {
    window.clearInterval(appState.alertTimer);
    appState.alertTimer = null;
  }
  clearTemporaryNotice();
}

function resetSession(message = "") {
  appState.sessionVersion += 1;
  stopTimers();
  appState.token = null;
  appState.user = null;
  appState.users = [];
  appState.usersById.clear();
  appState.usersLoaded = false;
  appState.alerts = [];
  appState.alertCursor = null;
  appState.selectedAlertId = null;
  appState.selectedAlert = null;
  appState.selectedHistory = [];
  appState.activeTab = "alerts-view";
  appState.defaultStatus = "";
  sessionStorage.removeItem(TOKEN_KEY);

  if (appState.dom["login-form"]) el("login-form").reset();
  if (appState.dom["alert-filters"]) el("alert-filters").reset();
  if (appState.dom["create-user-form"]) el("create-user-form").reset();
  if (appState.dom["simulation-form"]) el("simulation-form").reset();
  if (appState.dom["alert-rows"]) emptyRow(el("alert-rows"), 6, "Inicia sesión para cargar alertas.");
  if (appState.dom["user-rows"]) emptyRow(el("user-rows"), 7, "Inicia sesión como administrador para ver usuarios.");
  if (appState.dom["alert-detail"]) renderEmptyDetail();
  if (appState.dom["simulation-result"]) renderEmptySimulation();
  if (appState.dom["alert-count"]) el("alert-count").textContent = "";
  if (appState.dom["alert-scope"]) el("alert-scope").textContent = "";
  if (appState.dom.updatedAt) el("alerts-updated-at").textContent = "";
  if (appState.dom["global-notice"]) clearNotice(el("global-notice"));
  if (appState.dom["users-notice"]) clearNotice(el("users-notice"));
  if (appState.dom["login-notice"]) clearNotice(el("login-notice"));
  if (appState.dom["load-more"]) el("load-more").hidden = true;
  if (appState.dom["clear-alert-filters"]) el("clear-alert-filters").disabled = true;
  if (appState.dom.ownerHeading) appState.dom.ownerHeading.hidden = true;

  appState.dom.views?.forEach((view) => { view.hidden = true; });
  appState.dom.tabs?.forEach((tab) => {
    tab.hidden = true;
    tab.classList.remove("active");
    tab.setAttribute("aria-selected", "false");
  });
  if (appState.dom["users-tab"]) el("users-tab").hidden = true;
  if (appState.dom["main-tabs"]) el("main-tabs").hidden = true;
  if (appState.dom["app-panel"]) el("app-panel").hidden = true;
  if (appState.dom["login-panel"]) el("login-panel").hidden = false;
  if (appState.dom["account-name"]) el("account-name").textContent = "—";
  if (appState.dom["account-email"]) el("account-email").textContent = "";
  if (appState.dom["account-role"]) el("account-role").textContent = "";
  if (message && appState.dom["login-notice"]) setNotice(el("login-notice"), message);
}

function readableStatus(value) {
  return ({ open: "Abierta", investigating: "En investigación", resolved: "Resuelta" })[value] || value || "—";
}

function readableSeverity(value) {
  return ({ high: "Alta", medium: "Media", low: "Baja" })[value] || value || "—";
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
}

function personLabel(userId) {
  if (typeof userId !== "string" || userId.length === 0) return "Sin asignar";
  if (appState.user && userId === appState.user.user_id) return "Tú";
  if (appState.user?.role === "admin") {
    const user = appState.usersById.get(userId);
    if (user?.display_name) return user.display_name;
  }
  return userId;
}

function configureAlertColumns() {
  if (appState.dom.ownerHeading) {
    appState.dom.ownerHeading.hidden = appState.user?.role !== "admin";
  }
}

function addCell(row, value, className = "") {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = value === null || value === undefined || value === "" ? "—" : String(value);
  row.append(cell);
  return cell;
}

function renderAlertRows(alerts, append = false) {
  configureAlertColumns();
  if (!append) el("alert-rows").replaceChildren();
  if (alerts.length === 0 && !append) {
    emptyRow(el("alert-rows"), appState.user?.role === "admin" ? 7 : 6, "No hay alertas para estos filtros.");
    return;
  }
  alerts.forEach((alert) => {
    const row = document.createElement("tr");
    row.dataset.alertId = alert.alert_id;
    row.tabIndex = 0;
    row.setAttribute("aria-label", `Abrir alerta ${alert.title}`);
    if (alert.alert_id === appState.selectedAlertId) row.classList.add("selected");

    const severityCell = document.createElement("td");
    const severity = document.createElement("span");
    severity.className = `badge severity-${alert.severity}`;
    severity.textContent = readableSeverity(alert.severity);
    severityCell.append(severity);
    row.append(severityCell);
    addCell(row, alert.title);
    addCell(row, alert.rule_id);
    const statusCell = document.createElement("td");
    const status = document.createElement("span");
    status.className = `badge status-${alert.status}`;
    status.textContent = readableStatus(alert.status);
    statusCell.append(status);
    row.append(statusCell);
    addCell(row, personLabel(alert.assigned_to));
    if (appState.user?.role === "admin") addCell(row, personLabel(alert.owner_user_id));
    addCell(row, formatDate(alert.created_at));
    row.addEventListener("click", () => AlertController.select(alert.alert_id));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        AlertController.select(alert.alert_id);
      }
    });
    el("alert-rows").append(row);
  });
}

function syncFilterControls() {
  const status = el("status-filter").value;
  const severity = el("severity-filter").value;
  el("clear-alert-filters").disabled = status === appState.defaultStatus && severity === "";
}

function describeAlertScope() {
  if (appState.user?.role === "analyst") return "Mostrando tus alertas";
  const status = el("status-filter").value;
  const severity = el("severity-filter").value;
  if (status === "open" && severity === "") return "Mostrando alertas abiertas de todos los usuarios";
  if (status) return `Mostrando alertas ${readableStatus(status).toLowerCase()} de todos los usuarios`;
  return "Mostrando alertas de todos los usuarios";
}

function updateRefreshedTime() {
  const time = new Date().toLocaleTimeString("es-CO", { hour12: false });
  el("alerts-updated-at").textContent = `Actualizado a las ${time}`;
}

function buildAlertQuery(append) {
  const query = new URLSearchParams();
  const status = el("status-filter").value;
  const severity = el("severity-filter").value;
  if (status) query.set("status", status);
  if (severity) query.set("severity", severity);
  query.set("limit", "25");
  if (append && appState.alertCursor) query.set("cursor", appState.alertCursor);
  return query.toString();
}

const AlertController = {
  async load({ append = false, quiet = false } = {}) {
    if (!appState.user || appState.alertLoadInProgress) return;
    appState.alertLoadInProgress = true;
    const selectedId = appState.selectedAlertId;
    if (!quiet) clearNotice(el("global-notice"));
    syncFilterControls();
    try {
      const result = await Api.get(`/alerts?${buildAlertQuery(append)}`);
      appState.alertCursor = result.next_cursor || null;
      if (append) appState.alerts = appState.alerts.concat(result.items || []);
      else appState.alerts = result.items || [];
      renderAlertRows(appState.alerts, false);
      el("alert-scope").textContent = describeAlertScope();
      el("alert-count").textContent = `${appState.alerts.length} ${appState.alerts.length === 1 ? "alerta" : "alertas"} cargada${appState.alerts.length === 1 ? "" : "s"}`;
      el("load-more").hidden = !appState.alertCursor;
      updateRefreshedTime();
      // Las actualizaciones en segundo plano conservan el panel y vuelven a leer su historial.
      if (selectedId && appState.selectedAlertId === selectedId) {
        await this.loadDetail(selectedId, { quiet: true });
      }
    } catch (error) {
      if (appState.user) setNotice(el("global-notice"), error.message);
    } finally {
      appState.alertLoadInProgress = false;
    }
  },

  async select(alertId) {
    appState.selectedAlertId = alertId;
    el("alert-rows").querySelectorAll("tr[data-alert-id]").forEach((row) => {
      row.classList.toggle("selected", row.dataset.alertId === alertId);
    });
    clearNotice(el("global-notice"));
    await this.loadDetail(alertId);
  },

  async loadDetail(alertId, { quiet = false } = {}) {
    const version = appState.sessionVersion;
    try {
      const [alert, historyPage] = await Promise.all([
        Api.get(`/alerts/${encodeURIComponent(alertId)}`),
        Api.get(`/alerts/${encodeURIComponent(alertId)}/history?limit=100`),
      ]);
      if (version !== appState.sessionVersion || appState.selectedAlertId !== alertId) return;
      appState.selectedAlert = alert;
      appState.selectedHistory = historyPage.items || [];
      this.renderDetail(alert, appState.selectedHistory);
    } catch (error) {
      if (!quiet && appState.user) setNotice(el("global-notice"), error.message);
    }
  },

  closeDetail() {
    appState.selectedAlertId = null;
    appState.selectedAlert = null;
    appState.selectedHistory = [];
    el("alert-rows").querySelectorAll("tr.selected").forEach((row) => row.classList.remove("selected"));
    renderEmptyDetail();
  },

  async changeStatus(alertId, nextStatus, comment) {
    const alert = appState.selectedAlert;
    if (!alert) return;
    const oldLabel = readableStatus(alert.status);
    const nextLabel = readableStatus(nextStatus);
    if (!window.confirm(`¿Cambiar la alerta de "${oldLabel}" a "${nextLabel}"? Los cambios no se pueden revertir.`)) return;
    clearNotice(el("global-notice"));
    try {
      const updated = await Api.patch(`/alerts/${encodeURIComponent(alertId)}/status`, {
        status: nextStatus,
        comment: comment.trim() || null,
      });
      this.closeDetail();
      await this.load();
      showTemporaryNotice(`Alerta "${updated.title}": ahora está ${readableStatus(updated.status).toLowerCase()}.`);
    } catch (error) {
      if (appState.user) setNotice(el("global-notice"), error.message);
    }
  },

  async reassign(alertId, userId) {
    const selectedUser = appState.usersById.get(userId);
    const displayName = selectedUser?.display_name || userId;
    if (!window.confirm(`¿Reasignar esta alerta a ${displayName}?`)) return;
    clearNotice(el("global-notice"));
    try {
      const updated = await Api.patch(`/alerts/${encodeURIComponent(alertId)}/assignment`, { assigned_to: userId });
      this.closeDetail();
      await this.load();
      showTemporaryNotice(`Alerta "${updated.title}": asignada a ${displayName}.`);
    } catch (error) {
      if (appState.user) setNotice(el("global-notice"), error.message);
    }
  },

  renderDetail(alert, history) {
    const panel = el("alert-detail");
    panel.replaceChildren();
    const heading = document.createElement("div");
    heading.className = "detail-title";
    const titleBlock = document.createElement("div");
    const title = document.createElement("h2");
    title.textContent = alert.title;
    const id = document.createElement("p");
    id.className = "muted small-text";
    id.textContent = alert.alert_id;
    titleBlock.append(title, id);
    const severity = document.createElement("span");
    severity.className = `badge severity-${alert.severity}`;
    severity.textContent = readableSeverity(alert.severity);
    heading.append(titleBlock, severity);
    panel.append(heading);

    const description = document.createElement("p");
    description.className = "detail-copy";
    description.textContent = alert.description || "Sin descripción.";
    panel.append(description);
    const meta = document.createElement("div");
    meta.className = "detail-meta";
    const fields = [
      ["Regla", alert.rule_id], ["Estado", readableStatus(alert.status)],
      ["Asignada a", personLabel(alert.assigned_to)],
      ...(appState.user?.role === "admin" ? [["Dueño", personLabel(alert.owner_user_id)]] : []),
      ["Creada", formatDate(alert.created_at)], ["Primer evento", formatDate(alert.first_event_at)],
      ["Último evento", formatDate(alert.last_event_at)], ["Actualizada", formatDate(alert.updated_at)],
      ["Simulación", alert.simulation_id],
    ];
    fields.forEach(([label, value]) => {
      const item = document.createElement("div");
      item.className = "meta-item";
      const caption = document.createElement("span");
      caption.textContent = label;
      const content = document.createElement("strong");
      content.textContent = value || "—";
      item.append(caption, content);
      meta.append(item);
    });
    panel.append(meta);

    const eventSection = this.addSection(panel, `Eventos relacionados (${(alert.related_event_ids || []).length})`);
    const eventList = document.createElement("ul");
    eventList.className = "event-list";
    (alert.related_event_ids || []).forEach((eventId) => {
      const item = document.createElement("li");
      item.textContent = eventId;
      eventList.append(item);
    });
    if (eventList.childElementCount) eventSection.append(eventList);
    else {
      const none = document.createElement("p");
      none.className = "muted small-text";
      none.textContent = "No hay eventos relacionados.";
      eventSection.append(none);
    }

    const actionSection = this.addSection(panel, "Acciones");
    const stateNotice = document.createElement("p");
    stateNotice.className = "state-legend muted small-text";
    stateNotice.textContent = "Los cambios de estado no se pueden revertir.";
    actionSection.append(stateNotice);
    const transitions = {
      open: [["investigating", "Pasar a investigación"]],
      investigating: [["resolved", "Marcar como resuelta"]],
      resolved: [],
    };
    const options = transitions[alert.status] || [];
    if (alert.status === "resolved") {
      const finalState = document.createElement("p");
      finalState.className = "final-state";
      finalState.textContent = "Alerta resuelta: estado final.";
      actionSection.append(finalState);
    }
    if (options.length > 0) {
      const comment = document.createElement("textarea");
      comment.className = "comment-box";
      comment.maxLength = 500;
      comment.placeholder = "Comentario opcional para el historial";
      comment.setAttribute("aria-label", "Comentario opcional");
      actionSection.append(comment);
      const actionRow = document.createElement("div");
      actionRow.className = "action-row";
      options.forEach(([nextStatus, label]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "button secondary";
        button.textContent = label;
        button.addEventListener("click", () => this.changeStatus(alert.alert_id, nextStatus, comment.value));
        actionRow.append(button);
      });
      actionSection.append(actionRow);
    }
    if (appState.user?.role === "admin") this.renderAssignmentControls(actionSection, alert);

    const historySection = this.addSection(panel, `Historial (${history.length})`);
    const entries = document.createElement("div");
    entries.className = "history-list";
    history.forEach((record) => {
      const entry = document.createElement("div");
      entry.className = "history-entry";
      const action = document.createElement("strong");
      action.textContent = record.action || "Cambio";
      const actor = document.createElement("span");
      actor.textContent = `${record.actor_email || record.actor_id} · ${formatDate(record.changed_at)}`;
      entry.append(action, actor);
      if (record.previous_status || record.new_status) {
        const change = document.createElement("span");
        change.textContent = `${record.previous_status || "—"} → ${record.new_status || "—"}`;
        entry.append(change);
      }
      if (record.comment) {
        const comment = document.createElement("span");
        comment.textContent = record.comment;
        entry.append(comment);
      }
      entries.append(entry);
    });
    if (history.length === 0) {
      const none = document.createElement("p");
      none.className = "muted small-text";
      none.textContent = "Todavía no hay cambios registrados.";
      entries.append(none);
    }
    historySection.append(entries);
  },

  addSection(parent, text) {
    const section = document.createElement("section");
    section.className = "detail-section";
    const heading = document.createElement("h3");
    heading.textContent = text;
    section.append(heading);
    parent.append(section);
    return section;
  },

  renderAssignmentControls(parent, alert) {
    const controls = document.createElement("div");
    controls.className = "assignment-controls";
    const label = document.createElement("label");
    label.textContent = "Reasignar a";
    const select = document.createElement("select");
    select.setAttribute("aria-label", "Usuario activo para asignar la alerta");
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Selecciona un usuario activo";
    select.append(placeholder);
    appState.users.filter((user) => user.status === "active").forEach((user) => {
      const option = document.createElement("option");
      option.value = user.user_id;
      option.textContent = user.display_name;
      option.selected = user.user_id === alert.assigned_to;
      select.append(option);
    });
    label.append(select);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button secondary";
    button.textContent = "Reasignar";
    button.disabled = appState.users.length === 0;
    button.addEventListener("click", () => {
      if (select.value) this.reassign(alert.alert_id, select.value);
    });
    controls.append(label, button);
    parent.append(controls);
  },
};

function refreshTimer() {
  if (appState.alertTimer !== null) {
    window.clearInterval(appState.alertTimer);
    appState.alertTimer = null;
  }
  if (appState.user && appState.activeTab === "alerts-view" && document.visibilityState === "visible") {
    appState.alertTimer = window.setInterval(() => AlertController.load({ quiet: true }), 15000);
  }
}

function configureRoleDefaults() {
  const isAdmin = appState.user?.role === "admin";
  appState.defaultStatus = isAdmin ? "open" : "";
  const openOption = el("status-filter").querySelector('option[value="open"]');
  if (openOption) openOption.textContent = isAdmin ? "Abiertas (por defecto)" : "Abiertas";
  el("status-filter").value = appState.defaultStatus;
  el("severity-filter").value = "";
  syncFilterControls();
}

function setUtcDefaults() {
  const now = new Date();
  const dayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  el("period-end").value = now.toISOString().slice(0, 16);
  el("period-start").value = dayAgo.toISOString().slice(0, 16);
}

async function loadCurrentUser() {
  const user = await Api.get("/auth/me");
  if (!user || !["admin", "analyst"].includes(user.role) || !user.user_id) {
    resetSession("No se pudo verificar la cuenta activa.");
    return;
  }
  appState.user = user;
  el("account-name").textContent = user.display_name || user.email;
  el("account-email").textContent = user.email;
  el("account-role").textContent = user.role === "admin" ? "Administrador · admin" : "Analista · analyst";

  el("main-tabs").hidden = false;
  appState.dom.tabs.forEach((tab) => { tab.hidden = false; });
  el("users-tab").hidden = user.role !== "admin";
  el("app-panel").hidden = false;
  el("login-panel").hidden = true;
  appState.dom.views.forEach((view) => { view.hidden = view.id !== "alerts-view"; });
  appState.dom.tabs.forEach((tab) => {
    const active = tab.dataset.tab === "alerts-view";
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  appState.activeTab = "alerts-view";
  configureRoleDefaults();
  setUtcDefaults();
  renderEmptySimulation();
  clearNotice(el("global-notice"));
  clearNotice(el("users-notice"));

  await AlertController.load();
  // El admin necesita el directorio para mostrar nombres; se carga una vez y no en cada refresco.
  if (user.role === "admin") await UserController.load({ force: false, quiet: true });
  refreshTimer();
}

async function switchTab(targetId) {
  // El rol se valida aquí también, no solo al ocultar el botón del menú.
  if (targetId === "users-view") {
    if (appState.user?.role !== "admin") {
      appState.dom.views.forEach((view) => { view.hidden = view.id !== "alerts-view"; });
      setNotice(el("global-notice"), "Solo un administrador puede acceder a Usuarios.");
      targetId = "alerts-view";
    } else {
      try {
        const verifiedUser = await Api.get("/auth/me");
        if (verifiedUser.user_id !== appState.user.user_id || verifiedUser.role !== "admin") {
          resetSession("La cuenta ya no tiene permisos de administrador.");
          return;
        }
        appState.user = verifiedUser;
      } catch (error) {
        if (appState.user) setNotice(el("global-notice"), error.message);
        return;
      }
    }
  }

  if (!appState.user) return;
  if (appState.activeTab === "alerts-view" && targetId !== "alerts-view") AlertController.closeDetail();
  appState.activeTab = targetId;
  appState.dom.tabs.forEach((tab) => {
    const active = tab.dataset.tab === targetId;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  appState.dom.views.forEach((view) => { view.hidden = view.id !== targetId; });
  refreshTimer();

  if (targetId === "alerts-view") await AlertController.load();
  if (targetId === "users-view") await UserController.load({ force: false });
}

const UserController = {
  async load({ force = false, quiet = false } = {}) {
    if (appState.user?.role !== "admin") return;
    if (appState.usersLoaded && !force) {
      if (appState.activeTab === "users-view") this.render();
      return;
    }
    if (!quiet) clearNotice(el("users-notice"));
    try {
      appState.users = await Api.get("/users");
      appState.usersById = new Map(appState.users.map((user) => [user.user_id, user]));
      appState.usersLoaded = true;
      if (appState.activeTab === "users-view") this.render();
      renderAlertRows(appState.alerts);
      if (appState.selectedAlertId && appState.activeTab === "alerts-view") {
        await AlertController.loadDetail(appState.selectedAlertId, { quiet: true });
      }
    } catch (error) {
      if (appState.user?.role === "admin") setNotice(quiet ? el("global-notice") : el("users-notice"), error.message);
    }
  },

  render() {
    if (appState.user?.role !== "admin") {
      emptyRow(el("user-rows"), 7, "No tienes permisos para ver usuarios.");
      return;
    }
    const rows = el("user-rows");
    rows.replaceChildren();
    if (!appState.users.length) {
      emptyRow(rows, 7, "No hay usuarios.");
      return;
    }
    appState.users.forEach((user) => {
      const row = document.createElement("tr");
      addCell(row, user.display_name);
      addCell(row, user.email);
      const roleCell = document.createElement("td");
      const roleSelect = document.createElement("select");
      roleSelect.setAttribute("aria-label", `Rol de ${user.email}`);
      [["analyst", "Analista"], ["admin", "Administrador"]].forEach(([value, label]) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        option.selected = user.role === value;
        roleSelect.append(option);
      });
      const ownAccount = user.user_id === appState.user.user_id;
      roleSelect.disabled = ownAccount;
      roleCell.append(roleSelect);
      row.append(roleCell);
      addCell(row, user.status === "active" ? "Activo" : "Deshabilitado");
      addCell(row, formatDate(user.created_at));
      addCell(row, formatDate(user.last_login_at));
      const actionsCell = document.createElement("td");
      const actions = document.createElement("div");
      actions.className = "user-row-actions";
      const roleButton = document.createElement("button");
      roleButton.type = "button";
      roleButton.className = "button secondary";
      roleButton.textContent = "Cambiar rol";
      roleButton.disabled = ownAccount;
      roleButton.addEventListener("click", () => this.update(user, "role", { role: roleSelect.value }));
      const statusButton = document.createElement("button");
      statusButton.type = "button";
      statusButton.className = user.status === "active" ? "button danger" : "button secondary";
      statusButton.textContent = user.status === "active" ? "Desactivar" : "Activar";
      statusButton.disabled = ownAccount;
      statusButton.addEventListener("click", () => this.update(user, "status", {
        status: user.status === "active" ? "disabled" : "active",
      }));
      actions.append(roleButton, statusButton);
      actionsCell.append(actions);
      row.append(actionsCell);
      rows.append(row);
    });
  },

  async update(user, action, body) {
    const description = action === "role"
      ? `¿Cambiar el rol de ${user.display_name} a ${body.role === "admin" ? "administrador" : "analista"}?`
      : `¿${body.status === "disabled" ? "Desactivar" : "Activar"} la cuenta de ${user.display_name}?`;
    if (!window.confirm(description)) return;
    clearNotice(el("users-notice"));
    try {
      await Api.patch(`/users/${encodeURIComponent(user.email)}/${action}`, body);
      await this.load({ force: true, quiet: true });
      setNotice(el("users-notice"), "Usuario actualizado.", "success");
    } catch (error) {
      if (appState.user?.role === "admin") setNotice(el("users-notice"), error.message);
    }
  },

  async create(event) {
    event.preventDefault();
    clearNotice(el("users-notice"));
    // currentTarget solo es fiable mientras se despacha el evento; se conserva
    // el formulario antes del await para poder limpiarlo tras el 201.
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const body = {
      email: form.get("email"),
      display_name: form.get("display_name"),
      password: form.get("password"),
      role: form.get("role"),
    };
    try {
      const createdUser = await Api.post("/users", body);
      formElement.reset();
      // El POST ya devuelve el usuario persistido; actualizar la tabla con esa
      // respuesta evita una segunda lectura que podría fallar o llegar tarde.
      appState.users = [
        ...appState.users.filter((user) => user.user_id !== createdUser.user_id),
        createdUser,
      ];
      appState.usersById.set(createdUser.user_id, createdUser);
      this.render();
      renderAlertRows(appState.alerts);
      setNotice(el("users-notice"), "Usuario creado.", "success");
    } catch (error) {
      // El formulario solo se limpia tras confirmar el 201; si falla conserva lo escrito.
      if (appState.user?.role === "admin") setNotice(el("users-notice"), error.message);
    }
  },
};

function dateTimeLocalToUtc(value) {
  // datetime-local no trae zona; la etiqueta UTC permite interpretarlo sin usar la zona local del navegador.
  return new Date(`${value}:00Z`).toISOString();
}

function metric(label, value) {
  const box = document.createElement("div");
  box.className = "metric";
  const caption = document.createElement("span");
  caption.textContent = label;
  const number = document.createElement("strong");
  number.textContent = value === null || value === undefined ? "—" : String(value);
  box.append(caption, number);
  return box;
}

function renderSimulation(result) {
  const panel = el("simulation-result");
  panel.replaceChildren();
  const heading = document.createElement("div");
  heading.className = "result-heading";
  const title = document.createElement("h2");
  title.textContent = "Resultado de simulación";
  const status = document.createElement("span");
  status.className = `badge status-${result.status}`;
  status.textContent = result.status || "Sin estado";
  heading.append(title, status);
  panel.append(heading);
  const metrics = document.createElement("div");
  metrics.className = "result-grid";
  metrics.append(
    metric("Eventos solicitados", result.requested_event_count),
    metric("Eventos generados", result.generated_event_count),
    metric("Eventos procesados", result.processed_event_count),
    metric("Alertas creadas", result.created_alert_count),
  );
  panel.append(metrics);
  const errorHeading = document.createElement("h3");
  errorHeading.textContent = "Resumen de errores";
  const errorSummary = document.createElement("p");
  errorSummary.className = result.error_summary ? "error-summary" : "muted small-text";
  errorSummary.textContent = result.error_summary || "Sin errores reportados.";
  panel.append(errorHeading, errorSummary);
  const actions = document.createElement("div");
  actions.className = "action-row";
  const viewAlerts = document.createElement("button");
  viewAlerts.type = "button";
  viewAlerts.className = "button primary";
  viewAlerts.textContent = "Ver alertas";
  viewAlerts.addEventListener("click", () => switchTab("alerts-view"));
  actions.append(viewAlerts);
  panel.append(actions);
}

const SimulationController = {
  async run(event) {
    event.preventDefault();
    clearNotice(el("global-notice"));
    renderEmptySimulation("Ejecutando simulación…");
    const form = new FormData(event.currentTarget);
    let body;
    try {
      body = {
        requested_event_count: Number(form.get("requested_event_count")),
        period_start: dateTimeLocalToUtc(String(form.get("period_start"))),
        period_end: dateTimeLocalToUtc(String(form.get("period_end"))),
        seed: form.get("seed") === "" ? null : Number(form.get("seed")),
      };
      if (!Number.isInteger(body.requested_event_count) || body.requested_event_count < 30 || body.requested_event_count > 300) {
        throw new Error("La cantidad de eventos debe estar entre 30 y 300.");
      }
      if (body.seed !== null && !Number.isInteger(body.seed)) throw new Error("La seed debe ser un número entero.");
      if (new Date(body.period_start) >= new Date(body.period_end)) throw new Error("El inicio debe ser anterior al fin.");
      if (new Date(body.period_end) - new Date(body.period_start) > 30 * 24 * 60 * 60 * 1000) {
        throw new Error("El periodo no puede superar 30 días.");
      }
    } catch (error) {
      renderEmptySimulation();
      setNotice(el("global-notice"), error.message || "Revisa las fechas del periodo.");
      return;
    }
    try {
      const result = await Api.post("/simulations", body, { "Idempotency-Key": crypto.randomUUID() });
      renderSimulation(result);
      await AlertController.load({ quiet: true });
    } catch (error) {
      if (appState.user) setNotice(el("global-notice"), error.message);
      renderEmptySimulation("La simulación no pudo completarse.");
    }
  },
};

function bindEvents() {
  el("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "");
    const password = String(form.get("password") || "");
    resetSession();
    try {
      const response = await Api.post("/auth/login", { email, password });
      appState.token = response.access_token;
      sessionStorage.setItem(TOKEN_KEY, appState.token);
      await loadCurrentUser();
    } catch (error) {
      appState.token = null;
      sessionStorage.removeItem(TOKEN_KEY);
      el("email").value = email;
      setNotice(el("login-notice"), error.message);
    }
  });

  el("logout-button").addEventListener("click", () => resetSession());
  el("alert-filters").addEventListener("submit", async (event) => {
    event.preventDefault();
    AlertController.closeDetail();
    appState.alertCursor = null;
    await AlertController.load();
  });
  el("status-filter").addEventListener("change", syncFilterControls);
  el("severity-filter").addEventListener("change", syncFilterControls);
  el("clear-alert-filters").addEventListener("click", async () => {
    AlertController.closeDetail();
    el("status-filter").value = appState.defaultStatus;
    el("severity-filter").value = "";
    appState.alertCursor = null;
    syncFilterControls();
    await AlertController.load();
  });
  el("refresh-alerts").addEventListener("click", () => AlertController.load());
  el("load-more").addEventListener("click", () => AlertController.load({ append: true }));
  el("create-user-form").addEventListener("submit", (event) => UserController.create(event));
  el("refresh-users").addEventListener("click", () => UserController.load({ force: true }));
  el("simulation-form").addEventListener("submit", (event) => SimulationController.run(event));
  appState.dom.tabs.forEach((tab) => {
    tab.addEventListener("click", () => switchTab(tab.dataset.tab));
  });
  document.addEventListener("visibilitychange", refreshTimer);
}

async function initialize() {
  try {
    cacheDom();
    window.onerror = (message) => {
      reportVisibleError(typeof message === "string" ? message : "Ocurrió un error en la interfaz.");
      return false;
    };
    window.addEventListener("unhandledrejection", (event) => {
      event.preventDefault();
      const reason = event.reason;
      reportVisibleError(reason instanceof Error ? reason.message : "Ocurrió un error inesperado en la interfaz.");
    });
    bindEvents();
    const savedToken = sessionStorage.getItem(TOKEN_KEY);
    resetSession();
    if (savedToken) {
      appState.token = savedToken;
      sessionStorage.setItem(TOKEN_KEY, savedToken);
      try {
        await loadCurrentUser();
      } catch (error) {
        resetSession(error.message);
      }
    }
  } catch (error) {
    reportVisibleError(error instanceof Error ? error.message : "No se pudo inicializar la interfaz.");
  }
}

document.addEventListener("DOMContentLoaded", initialize, { once: true });
