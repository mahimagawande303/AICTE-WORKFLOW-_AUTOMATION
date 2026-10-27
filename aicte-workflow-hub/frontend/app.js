/* AICTE Workflow Hub - frontend (plain JavaScript, no framework, no build step). */
let token = localStorage.getItem("token");
let user = JSON.parse(localStorage.getItem("user") || "null");
const F = { q: "", stage: "", status: "", docStatus: "" };   // filter state
let institutions = [];

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const isStaff = () => user && user.role !== "institution";

async function api(path, method = "GET", body) {
  const res = await fetch(`http://127.0.0.1:5000/api${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && token) { logout(); throw new Error("Session expired, please login again"); }
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

function toast(msg, isErr) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.className = "toast" + (isErr ? " err" : "");
  clearTimeout(toast.timer); toast.timer = setTimeout(() => t.classList.add("hidden"), 3500);
}

const COLORS = { Pending: "amber", Submitted: "blue", Verified: "green", "In Progress": "blue", Approved: "green",
  Rejected: "red", High: "red", Medium: "amber", Low: "green", Active: "green", Inactive: "red" };
const pill = t => `<span class="pill ${COLORS[t] || ""}">${esc(t)}</span>`;

function donut(items) {
  const real = items.reduce((s, i) => s + i.value, 0), total = real || 1, R = 40, C = 2 * Math.PI * R;
  let off = 0;
  const segs = items.map(i => {
    const len = (i.value / total) * C;
    const s = `<circle r="${R}" cx="60" cy="60" fill="none" stroke="${i.color}" stroke-width="18" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-off}" transform="rotate(-90 60 60)"/>`;
    off += len; return s;
  }).join("");
  const legend = items.map(i => `<div><i style="background:${i.color}"></i>${i.label}: <b>${i.value}</b></div>`).join("");
  return `<div class="donut-wrap"><svg viewBox="0 0 120 120" width="140">${segs}
    <text x="60" y="60" text-anchor="middle" font-size="20" font-weight="700">${real}</text>
    <text x="60" y="76" text-anchor="middle" font-size="9" fill="#64748b">Total</text></svg>
    <div class="legend">${legend}</div></div>`;
}

function bars(obj) {
  const max = Math.max(1, ...Object.values(obj));
  return Object.entries(obj).map(([k, v]) =>
    `<div class="bar-row"><div class="label">${esc(k)}</div><div class="bar"><div class="fill" style="width:${(v / max) * 100}%"></div></div><div class="val">${v}</div></div>`).join("");
}

/* ---------- login ---------- */
function loginView() {
  return `<div class="login-wrap"><div class="login-card">
    <h1>AICTE Workflow Hub</h1><p class="muted">Approval · Compliance · Monitoring (hackathon prototype)</p>
    <input id="email" placeholder="Email" >
    <input id="password" type="password" placeholder="Password" >
    <button class="full" data-act="login">Login</button>
    <div class="demo-btns small muted">Demo accounts (password demo123):
     <div> <button class="ghost sm" data-act="fill" data-email="official1@demo.com">Official</button>
      <button class="ghost sm" data-act="fill" data-email="institution1@demo.com">Institution</button>
  </div>
  </div>`;
}

/* ---------- layout ---------- */
const NAV = [
  ["dashboard", "Dashboard"], ["applications", "Applications"], ["compliance", "Compliance & Documents"],
  ["alerts", "Alerts"], ["institutions", "Institutions", true], ["audit", "Audit trail", true], ["config", "Workflow Rules", true],
];
function layout(active, html) {
  const links = NAV.filter(n => !n[2] || isStaff())
    .map(n => `<a href="#/${n[0]}" class="${active === n[0] ? "active" : ""}">${n[1]}</a>`).join("");
  return `<div class="layout"><aside class="sidebar"><div class="brand">AICTE Workflow Hub</div><nav class="nav">${links}</nav></aside>
    <div class="main"><div class="topbar"><span class="muted">Prototype · demo data only</span>
      <span>${esc(user.name)} ${pill(user.role)} <button class="ghost sm" data-act="logout">Logout</button></span></div>
    <div class="content">${html}</div></div></div>
    <dialog id="newAppDialog"><h2>New Application</h2>
      <select id="naType"></select>${isStaff() ? '<select id="naInst"></select>' : ""}
      <div style="display:flex;gap:8px;justify-content:flex-end"><button class="ghost" data-act="closeDialog">Cancel</button>
      <button data-act="createApp">Create</button></div></dialog>`;
}

