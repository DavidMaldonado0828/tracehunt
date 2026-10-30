"use strict";

const tokenKey = "tracehunt_access_token";
let accessToken = sessionStorage.getItem(tokenKey);
let currentUser = null;
let nextAlertCursor = null;
let selectedAlertId = null;
let pendingRequests = 0;
let disabledBeforeRequest = new Map();

const $ = (id) => document.getElementById(id);
const loginPanel = $("login-panel");
const appPanel = $("app-panel");
const globalNotice = $("global-notice");
const alertRows = $("alert-rows");
const detailPanel = $("alert-detail");
const historyPanelId = "history-list";

function setBusy(active) {
  pendingRequests += active ? 1 : -1;
  if (pendingRequests < 0) pendingRequests = 0;
  if (pendingRequests > 0 && disabledBeforeRequest.size === 0) {
    document.querySelectorAll("button").forEach((button) => {
      disabledBeforeRequest.set(button, button.disabled);
      button.disabled = true;
    });
  } else if (pendingRequests === 0 && disabledBeforeRequest.size > 0) {
    disabledBeforeRequest.forEach((wasDisabled, button) => {
      if (button.isConnected) button.disabled = wasDisabled;
    });
    disabledBeforeRequest.clear();
  }
}

function showNotice(target, message, kind = "error") {
  target.textContent = message;
  target.className = `notice ${kind}`;
  target.hidden = !message;
}

function clearNotice(target) {
  target.textContent = "";
  target.hidden = true;
}

function detailMessage(payload, fallback) {
  if (payload && Array.isArray(payload.detail)) {
    return payload.detail.map((item) => {
      if (typeof item === "string") return item;
      return item.msg || item.message || JSON.stringify(item);
    }).join(" · ");
  }
  if (payload && typeof payload.detail === "string") return payload.detail;
  return fallback;
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
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
      endSession("Tu sesión expiró. Inicia sesión de nuevo.");
    }
    if (!response.ok) {
      throw new Error(detailMessage(payload, `La solicitud falló (${response.status}).`));
    }
    return payload;
  } catch (error) {
    if (error instanceof TypeError) throw new Error("No se pudo conectar con la API.");
    throw error;
  } finally {
    setBusy(false);
  }
}

function endSession(message = "") {
  accessToken = null;
  currentUser = null;
  sessionStorage.removeItem(tokenKey);
  loginPanel.hidden = false;
  appPanel.hidden = true;
  $("login-form").reset();
  if (message) showNotice($("login-notice"), message);
  else clearNotice($("login-notice"));
}

function openSession() {
  loginPanel.hidden = true;
  appPanel.hidden = false;
  clearNotice($("login-notice"));
  clearNotice(globalNotice);
}

async function loadCurrentUser() {
  currentUser = await request("/auth/me");
  $("account-email").textContent = currentUser.email;
  $("account-role").textContent = currentUser.role === "admin" ? "Administrador" : "Analista";
  openSession();
  await loadAlerts(false);
}

function addCell(row, value, className = "") {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = value === null || value === undefined || value === "" ? "—" : String(value);
  row.append(cell);
  return cell;
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
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
}

function renderAlertRows(alerts, append) {
  if (!append) alertRows.replaceChildren();
  if (!alerts.length && !append) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.className = "empty-cell";
    cell.textContent = "No hay alertas para estos filtros.";
    row.append(cell);
    alertRows.append(row);
    return;
  }
  alerts.forEach((alert) => {
    const row = document.createElement("tr");
    row.dataset.alertId = alert.alert_id;
    row.tabIndex = 0;
    row.setAttribute("aria-label", `Abrir alerta ${alert.title}`);
    if (alert.alert_id === selectedAlertId) row.classList.add("selected");
    const severityCell = document.createElement("td");
    const severityBadge = document.createElement("span");
    severityBadge.className = `badge severity-${alert.severity}`;
    severityBadge.textContent = readableSeverity(alert.severity);
    severityCell.append(severityBadge);
    row.append(severityCell);
    addCell(row, alert.title);
    addCell(row, alert.rule_id);
    const statusCell = document.createElement("td");
    const statusBadge = document.createElement("span");
    statusBadge.className = `badge status-${alert.status}`;
    statusBadge.textContent = readableStatus(alert.status);
    statusCell.append(statusBadge);
    row.append(statusCell);
    addCell(row, alert.assigned_to);
    addCell(row, formatDate(alert.created_at));
    row.addEventListener("click", () => selectAlert(alert.alert_id));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectAlert(alert.alert_id);
      }
    });
    alertRows.append(row);
  });
}

