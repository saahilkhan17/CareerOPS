/* CareerOps dashboard — vanilla JS, no framework, no build step.
 * Talks to the CareerOps API (default http://localhost:8000).
 * Every server-rendered string goes through esc() to prevent XSS. */
"use strict";

/* ---------- tiny helpers ---------- */

const $ = (sel, el) => (el || document).querySelector(sel);
const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));

function esc(value) {
  return String(value === null || value === undefined ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function apiBase() {
  const v = (localStorage.getItem("careerops.api") || "").trim();
  return v || "http://localhost:8000";
}

function toast(message, kind) {
  const el = $("#toast");
  el.textContent = message;
  el.className = "toast" + (kind === "error" ? " error" : "");
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => {
    el.hidden = true;
  }, 4200);
}

class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message || code || ("HTTP " + status));
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/* ---------- API client ---------- */

async function api(method, path, options) {
  const opts = options || {};
  const headers = { "Content-Type": "application/json" };
  const token = localStorage.getItem("careerops.token");
  if (token) headers.Authorization = "Bearer " + token;
  const resp = await fetch(apiBase() + path, {
    method,
    headers,
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
  });
  if (resp.status === 204) return null;
  const isJson = (resp.headers.get("content-type") || "").includes("json");
  const data = isJson ? await resp.json() : await resp.text();
  if (!resp.ok) {
    if (resp.status === 401) logout("Session expired — logged out.");
    const err = data && data.error ? data.error : {};
    throw new ApiError(resp.status, err.code, err.message, err.details);
  }
  return data;
}

const get = (path) => api("GET", path);
const post = (path, body) => api("POST", path, { body });
const put = (path, body) => api("PUT", path, { body });
const patch = (path, body) => api("PATCH", path, { body });
const del = (path) => api("DELETE", path);

async function apiBlob(path) {
  const token = localStorage.getItem("careerops.token");
  const headers = token ? { Authorization: "Bearer " + token } : {};
  const resp = await fetch(apiBase() + path, { headers });
  if (!resp.ok) throw new ApiError(resp.status, "request_failed", "Export failed");
  return resp.blob();
}

/* ---------- auth + tabs ---------- */