/* ---------- pages ---------- */
async function pageDashboard() {
  const d = await api("/dashboard");
  const kpi = (n, l, c = "") => `<div class="card kpi ${c}"><div class="muted">${l}</div><div class="num">${n}</div></div>`;
  const risk = d.top_risk.map(a => `<tr class="click" onclick="location.hash='#/applications/${a.id}'">
    <td>${esc(a.app_code)}</td><td>${esc(a.institution_name)}</td><td>${esc(a.days_in_stage ?? "-")}</td>
    <td>${(a.submitted_at ? new Date(a.submitted_date).toISOString().slice(0, 10) : "-")} </td></tr>`).join("");
return `<div class="page-head"><div>
    <h1> Namaste 🙏, ${esc(user.name || "User")}!</h1>
    <div class="muted">
      Welcome to your ${user.role === "institution" ? "Institution" : "Official"} Dashboard.
    </div>
  </div></div>
  <div class="grid g4">${kpi(d.total, "Total applications")}${kpi(d.in_progress, "In progress")}
    ${kpi(d.overdue, "Overdue (past stage limit)", "red")}${kpi(d.expiring_docs, "Documents expiring ≤30 days", "amber")}
    ${kpi(d.open_alerts, "Open alerts", "red")}</div>
  <div class="grid g2">
    <div class="card" id="applicationstatuscard" style="cursor:pointer;" onclick="document.getElementById('stagependingcard').classList.toggle('show-stage-pending')">
      <h2>Application status</h2>${donut([
        { label: "In Progress", value: d.in_progress, color: "#1f6feb" }, 
        { label: "Approved", value: d.approved, color: "#16a34a" },
        { label: "Rejected", value: d.rejected, color: "#dc2626" }])}
        </div>
    <div class="card stage-pending-card" id="stagependingcard"><h2>Stage-wise pending</h2>${bars(d.stage_counts)}</div></div>
  <div class="card"><h2>Highest-risk applications <span class="muted small">(rule-based score, see Application Details for reasons)</span></h2>
    <div class="table-wrap"><table><tr><th>Application</th><th>Institution</th><th>days_in_stage</th><th>submitted_date</th></tr>${risk || '<tr><td colspan="4" class="muted">No active applications</td></tr>'}</table></div></div>`;
}

async function pageApplications() {
  const qs = new URLSearchParams(
    Object.entries({ q: F.q, stage: F.stage, status: F.status })
      .filter(([, v]) => v)
  ).toString();

  const [rows, cfg] = await Promise.all([
    api("/applications?" + qs),
    api("/config")
  ]);

  const opt = (arr, cur) =>
    `<option value="">All</option>` +
    arr.map(x => `<option ${x === cur ? "selected" : ""}>${x}</option>`).join("");

  const body = rows.map(a => `
    <tr class="click" onclick="location.hash='#/applications/${a.id}'">
      <td><b>${esc(a.app_code)}</b></td>
      <td>${esc(a.institution_name)}</td>
      <td>${esc(a.type)}</td>
      <td>${esc(a.current_stage)}</td>
      <td>${pill(a.status)}</td>
      <td>${a.status === "In Progress" ? `${a.days_in_stage}/${a.sla_days} d` : "-"}</td>
      <td>${a.status === "In Progress" ? pill(a.risk.level) + " " + a.risk.score : "-"}</td>
      <td>${esc(a.submitted_on)}</td>
    </tr>`).join("");

  return `
    <div class="page-head">
      <div>
        <h1>Applications</h1>
        <div class="muted">Manage and track all applications (${rows.length} shown)</div>
      </div>
      ${isStaff()
        ? '<button data-act="openNewApp">+ New Application</button>'
        : '<button data-act="newInstitutionApplication">+ New Application</button>'}
    </div>

    <div class="card">
      <div class="filters">
        <input id="fq" placeholder="Search code or institution" value="${esc(F.q)}">
        <select id="fstage">${opt(cfg.stages, F.stage)}</select>
        <select id="fstatus">${opt(["In Progress", "Approved", "Rejected"], F.status)}</select>
        <button data-act="applyFilters">Search</button>
      </div>
      <div class="table-wrap">
        <table>
          <tr>
            <th>ID</th><th>Institution</th><th>Type</th><th>Stage</th>
            <th>Status</th><th>Days in stage</th><th>Risk</th><th>Submitted</th>
          </tr>
          ${body || '<tr><td colspan="8" class="muted">No applications found</td></tr>'}
        </table>
      </div>
    </div>`;
}