async function loadAlerts(append) {
  clearNotice(globalNotice);
  const query = new URLSearchParams();
  const statusValue = $("status-filter").value;
  const severityValue = $("severity-filter").value;
  if (statusValue) query.set("status", statusValue);
  if (severityValue) query.set("severity", severityValue);
  query.set("limit", "25");
  if (append && nextAlertCursor) query.set("cursor", nextAlertCursor);
  try {
    const response = await request(`/alerts?${query.toString()}`);
    renderAlertRows(response.items || [], append);
    nextAlertCursor = response.next_cursor || null;
    $("load-more").hidden = !nextAlertCursor;
    const count = alertRows.querySelectorAll("tr[data-alert-id]").length;
    $("alert-count").textContent = `${count} ${count === 1 ? "alerta" : "alertas"} cargada${count === 1 ? "" : "s"}`;
    if (selectedAlertId && !append) {
      const stillVisible = (response.items || []).some((alert) => alert.alert_id === selectedAlertId);
      if (!stillVisible) {
        selectedAlertId = null;
        showEmptyDetail();
      }
    }
  } catch (error) {
    showNotice(globalNotice, error.message);
  }
}

function showEmptyDetail() {
  detailPanel.replaceChildren();
  const empty = document.createElement("div");
  empty.className = "empty-state";
  const icon = document.createElement("span");
  icon.className = "empty-icon";
  icon.textContent = "⌕";
  icon.setAttribute("aria-hidden", "true");
  const title = document.createElement("h2");
  title.textContent = "Selecciona una alerta";
  const copy = document.createElement("p");
  copy.className = "muted";
  copy.textContent = "El detalle y el historial aparecerán aquí.";
  empty.append(icon, title, copy);
  detailPanel.append(empty);
}

function addSection(parent, titleText) {
  const section = document.createElement("section");
  section.className = "detail-section";
  const heading = document.createElement("h3");
  heading.textContent = titleText;
  section.append(heading);
  parent.append(section);
  return section;
}

function renderDetail(alert, history) {
  detailPanel.replaceChildren();
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
  detailPanel.append(heading);

  const description = document.createElement("p");
  description.className = "detail-copy";
  description.textContent = alert.description || "Sin descripción.";
  detailPanel.append(description);

  const meta = document.createElement("div");
  meta.className = "detail-meta";
  const publicFields = [
    ["Regla", alert.rule_id], ["Estado", readableStatus(alert.status)],
    ["Asignada a", alert.assigned_to], ["Propietario", alert.owner_user_id],
    ["Creada", formatDate(alert.created_at)], ["Primer evento", formatDate(alert.first_event_at)],
    ["Último evento", formatDate(alert.last_event_at)], ["Actualizada", formatDate(alert.updated_at)],
    ["Simulación", alert.simulation_id],
  ];
  publicFields.forEach(([label, value]) => {
    const item = document.createElement("div");
    item.className = "meta-item";
    const caption = document.createElement("span");
    caption.textContent = label;
    const content = document.createElement("strong");
    content.textContent = value || "—";
    item.append(caption, content);
    meta.append(item);
  });
  detailPanel.append(meta);

  const events = addSection(detailPanel, `Eventos relacionados (${(alert.related_event_ids || []).length})`);
  const eventList = document.createElement("ul");
  eventList.className = "event-list";
  (alert.related_event_ids || []).forEach((eventId) => {
    const item = document.createElement("li");
    item.textContent = eventId;
    eventList.append(item);
  });
  if (!alert.related_event_ids || !alert.related_event_ids.length) {
    const none = document.createElement("p");
    none.className = "muted small-text";
    none.textContent = "No hay eventos relacionados.";
    events.append(none);
  } else events.append(eventList);

  const actions = addSection(detailPanel, "Acciones");
  const comment = document.createElement("textarea");
  comment.className = "comment-box";
  comment.maxLength = 500;
  comment.placeholder = "Comentario opcional para el historial";
  comment.setAttribute("aria-label", "Comentario opcional");
  actions.append(comment);
  const actionRow = document.createElement("div");
  actionRow.className = "action-row";
  const transitions = {
    open: [["investigating", "Investigar"], ["resolved", "Resolver"]],
    investigating: [["resolved", "Resolver"]],
    resolved: [],
  };
  (transitions[alert.status] || []).forEach(([newStatus, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button secondary";
    button.textContent = label;
    button.addEventListener("click", () => changeAlertStatus(alert.alert_id, newStatus, comment.value));
    actionRow.append(button);
  });
  const assignButton = document.createElement("button");
  assignButton.type = "button";
  assignButton.className = "button secondary";
  assignButton.textContent = "Asignármela";
  assignButton.addEventListener("click", () => assignAlertToSelf(alert.alert_id));
  actionRow.append(assignButton);
  actions.append(actionRow);

  const historySection = addSection(detailPanel, `Historial (${history.length})`);
  const historyList = document.createElement("div");
  historyList.id = historyPanelId;
  historyList.className = "history-list";
  if (!history.length) {
    const none = document.createElement("p");
    none.className = "muted small-text";
    none.textContent = "Todavía no hay cambios registrados.";
    historyList.append(none);
  }
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
      const note = document.createElement("span");
      note.textContent = record.comment;
      entry.append(note);
    }
    historyList.append(entry);
  });
  historySection.append(historyList);
}