const STATUS_LABEL = {
  saved: "Saved",
  applied: "Applied",
  oa: "OA",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

function showApp(userEmail) {
  $("#auth-view").hidden = true;
  $("#app-view").hidden = false;
  $("#user-email").hidden = false;
  $("#user-email").textContent = userEmail;
  $("#logout-btn").hidden = false;
}

function logout(message) {
  localStorage.removeItem("careerops.token");
  $("#auth-view").hidden = false;
  $("#app-view").hidden = true;
  $("#user-email").hidden = true;
  $("#logout-btn").hidden = true;
  if (message) toast(message);
}

function switchTab(name) {
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $$(".tabpanel").forEach((p) => {
    p.hidden = p.id !== "tab-" + name;
  });
  if (name === "apps" && !state.apps.loaded) loadApps();
  if (name === "match" && !state.match.loaded) initMatch();
  if (name === "listings" && !state.listings.loaded) loadListings();
  if (name === "analytics" && !state.analytics.loaded) loadAnalytics();
}

const state = {
  apps: { items: [], total: 0, limit: 10, offset: 0, filters: {}, loaded: false, selected: null },
  match: { loaded: false },
  listings: { items: [], total: 0, limit: 10, offset: 0, filters: {}, loaded: false },
  analytics: { loaded: false },
};

/* ---------- applications ---------- */

function appFilters() {
  const f = new FormData($("#apps-filters"));
  const out = {};
  for (const [k, v] of f.entries()) if (v !== "") out[k] = v;
  return out;
}

async function loadApps() {
  const s = state.apps;
  const params = new URLSearchParams({ ...s.filters, limit: s.limit, offset: s.offset });
  try {
    const data = await get("/applications?" + params.toString());
    s.items = data.items;
    s.total = data.total;
    s.loaded = true;
    renderApps();
  } catch (e) {
    toast("Load failed: " + e.message, "error");
  }
}

function renderApps() {
  const s = state.apps;
  const tb = $("#apps-table tbody");
  tb.innerHTML = s.items
    .map(
      (a) =>
        `<tr data-id="${esc(a.id)}" class="${s.selected === a.id ? "selected" : ""}">` +
        `<td>${esc(a.title)}</td><td>${esc(a.company.name)}</td>` +
        `<td><span class="badge">${esc(STATUS_LABEL[a.status] || a.status)}</span></td>` +
        `<td>${esc(a.location || "")}</td></tr>`
    )
    .join("");
  $$("tr[data-id]", tb).forEach((tr) =>
    tr.addEventListener("click", () => selectApp(tr.dataset.id))
  );
  $("#apps-total").textContent = `(${s.total})`;
  const page = s.limit ? Math.floor(s.offset / s.limit) + 1 : 1;
  const pages = s.limit ? Math.max(1, Math.ceil(s.total / s.limit)) : 1;
  $("#apps-page").textContent = `Page ${page} of ${pages}`;
  $("#apps-prev").disabled = s.offset === 0;
  $("#apps-next").disabled = s.offset + s.limit >= s.total;
}

async function selectApp(id) {
  state.apps.selected = id;
  renderApps();
  try {
    const [app, history, notes, reminders] = await Promise.all([
      get("/applications/" + id),
      get(`/applications/${id}/history`),
      get(`/applications/${id}/notes`),
      get(`/applications/${id}/reminders`),
    ]);
    $("#app-detail").hidden = false;
    $("#detail-title").textContent = `${app.title} @ ${app.company.name}`;
    $("#detail-meta").textContent =
      `${STATUS_LABEL[app.status] || app.status}` +
      (app.location ? ` · ${app.location}` : "") +
      (app.applied_at ? ` · applied ${app.applied_at.slice(0, 10)}` : "");
    $("#detail-status").value = app.status;
    $("#detail-history").innerHTML = history
      .map(
        (h) =>
          `<li><span>${h.from_status ? esc(STATUS_LABEL[h.from_status]) + " → " : ""}` +
          `${esc(STATUS_LABEL[h.to_status])}</span><span class="muted">${esc(
            (h.changed_at || "").slice(0, 16).replace("T", " ")
          )}</span></li>`
      )
      .join("") || '<li class="muted">No history</li>';
    $("#detail-notes").innerHTML = notes
      .map((n) => `<li>${esc(n.body)}</li>`)
      .join("") || '<li class="muted">No notes</li>';
    renderReminders(reminders);
  } catch (e) {
    toast("Load failed: " + e.message, "error");
  }
}

function renderReminders(reminders) {
  $("#detail-reminders").innerHTML =
    reminders
      .map(
        (r) =>
          `<li><span class="${r.done ? "done" : ""}">Due ${esc(
            (r.due_at || "").slice(0, 16).replace("T", " ")
          )}</span>` +
          `<button class="btn ghost" data-rem="${esc(r.id)}" data-done="${r.done ? "false" : "true"}" type="button">` +
          `${r.done ? "Reopen" : "Done"}</button></li>`
      )
      .join("") || '<li class="muted">No reminders</li>';
  $$("#detail-reminders [data-rem]").forEach((b) =>
    b.addEventListener("click", async () => {
      try {
        await patch(`/applications/${state.apps.selected}/reminders/${b.dataset.rem}`, {
          done: b.dataset.done === "true",
        });
        selectApp(state.apps.selected);
      } catch (e) {
        toast("Update failed: " + e.message, "error");
      }
    })
  );
}

/* ---------- match ---------- */

function skillRow(name, years) {
  const div = document.createElement("div");
  div.className = "skill-row";
  div.innerHTML =
    `<input placeholder="Skill (e.g. postgres)" value="${esc(name || "")}" maxlength="120" />` +
    `<input placeholder="Years" type="number" min="0" max="60" step="0.5" value="${esc(
      years === undefined || years === null ? "" : years
    )}" />` +
    `<button class="btn ghost" type="button" title="Remove">✕</button>`;
  $("button", div).addEventListener("click", () => div.remove());
  return div;
}

async function initMatch() {
  state.match.loaded = true;
  try {
    const p = await get("/profile");
    $("#skill-rows").innerHTML = "";
    (p.skills || []).forEach((s) => $("#skill-rows").appendChild(skillRow(s.name, s.years)));
    if (!p.skills || !p.skills.length) $("#skill-rows").appendChild(skillRow("", ""));
    $('input[name="target_roles"]', $("#profile-form")).value = (p.target_roles || []).join(", ");
    $('input[name="education"]', $("#profile-form")).value = p.education || "";
  } catch (e) {
    if (e.status !== 404) toast("Profile load failed: " + e.message, "error");
    if (!$("#skill-rows").children.length) $("#skill-rows").appendChild(skillRow("", ""));
  }
  try {
    const history = await get("/match/history?limit=10");
    $("#match-history").innerHTML = history
      .map(
        (m) =>
          `<li><span>${esc(m.title || "Pasted JD")} — <strong>${esc(m.score)}</strong></span>` +
          `<span class="muted">${esc((m.created_at || "").slice(0, 10))}</span></li>`
      )
      .join("") || '<li class="muted">No matches yet</li>';
  } catch (e) {
    toast("History load failed: " + e.message, "error");
  }
}

function renderMatchResult(body) {
  const comps = Object.entries(body.breakdown || {})
    .map(([name, c]) => {
      const pct = Math.max(0, Math.min(100, c.score || 0));
      const extra =
        c.matched && c.matched.length
          ? `<br><span class="muted">Matched: ${esc(c.matched.join(", "))}</span>`
          : "";
      const missing =
        c.missing && c.missing.length
          ? `<br><span class="muted">Missing: ${esc(c.missing.join(", "))}</span>`
          : "";
      return (
        `<div class="bar-row"><span class="name">${esc(name)}</span>` +
        `<span class="bar" style="width:${pct}%"></span>` +
        `<span class="val">${pct} (w ${esc(c.weight)})</span></div>${extra}${missing}`
      );
    })
    .join("");
  const suggestions = (body.suggestions || [])
    .map((s) => `<li>${esc(s)}</li>`)
    .join("");
  $("#match-result").innerHTML =
    `<h3>Score: <span class="score-ring">${esc(body.score)}</span></h3>` +
    comps +
    (suggestions ? `<h3>Suggestions</h3><ul class="list">${suggestions}</ul>` : "") +
    (body.llm_explanation ? `<h3>LLM notes</h3><p>${esc(body.llm_explanation)}</p>` : "");
}

/* ---------- listings ---------- */

function listingFilters() {
  const f = new FormData($("#listings-filters"));
  const out = {};
  for (const [k, v] of f.entries()) if (v !== "") out[k] = v;
  return out;
}

async function loadListings() {
  const s = state.listings;
  const params = new URLSearchParams({ ...s.filters, limit: s.limit, offset: s.offset });
  try {
    const data = await get("/listings?" + params.toString());
    s.items = data.items;
    s.total = data.total;
    s.loaded = true;
    renderListings();
  } catch (e) {
    toast("Load failed: " + e.message, "error");
  }
}

function renderListings() {
  const s = state.listings;
  const tb = $("#listings-table tbody");
  tb.innerHTML = s.items
    .map(
      (l) =>
        `<tr data-id="${esc(l.id)}">` +
        `<td>${esc(l.title)}</td><td>${esc(l.company)}</td><td>${esc(l.source)}</td>` +
        `<td>${l.match_score === null || l.match_score === undefined ? "—" : esc(l.match_score)}</td>` +
        `<td>${l.remote ? '<span class="badge">remote</span>' : ""}</td></tr>`
    )
    .join("");
  $$("tr[data-id]", tb).forEach((tr) =>
    tr.addEventListener("click", () => selectListing(tr.dataset.id))
  );
  $("#listings-total").textContent = `(${s.total})`;
  const page = s.limit ? Math.floor(s.offset / s.limit) + 1 : 1;
  const pages = s.limit ? Math.max(1, Math.ceil(s.total / s.limit)) : 1;
  $("#listings-page").textContent = `Page ${page} of ${pages}`;
  $("#listings-prev").disabled = s.offset === 0;
  $("#listings-next").disabled = s.offset + s.limit >= s.total;
}

async function selectListing(id) {
  try {
    const l = await get("/listings/" + id);
    $("#listing-detail").hidden = false;
    $("#listing-title").textContent = `${l.title} @ ${l.company}`;
    $("#listing-meta").textContent =
      `${l.source}` +
      (l.location ? ` · ${l.location}` : "") +
      (l.salary_min || l.salary_max
        ? ` · ${l.salary_min || "?"}–${l.salary_max || "?"} ${l.currency || ""}`
        : "") +
      (l.match_score !== null && l.match_score !== undefined ? ` · score ${l.match_score}` : "");
    $("#listing-skills").innerHTML = (l.skills || [])
      .map((s) => `<span class="chip${s.required ? " req" : ""}">${esc(s.skill)}</span>`)
      .join("");
    $("#listing-desc").textContent = l.description || "(no description)";
  } catch (e) {
    toast("Load failed: " + e.message, "error");
  }
}

/* ---------- analytics ---------- */

function barList(el, items, labelKey, valueKey, maxItems) {
  const rows = items.slice(0, maxItems || 20);
  const max = Math.max(1, ...rows.map((r) => r[valueKey]));
  el.innerHTML = rows
    .map(
      (r) =>
        `<div class="bar-row"><span class="name">${esc(r[labelKey])}</span>` +
        `<span class="bar" style="width:${Math.round((r[valueKey] / max) * 100)}%"></span>` +
        `<span class="val">${esc(r[valueKey])}</span></div>`
    )
    .join("") || '<p class="muted">No data</p>';
}

async function loadAnalytics() {
  state.analytics.loaded = true;
  await Promise.all([loadTop(), loadGap(), loadSalary(), loadTrends()]);
}

async function loadTop() {
  const f = new FormData($("#top-form"));
  const params = new URLSearchParams();
  if (f.get("role")) params.set("role", f.get("role"));
  if (f.get("location")) params.set("location", f.get("location"));
  params.set("days", f.get("days") || "30");
  try {
    const data = await get("/analytics/skills/top?" + params.toString());
    barList($("#top-skills"), data.items, "skill", "postings");
  } catch (e) {
    toast("Top skills failed: " + e.message, "error");
  }
}

async function loadGap() {
  try {
    const data = await get("/analytics/my-gap");
    barList($("#my-gap"), data.items, "skill", "postings", 15);
  } catch (e) {
    toast("Gap failed: " + e.message, "error");
  }
}

async function loadSalary() {
  const f = new FormData($("#salary-form"));
  const params = new URLSearchParams();
  if (f.get("role")) params.set("role", f.get("role"));
  if (f.get("location")) params.set("location", f.get("location"));
  try {
    const data = await get("/analytics/salary?" + params.toString());
    const s = data.stats;
    const fmt = (v) => (v === null || v === undefined ? "—" : Number(v).toLocaleString());
    $("#salary-stats").innerHTML =
      `<div class="stat"><div class="k">Sample</div><div class="v">${esc(s.count)}</div></div>` +
      `<div class="stat"><div class="k">Min</div><div class="v">${fmt(s.min)}</div></div>` +
      `<div class="stat"><div class="k">Median</div><div class="v">${fmt(s.median)}</div></div>` +
      `<div class="stat"><div class="k">P75</div><div class="v">${fmt(s.p75)}</div></div>`;
  } catch (e) {
    toast("Salary failed: " + e.message, "error");
  }
}

async function loadTrends() {
  const f = new FormData($("#trends-form"));
  try {
    const data = await get("/analytics/trends?granularity=" + (f.get("granularity") || "week"));
    const pts = data.points || [];
    const max = Math.max(1, ...pts.map((p) => p.postings));
    $("#trends-chart").innerHTML = pts
      .map(
        (p) =>
          `<div class="col" title="${esc(p.bucket)}: ${esc(p.postings)}">` +
          `<div class="vbar" style="height:${Math.max(2, Math.round((p.postings / max) * 130))}px"></div>` +
          `<div class="lbl">${esc(p.bucket.slice(5))}</div></div>`
      )
      .join("") || '<p class="muted">No data</p>';
  } catch (e) {
    toast("Trends failed: " + e.message, "error");
  }
}

/* ---------- wiring ---------- */

function formData(form) {
  const out = {};
  new FormData(form).forEach((v, k) => {
    out[k] = typeof v === "string" ? v : "";
  });
  return out;
}

function init() {
  const baseInput = $("#api-base");
  baseInput.value = apiBase();
  baseInput.addEventListener("change", () => {
    localStorage.setItem("careerops.api", baseInput.value.trim());
    toast("API base saved. Log in again if needed.");
  });

  $("#logout-btn").addEventListener("click", () => logout("Logged out."));

  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = formData(e.target);
    try {
      const data = await post("/auth/login", { email: f.email, password: f.password });
      localStorage.setItem("careerops.token", data.access_token);
      const me = await get("/auth/me");
      Object.keys(state).forEach((k) => {
        state[k].loaded = false;
      });
      showApp(me.email);
      switchTab("apps");
    } catch (err) {
      toast("Login failed: " + err.message, "error");
    }
  });

  $("#register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = formData(e.target);
    try {
      await post("/auth/register", { email: f.email, password: f.password });
      toast("Account created — now log in.");
    } catch (err) {
      toast("Register failed: " + err.message, "error");
    }
  });

  $$(".tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));

  // Applications
  $("#apps-filters").addEventListener("submit", (e) => {
    e.preventDefault();
    state.apps.filters = appFilters();
    state.apps.offset = 0;
    loadApps();
  });
  $("#apps-prev").addEventListener("click", () => {
    state.apps.offset = Math.max(0, state.apps.offset - state.apps.limit);
    loadApps();
  });
  $("#apps-next").addEventListener("click", () => {
    state.apps.offset += state.apps.limit;
    loadApps();
  });
  $("#app-create").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = formData(e.target);
    const body = { company: f.company, title: f.title };
    if (f.location) body.location = f.location;
    if (f.source) body.source = f.source;
    if (f.url) body.url = f.url;
    try {
      const created = await post("/applications", body);
      e.target.reset();
      state.apps.offset = 0;
      await loadApps();
      selectApp(created.id);
      toast("Application created.");
    } catch (err) {
      toast("Create failed: " + err.message, "error");
    }
  });
  $("#apps-export").addEventListener("click", async () => {
    try {
      const blob = await apiBlob("/applications/export.csv");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "applications.csv";
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (err) {
      toast("Export failed: " + err.message, "error");
    }
  });
  $("#detail-save-status").addEventListener("click", async () => {
    try {
      await post(`/applications/${state.apps.selected}/status`, {
        to_status: $("#detail-status").value,
      });
      loadApps();
      selectApp(state.apps.selected);
    } catch (err) {
      toast("Move failed: " + err.message, "error");
    }
  });
  $("#detail-delete").addEventListener("click", async () => {
    if (!confirm("Delete this application and its history?")) return;
    try {
      await del(`/applications/${state.apps.selected}`);
      $("#app-detail").hidden = true;
      state.apps.selected = null;
      loadApps();
      toast("Deleted.");
    } catch (err) {
      toast("Delete failed: " + err.message, "error");
    }
  });
  $("#note-add").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = formData(e.target);
    try {
      await post(`/applications/${state.apps.selected}/notes`, { body: f.body });
      e.target.reset();
      selectApp(state.apps.selected);
    } catch (err) {
      toast("Note failed: " + err.message, "error");
    }
  });
  $("#reminder-add").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = formData(e.target);
    try {
      await post(`/applications/${state.apps.selected}/reminders`, { due_at: f.due_at });
      e.target.reset();
      selectApp(state.apps.selected);
    } catch (err) {
      toast("Reminder failed: " + err.message, "error");
    }
  });

  // Match
  $("#skill-add").addEventListener("click", () => $("#skill-rows").appendChild(skillRow("", "")));
  $("#profile-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = formData(e.target);
    const skills = $$("#skill-rows .skill-row")
      .map((row) => {
        const [nameEl, yearsEl] = $$("input", row);
        const name = nameEl.value.trim();
        if (!name) return null;
        const years = yearsEl.value === "" ? null : Number(yearsEl.value);
        return { name, years };
      })
      .filter(Boolean);
    try {
      await put("/profile", {
        skills,
        target_roles: f.target_roles.split(",").map((s) => s.trim()).filter(Boolean),
        education: f.education || null,
        preferences: {},
      });
      toast("Profile saved.");
    } catch (err) {
      toast("Save failed: " + err.message, "error");
    }
  });
  $("#match-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = formData(e.target);
    try {
      const body = await post("/match", { title: f.title || null, text: f.text });
      renderMatchResult(body);
      initMatchHistoryOnly();
    } catch (err) {
      toast("Scoring failed: " + err.message, "error");
    }
  });

  // Listings
  $("#listings-filters").addEventListener("submit", (e) => {
    e.preventDefault();
    state.listings.filters = listingFilters();
    state.listings.offset = 0;
    loadListings();
  });
  $("#listings-prev").addEventListener("click", () => {
    state.listings.offset = Math.max(0, state.listings.offset - state.listings.limit);
    loadListings();
  });
  $("#listings-next").addEventListener("click", () => {
    state.listings.offset += state.listings.limit;
    loadListings();
  });
  $("#import-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = formData(e.target);
    try {
      let payload;
      if (f.format === "csv") {
        payload = { format: "csv", csv_text: f.payload };
      } else {
        payload = { format: "json", records: JSON.parse(f.payload) };
      }
      const result = await post("/listings/import", payload);
      $("#import-result").textContent =
        `Inserted ${result.inserted}, skipped ${result.skipped}, errors ${result.errors}.`;
      state.listings.loaded = false;
      loadListings();
    } catch (err) {
      toast("Import failed: " + err.message, "error");
    }
  });

  // Analytics
  $("#top-form").addEventListener("submit", (e) => {
    e.preventDefault();
    loadTop();
  });
  $("#salary-form").addEventListener("submit", (e) => {
    e.preventDefault();
    loadSalary();
  });
  $("#trends-form").addEventListener("submit", (e) => {
    e.preventDefault();
    loadTrends();
  });
  $("#cooc-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = formData(e.target);
    try {
      const data = await get("/analytics/skills/cooccurrence?skill=" + encodeURIComponent(f.skill));
      $("#cooc-result").innerHTML = data.items
        .map((i) => `<span class="chip">${esc(i.skill)} · ${esc(i.postings)}</span>`)
        .join("") || '<span class="muted">No data</span>';
    } catch (err) {
      toast("Lookup failed: " + err.message, "error");
    }
  });

  if (localStorage.getItem("careerops.token")) {
    get("/auth/me")
      .then((me) => {
        showApp(me.email);
        switchTab("apps");
      })
      .catch(() => logout());
  }
}

async function initMatchHistoryOnly() {
  try {
    const history = await get("/match/history?limit=10");
    $("#match-history").innerHTML = history
      .map(
        (m) =>
          `<li><span>${esc(m.title || "Pasted JD")} — <strong>${esc(m.score)}</strong></span>` +
          `<span class="muted">${esc((m.created_at || "").slice(0, 10))}</span></li>`
      )
      .join("");
  } catch (err) {
    toast("History load failed: " + err.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", init);