/* ---------- Institution application catalogue ---------- */

const APPLICATION_INFO = {
  "New Institution Approval": {
    intro: "Apply to start a new technical institution.",
    rules: [
      "Provide complete and accurate information.",
      "Prepare the required supporting documents.",
      "The application is subject to official scrutiny."
    ],
    requirements: [
      "Institution or society details",
      "Proposed location and infrastructure",
      "Authorized contact person details"
    ],
    deadline: "Demo deadline: 30 November 2026"
  },

  "Extension of Approval": {
    intro: "Apply to continue approval for an existing institution or programme.",
    rules: [
      "Keep institutional information updated.",
      "Prepare current compliance documents.",
      "Approval depends on the applicable review process."
    ],
    requirements: [
      "Existing approval details",
      "Current faculty and infrastructure information",
      "Compliance documents"
    ],
    deadline: "Demo deadline: 15 December 2026"
  },

  "Increase in Intake": {
    intro: "Request approval to increase the intake of an existing programme.",
    rules: [
      "Mention the existing and proposed intake.",
      "Prepare faculty and infrastructure information.",
      "The request is subject to official scrutiny."
    ],
    requirements: [
      "Programme details",
      "Existing and proposed intake",
      "Faculty and infrastructure evidence"
    ],
    deadline: "Demo deadline: 20 December 2026"
  }
};

function appInfo(type, requiredDocs = []) {
  const info = APPLICATION_INFO[type] || {
    intro: `Start an application for ${type}. Review the required documents before proceeding.`,
    rules: [
      "Enter accurate information.",
      "Prepare all required documents.",
      "Follow the applicable review process."
    ],
    requirements: [
      "Institution details",
      "Authorized contact details",
      "Supporting evidence"
    ],
    deadline: "Demo deadline: 31 December 2026"
  };

  return { ...info, documents: requiredDocs };
}

async function pageNewApplicationTypes() {
  if (isStaff()) {
    return `<div class="card">
      <h2>Institution access only</h2>
      <button data-act="backApplications">Back to Applications</button>
    </div>`;
  }

  const cfg = await api("/config");
  const types = Object.keys(cfg.required_docs || {});

  const cards = types.map(type => {
    const info = appInfo(type, cfg.required_docs[type] || []);

    return `<div class="card application-type-card">
      <div class="app-type-icon">▤</div>
      <h2>${esc(type)}</h2>
      <p class="muted">${esc(info.intro)}</p>
      <p><b>Deadline:</b> ${esc(info.deadline.replace("Demo deadline: ", ""))}</p>
      <button data-act="viewApplicationType" data-type="${esc(type)}">
        View details →
      </button>
    </div>`;
  }).join("");

  return `<div class="page-head">
      <div>
        <h1>New Application</h1>
        <div class="muted">Choose the application type you want to submit.</div>
      </div>
      <button class="ghost" data-act="backApplications">← Back to Applications</button>
    </div>

    <div class="application-type-grid">
      ${cards || '<div class="card">No application types configured.</div>'}
    </div>

    <p class="muted small">
      Deadlines are illustrative demo dates, not verified official AICTE deadlines.
    </p>`;
}