async function selectAlert(alertId) {
  selectedAlertId = alertId;
  alertRows.querySelectorAll("tr[data-alert-id]").forEach((row) => {
    row.classList.toggle("selected", row.dataset.alertId === alertId);
  });
  clearNotice(globalNotice);
  try {
    const [alert, historyPage] = await Promise.all([
      request(`/alerts/${encodeURIComponent(alertId)}`),
      request(`/alerts/${encodeURIComponent(alertId)}/history?limit=100`),
    ]);
    renderDetail(alert, historyPage.items || []);
  } catch (error) {
    showNotice(globalNotice, error.message);
  }
}

async function refreshSelectedAlert(alertId) {
  await selectAlert(alertId);
  await loadAlerts(false);
}

async function changeAlertStatus(alertId, newStatus, comment) {
  clearNotice(globalNotice);
  try {
    await request(`/alerts/${encodeURIComponent(alertId)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: newStatus, comment: comment.trim() || null }),
    });
    showNotice(globalNotice, "Estado actualizado.", "success");
    await refreshSelectedAlert(alertId);
  } catch (error) {
    showNotice(globalNotice, error.message);
  }
}

async function assignAlertToSelf(alertId) {
  clearNotice(globalNotice);
  try {
    await request(`/alerts/${encodeURIComponent(alertId)}/assignment`, {
      method: "PATCH",
      body: JSON.stringify({ assigned_to: currentUser.user_id }),
    });
    showNotice(globalNotice, "Alerta asignada a tu usuario.", "success");
    await refreshSelectedAlert(alertId);
  } catch (error) {
    showNotice(globalNotice, error.message);
  }
}

function setUtcDefaults() {
  const now = new Date();
  const dayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  $("period-end").value = now.toISOString().slice(0, 16);
  $("period-start").value = dayAgo.toISOString().slice(0, 16);
}

function dateTimeLocalToUtc(value) {
  // datetime-local no incluye zona; el campo está rotulado UTC y se interpreta explícitamente así.
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

function renderSimulationResult(result) {
  const panel = $("simulation-result");
  panel.replaceChildren();
  const heading = document.createElement("div");
  heading.className = "result-heading";
  const title = document.createElement("h2");
  title.textContent = "Resultado de simulación";
  const state = document.createElement("span");
  state.className = `badge status-${result.status}`;
  state.textContent = result.status || "Sin estado";
  heading.append(title, state);
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
  const errors = document.createElement("div");
  const errorHeading = document.createElement("h3");
  errorHeading.textContent = "Resumen de errores";
  const summary = document.createElement("p");
  summary.className = result.error_summary ? "error-summary" : "muted small-text";
  summary.textContent = result.error_summary || "Sin errores reportados.";
  errors.append(errorHeading, summary);
  panel.append(errors);
  const actions = document.createElement("div");
  actions.className = "action-row";
  const seeAlerts = document.createElement("button");
  seeAlerts.type = "button";
  seeAlerts.className = "button primary";
  seeAlerts.textContent = "Ver alertas";
  seeAlerts.addEventListener("click", async () => {
    switchTab("alerts-view");
    $("status-filter").value = "";
    $("severity-filter").value = "";
    selectedAlertId = null;
    showEmptyDetail();
    await loadAlerts(false);
  });
  actions.append(seeAlerts);
  panel.append(actions);
}

function switchTab(targetId) {
  document.querySelectorAll(".tab").forEach((tab) => {
    const active = tab.dataset.tab === targetId;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".view").forEach((view) => {
    view.hidden = view.id !== targetId;
  });
}

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearNotice($("login-notice"));
  const form = new FormData(event.currentTarget);
  try {
    const response = await request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
    });
    accessToken = response.access_token;
    sessionStorage.setItem(tokenKey, accessToken);
    await loadCurrentUser();
  } catch (error) {
    accessToken = null;
    sessionStorage.removeItem(tokenKey);
    showNotice($("login-notice"), error.message);
  }
});

$("logout-button").addEventListener("click", () => endSession());
$("alert-filters").addEventListener("submit", async (event) => {
  event.preventDefault();
  nextAlertCursor = null;
  selectedAlertId = null;
  showEmptyDetail();
  await loadAlerts(false);
});
$("refresh-alerts").addEventListener("click", () => loadAlerts(false));
$("load-more").addEventListener("click", () => loadAlerts(true));
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => switchTab(tab.dataset.tab));
});

$("simulation-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearNotice(globalNotice);
  const form = new FormData(event.currentTarget);
  let body;
  try {
    body = {
      requested_event_count: Number(form.get("requested_event_count")),
      period_start: dateTimeLocalToUtc(String(form.get("period_start"))),
      period_end: dateTimeLocalToUtc(String(form.get("period_end"))),
      seed: form.get("seed") === "" ? null : Number(form.get("seed")),
    };
  } catch {
    showNotice(globalNotice, "Revisa las fechas del periodo.");
    return;
  }
  try {
    const result = await request("/simulations", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(body),
    });
    renderSimulationResult(result);
  } catch (error) {
    showNotice(globalNotice, error.message);
  }
});

setUtcDefaults();
if (accessToken) {
  loginPanel.hidden = true;
  appPanel.hidden = false;
  loadCurrentUser().catch((error) => {
    endSession(error.message);
  });
} else {
  loginPanel.hidden = false;
  appPanel.hidden = true;
}