async function pageNewApplicationDetail(type) {
  if (isStaff()) {
    return `<div class="card">
      <h2>Institution access only</h2>
      <button data-act="backApplications">Back to Applications</button>
    </div>`;
  }

  const cfg = await api("/config");
  const types = Object.keys(cfg.required_docs || {});

  if (!types.includes(type)) {
    return `<div class="card">
      <h2>Application type not found</h2>
      <button data-act="newInstitutionApplication">Back to application types</button>
    </div>`;
  }

  const info = appInfo(type, cfg.required_docs[type] || []);
  const list = items => items.length
    ? items.map(x => `<li>${esc(x)}</li>`).join("")
    : "<li>Check the applicable requirements with the responsible authority.</li>";

  return `<div class="page-head">
      <div>
        <div class="muted small">
          <a href="#/new-applications">New Application</a> / Details
        </div>
        <h1>${esc(type)}</h1>
        <div class="muted">Review the details before starting.</div>
      </div>
      <button class="ghost" data-act="newInstitutionApplication">← All application types</button>
    </div>

    <div class="card">
      <h2>Introduction</h2>
      <p>${esc(info.intro)}</p>
    </div>

    <div class="grid g2">
      <div class="card">
        <h2>Rules and instructions</h2>
        <ul>${list(info.rules)}</ul>
      </div>
      <div class="card">
        <h2>Institutional requirements</h2>
        <ul>${list(info.requirements)}</ul>
      </div>
    </div>

    <div class="card">
      <h2>Required documents</h2>
      <ul>${list(info.documents)}</ul>
    </div>

    <div class="card deadline-card">
      <h2>Important date</h2>
      <p><b>${esc(info.deadline)}</b></p>
      <p class="muted small">Confirm the official deadline before submission.</p>
    </div>

    <div class="application-cta">
      <div>
        <h2>Ready to begin?</h2>
        <p class="muted">Keep your supporting documents ready.</p>
      </div>
      <button data-act="fillApplication" data-type="${esc(type)}">
        Fill Application →
      </button>
    </div>`;
}

async function pageFillApplication(type) {
  if (isStaff()) {
    return `<div class="card">
      <h2>Institution access only</h2>
      <button data-act="backApplications">Back to Applications</button>
    </div>`;
  }

  const cfg = await api("/config");
  const types = Object.keys(cfg.required_docs || {});

  if (!types.includes(type)) {
    return `<div class="card">
      <h2>Application type not found</h2>
      <button data-act="newInstitutionApplication">Back to application types</button>
    </div>`;
  }

  const info = appInfo(type, cfg.required_docs[type] || []);

  return `<div class="page-head">
      <div>
        <h1>Fill Application</h1>
        <div class="muted">${esc(type)}</div>
      </div>
    </div>

    <form id="institutionApplicationForm" class="card application-form" onsubmit="return false">
      <h2>Institution details</h2>

      <label for="institutionName">Institution name</label>
      <input id="institutionName" required placeholder="Enter institution name">

      <label for="contactName">Authorized contact person</label>
      <input id="contactName" required placeholder="Enter contact person name">

      <label for="contactEmail">Contact email</label>
      <input id="contactEmail" type="email" required placeholder="name@example.com">

      <label for="institutionAddress">Institution address</label>
      <textarea id="institutionAddress" required rows="3" placeholder="Enter full address"></textarea>

      <h2>Document checklist</h2>
      <p class="muted small">This checklist does not upload files.</p>

      <div class="document-checklist">
        ${info.documents.map(d => `
          <label class="check-row">
            <input type="checkbox" name="preparedDoc" value="${esc(d)}">
            <span>${esc(d)}</span>
          </label>
        `).join("") || '<p class="muted">No documents configured.</p>'}
      </div>

      <p class="prototype-note">
        Demo: only the application type is sent to the current backend.
        Other form fields and checklist selections are not saved.
      </p>

      <div class="form-actions">
        <button type="button" class="ghost"
          data-act="viewApplicationType" data-type="${esc(type)}">Back</button>

        <button type="button" data-act="submitInstitutionApplication"
          data-type="${esc(type)}">Create Application</button>
      </div>
    </form>`;
}

function docActions(d) {
  if (d.status === "Verified") return "";
  const submit = `<button class="ghost sm" data-act="doc" data-id="${d.id}" data-status="Submitted" data-ask="1">${isStaff() ? "Mark submitted" : "Upload (simulated)"}</button>`;
  const verify = isStaff() && d.status === "Submitted" ? `<button class="sm" data-act="doc" data-id="${d.id}" data-status="Verified">Verify</button>` : "";
  return (d.status === "Pending" ? submit : "") + " " + verify;
}
function expiryCell(d) {
  if (d.days_to_expiry === null || d.days_to_expiry === undefined) return '<span class="muted">-</span>';
  const t = d.days_to_expiry;
  const p = t < 0 ? `<span class="pill red">expired ${-t}d ago</span>` : t <= 30 ? `<span class="pill amber">${t} days left</span>` : `<span class="muted">${t} days</span>`;
  return `${esc(d.expiry_date)} ${p}`;
}

async function pageDetail(id) {
  const d = await api("/applications/" + id), a = d.application, p = d.prediction;
  const idx = d.stages.indexOf(a.current_stage), closed = a.status !== "In Progress";
  const stepper = d.stages.map((s, i) => {
    const h = d.history.find(x => x.stage === s);
    const cls = (h && h.completed_on) || (closed && i <= idx) ? "done" : i === idx ? "current" : "";
    return `<div class="step ${cls}"><div class="dot"></div><b>${s}</b><div class="muted small">${h ? esc(h.entered_on) : "Pending"}</div></div>`;
  }).join("");
  const color = a.risk.level === "High" ? "#dc2626" : a.risk.level === "Medium" ? "#d97706" : "#16a34a";
  const docs = d.documents.map(x => `<tr><td>${esc(x.name)}</td><td>${pill(x.status)}</td><td>${expiryCell(x)}</td><td class="right">${closed ? "" : docActions(x)}</td></tr>`).join("");
  const hist = d.history.map(h => `<tr><td>${esc(h.stage)}</td><td>${esc(h.entered_on)}</td><td>${esc(h.completed_on || "in progress")}</td></tr>`).join("");
  const advanceBtn = isStaff() && !closed
    ? `<button data-act="advance" data-id="${a.id}" data-final="${idx === d.stages.length - 1}">${idx === d.stages.length - 1 ? "Record final decision" : "Move to next stage →"}</button>` : "";
  return `<div class="page-head"><div><div class="muted small"><a href="#/applications">Applications</a> / ${esc(a.app_code)}</div>
    <h1>${esc(a.app_code)} ${pill(a.status)}</h1>
    <div class="muted">${esc(a.institution_name)} · ${esc(a.type)} · submitted ${esc(a.submitted_on)} · assigned to ${esc(a.assigned_name || "nobody yet")}</div></div>${advanceBtn}</div>
  <div class="card"><h2>Workflow progress</h2><div class="stepper">${stepper}</div></div>
  <div class="grid g2">
    <div class="card"><h2>Risk score: ${a.risk.score}/100 ${pill(a.risk.level)}</h2>
      <div class="riskbar"><div style="width:${a.risk.score}%;background:${color}"></div></div>
      <ul class="reasons">${a.risk.reasons.map(r => `<li>${esc(r)}</li>`).join("")}</ul>
      <div class="muted small" style="margin-top:8px">Rule-based scoring (not a trained ML model). Every point is explained above.</div></div>
    <div class="card"><h2>Current stage & forecast</h2>
      ${closed ? "<p>Application is closed.</p>" : `<p>Stage <b>${esc(a.current_stage)}</b>: day <b>${a.days_in_stage}</b> of ${a.sla_days} allowed
        ${a.overdue_days ? `<span class="pill red">${a.overdue_days} day(s) overdue</span>` : ""}</p>
        <p>Expected completion: <b>${esc(p.expected_date)}</b> (~${p.remaining_days} days)</p>
        <div class="muted small">${esc(p.method)}. Minimum samples used: ${p.min_samples}. This is an estimate from synthetic demo history.</div>`}</div></div>
  <div class="card"><h2>Documents</h2><div class="table-wrap"><table><tr><th>Document</th><th>Status</th><th>Expiry</th><th></th></tr>${docs}</table></div></div>
  <div class="card"><h2>Stage history</h2><div class="table-wrap"><table><tr><th>Stage</th><th>Entered</th><th>Completed</th></tr>${hist}</table></div></div>`;
}

async function pageCompliance() {
  const rows = await api("/documents" + (F.docStatus ? "?status=" + F.docStatus : ""));
  const body = rows.map(r => `<tr><td>${esc(r.name)}</td><td><a href="#/applications/${r.application_id}">${esc(r.app_code)}</a></td>
    <td>${esc(r.institution_name)}</td><td>${pill(r.status)}</td><td>${expiryCell(r)}</td><td class="right">${docActions(r)}</td></tr>`).join("");
  return `<div class="page-head"><div><h1>Compliance & Documents</h1><div class="muted">Documents of in-progress applications, soonest expiry first</div></div></div>
  <div class="card"><div class="filters"><select id="fdoc"><option value="">All statuses</option>
    ${["Pending", "Submitted", "Verified"].map(s => `<option ${F.docStatus === s ? "selected" : ""}>${s}</option>`).join("")}</select>
    <button data-act="applyDocFilter">Filter</button></div>
  <div class="table-wrap"><table><tr><th>Document</th><th>Application</th><th>Institution</th><th>Status</th><th>Expiry</th><th></th></tr>
  ${body || '<tr><td colspan="6" class="muted">Nothing here</td></tr>'}</table></div></div>`;
}

async function pageAlerts() {
  const rows = await api("/alerts");
  const items = rows.map(a => `<div class="alert-item"><div>${pill(a.severity)} <span class="pill">${esc(a.kind)}</span>
    <a href="#/applications/${a.application_id}">${esc(a.message)}</a></div>
    ${isStaff() ? `<button class="ghost sm" data-act="resolve" data-id="${a.id}">Resolve</button>` : ""}</div>`).join("");
  return `<div class="page-head"><div><h1>Alerts & Notifications</h1><div class="muted">${rows.length} open alert(s). In-app only (email/SMS not implemented).</div></div>
    ${isStaff() ? '<button data-act="refreshAlerts">Run alert engine</button>' : ""}</div>
  <div class="card">${items || '<div class="muted">No open alerts 🎉</div>'}</div>`;
}

async function pageInstitutions() {
  const rows = await api("/institutions");
  institutions = rows;
  return `<div class="page-head"><div><h1>Institutions</h1><div class="muted">Synthetic demo institutions</div></div></div>
  <div class="card"><div class="table-wrap"><table><tr><th>ID</th><th>Name</th><th>City</th><th>Applications</th><th>Active</th><th>Status</th></tr>
  ${rows.map(r => `<tr><td>${r.id}</td><td>${esc(r.name)}</td><td>${esc(r.city)}</td><td>${r.applications}</td><td>${r.active}</td><td>${pill(r.status)}</td></tr>`).join("")}</table></div></div>`;
}

async function pageAudit() {
  const rows = await api("/audit");
  return `<div class="page-head"><div><h1>Audit Log</h1><div class="muted">Last 100 actions</div></div></div>
  <div class="card"><div class="table-wrap"><table><tr><th>Time (UTC)</th><th>User</th><th>Action</th><th>Details</th></tr>
  ${rows.map(r => `<tr><td>${esc(r.ts)}</td><td>${esc(r.user_name)}</td><td>${esc(r.action)}</td><td>${esc(r.details)}</td></tr>`).join("")}</table></div></div>`;
}

async function pageConfig() {
  const c = await api("/config");
  return `<div class="page-head"><div><h1>Workflow Rules</h1><div class="muted">Read-only in this prototype (editable config is a proposed feature). Values are assumed demo rules, not official AICTE norms.</div></div></div>
  <div class="grid g2"><div class="card"><h2>Stages & time limit</h2>${Object.entries(c.sla_days).map(([s, d]) => `<div class="bar-row"><div class="label">${esc(s)}</div><b>${d} days</b></div>`).join("")}
    <p class="muted small">Rule: an application cannot leave Scrutiny while any document is Pending.</p></div>
  <div class="card"><h2>Required documents</h2>${Object.entries(c.required_docs).map(([t, d]) => `<p><b>${esc(t)}</b><br><span class="muted">${d.map(esc).join(", ")}</span></p>`).join("")}</div></div>`;
}

/* ---------- router ---------- */
async function render() {
  const root = document.getElementById("root");
  if (!token) { root.innerHTML = loginView(); return; }
  const parts = (location.hash || "#/dashboard").replace("#/", "").split("/");
  const page = parts[0] || "dashboard";
  try {
    let html;
    if (page === "applications" && parts[1]) {
      html = await pageDetail(parts[1]);
    } else if (page === "new-applications" && parts[1] === "type" && parts[2]) {
      html = await pageNewApplicationDetail(
        decodeURIComponent(parts.slice(2).join("/"))
      );
    } else if (page === "new-applications" && parts[1] === "fill" && parts[2]) {
      html = await pageFillApplication(
        decodeURIComponent(parts.slice(2).join("/"))
      );
    } else if (page === "new-applications") {
      html = await pageNewApplicationTypes();
    } else {
      html = await ({
        dashboard: pageDashboard,
        applications: pageApplications,
        compliance: pageCompliance,
        alerts: pageAlerts,
        institutions: pageInstitutions,
        audit: pageAudit,
        config: pageConfig
      }[page] || pageDashboard)();
    }

    root.innerHTML = layout(page, html);
  } catch (e) {
    if (token) { root.innerHTML = layout(page, `<div class="card"><h2>Something went wrong</h2><p>${esc(e.message)}</p></div>`); }
  }
}

function logout() { token = null; user = null; localStorage.clear(); location.hash = ""; render(); }

/* ---------- actions (event delegation) ---------- */
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-act]"); if (!b) return;
  const act = b.dataset.act;
  try {
    if (act === "fill") document.getElementById("email").value = b.dataset.email;
    else if (act === "login") {
      const r = await api("/login", "POST", { email: document.getElementById("email").value, password: document.getElementById("password").value });
      token = r.token; user = r.user; localStorage.setItem("token", token); localStorage.setItem("user", JSON.stringify(user));
      location.hash = "#/dashboard"; await render();
    } else if (act === "logout") logout();
    else if (act === "applyFilters") { F.q = fq.value; F.stage = fstage.value; F.status = fstatus.value; await render(); }
    else if (act === "applyDocFilter") { F.docStatus = fdoc.value; await render(); }
    else if (act === "newInstitutionApplication") {
  location.hash = isStaff() ? "#/applications" : "#/new-applications";
  await render();
}
    else if (act === "closeDialog") document.getElementById("newAppDialog").close();
    else if (act === "createApp") {
      const body = { type: naType.value }; if (isStaff()) body.institution_id = Number(naInst.value);
      const r = await api("/applications", "POST", body);
      toast("Created " + r.app_code); location.hash = "#/applications/" + r.id; await render();
    } else if (act === "advance") {
      let body;
      if (b.dataset.final === "true") {
        const dec = prompt("Final decision? Type Approved or Rejected"); if (!dec) return; body = { decision: dec.trim() };
      }
      const r = await api(`/applications/${b.dataset.id}/advance`, "POST", body); toast(r.message); await render();
    } else if (act === "doc") {
      let expiry;
      if (b.dataset.ask) { expiry = prompt("Document expiry date (YYYY-MM-DD), leave empty if none:") || undefined; }
      await api(`/documents/${b.dataset.id}/status`, "POST", { status: b.dataset.status, expiry_date: expiry });
      toast("Document updated"); await render();
    } else if (act === "resolve") { await api(`/alerts/${b.dataset.id}/resolve`, "POST"); toast("Alert resolved"); await render(); }
    else if (act === "refreshAlerts") {
      const r = await api("/alerts/refresh", "POST"); toast(`New alerts: ${r.created}, auto-resolved: ${r.auto_resolved}`); await render();
    }
  } catch (err) { toast(err.message, true); }
});

async function openNewApp() {
  const cfg = await api("/config");
  naType.innerHTML = Object.keys(cfg.required_docs).map(t => `<option>${t}</option>`).join("");
  if (isStaff()) {
    const list = await api("/institutions");
    naInst.innerHTML = list.map(i => `<option value="${i.id}">${esc(i.name)}</option>`).join("");
  }
  document.getElementById("newAppDialog").showModal();
}

document.addEventListener("keydown", e => { if (e.key === "Enter" && !token && document.getElementById("password")) document.querySelector('[data-act="login"]').click(); });
window.addEventListener("hashchange", render);
render();
