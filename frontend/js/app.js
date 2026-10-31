/**
 * AIDNEXUS ONE — Dynamic Mission Control & Simulation Controller
 *
 * Trust rules (docs/context/DESIGN_PRINCIPLES.md):
 * - Every value rendered comes from the backend /api/v1/state payload.
 * - The dispatch queue is the backend's projection of the active optimizer
 *   plan. This file NEVER recomputes priority or reorders the queue.
 * - When the backend is unreachable the app shows an explicit OFFLINE state.
 *   It does NOT fabricate missions, stats, or audit events.
 * - All dynamic strings are HTML-escaped before insertion (XSS defense).
 */

const API_BASE = "/api/v1"; // same-origin; served by the FastAPI app

// ------------------------------------------------------------------
// Utilities
// ------------------------------------------------------------------
function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function fmtClock(totalSec) {
  const t = Math.floor(totalSec);
  const h = String(Math.floor(t / 3600)).padStart(2, "0");
  const m = String(Math.floor((t % 3600) / 60)).padStart(2, "0");
  const s = String(t % 60).padStart(2, "0");
  return `T+${h}:${m}:${s}`;
}

// ------------------------------------------------------------------
// Global state (mirrors backend payload only)
// ------------------------------------------------------------------
const state = {
  connectedToBackend: false,
  activeTab: "mission-command",
  mapFilter: "ALL",
  mapZoom: 1.0,
  mapPan: { x: 0, y: 0 },
  sim: { elapsedSeconds: 0, isPaused: false, speed: 2.0 },
  stats: {},
  depots: [],
  vehicles: [],
  volunteers: [],
  requests: [],
  requestById: {},
  active_disruptions: [],
  current_plan: null,
  pending_plan: null,
  dispatch_queue: [],
  blocked_requests: [],
  audit_events: [],
  selectedNode: null
};

// ------------------------------------------------------------------
// Backend sync
// ------------------------------------------------------------------
async function syncStateWithBackend() {
  try {
    const res = await fetch(`${API_BASE}/state`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.connectedToBackend = true;
    state.stats = data.stats;
    state.depots = data.depots;
    state.vehicles = data.vehicles;
    state.volunteers = data.volunteers;
    state.requests = data.requests;
    state.requestById = {};
    data.requests.forEach(r => { state.requestById[r.id] = r; });
    state.active_disruptions = data.active_disruptions;
    state.current_plan = data.current_plan;
    state.pending_plan = data.pending_plan;
    state.dispatch_queue = data.dispatch_queue;       // authoritative plan projection
    state.blocked_requests = data.blocked_requests;   // visible, explained
    state.audit_events = data.recent_audit;
    state.sim.elapsedSeconds = data.stats.sim_elapsed_seconds || 0;
    state.sim.isPaused = data.stats.is_paused || false;
    state.sim.speed = data.stats.sim_speed || 2.0;
  } catch (err) {
    state.connectedToBackend = false;
  }
  renderAll();
}

// ------------------------------------------------------------------
// Simulation control
// ------------------------------------------------------------------
async function tickSimulationStep() {
  if (!state.connectedToBackend || state.sim.isPaused) return;
  try {
    await fetch(`${API_BASE}/sim/tick`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ step_delta_sec: 1.0 })
    });
    await syncStateWithBackend();
  } catch (e) {
    state.connectedToBackend = false;
    renderAll();
  }
}

window.toggleSimulationPlay = async function () {
  state.sim.isPaused = !state.sim.isPaused;
  const btn = document.getElementById("simPlayBtn");
  if (btn) {
    btn.textContent = state.sim.isPaused ? "▶ Resume" : "⏸ Pause";
    btn.classList.toggle("paused", state.sim.isPaused);
  }
  try {
    await fetch(`${API_BASE}/sim/control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_paused: state.sim.isPaused })
    });
  } catch (e) { /* banner shows offline state */ }
};

window.setSimulationSpeed = async function (speed) {
  state.sim.speed = speed;
  document.querySelectorAll(".sim-speed-btn").forEach(btn => {
    btn.classList.toggle("active", parseFloat(btn.dataset.speed) === speed);
  });
  try {
    await fetch(`${API_BASE}/sim/control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sim_speed: speed })
    });
  } catch (e) { /* offline */ }
};

window.stepSimulationManual = function () { tickSimulationStep(); };

// ------------------------------------------------------------------
// Tabs / map controls
// ------------------------------------------------------------------
function switchTab(tabId) {
  state.activeTab = tabId;
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });
  document.querySelectorAll(".tab-pane").forEach(pane => {
    pane.classList.toggle("active", pane.id === `tab-${tabId}`);
  });
  if (tabId === "mission-command") renderCrisisMap();
}
window.switchTab = switchTab;

window.setMapFilter = function (filter) {
  state.mapFilter = filter;
  document.querySelectorAll(".map-pill").forEach(p => {
    p.classList.toggle("active", p.dataset.filter === filter);
  });
  renderCrisisMap();
};

window.zoomMap = function (delta) {
  state.mapZoom = Math.max(0.7, Math.min(2.5, state.mapZoom + delta));
  renderCrisisMap();
};

window.resetMapZoom = function () {
  state.mapZoom = 1.0;
  state.mapPan = { x: 0, y: 0 };
  renderCrisisMap();
};

// ------------------------------------------------------------------
// KPIs & header (all values from backend payload)
// ------------------------------------------------------------------
function renderKPIs() {
  const s = state.stats;
  const clockEl = document.getElementById("simClock");
  if (clockEl) clockEl.textContent = fmtClock(state.sim.elapsedSeconds);

  // Connection status: LIVE only when the real backend answers.
  const conn = document.getElementById("connectionBadge");
  if (conn) {
    if (state.connectedToBackend) {
      conn.textContent = "● LIVE — backend connected";
      conn.className = "live-badge connected";
      conn.setAttribute("aria-label", "Backend connected, showing live state");
    } else {
      conn.textContent = "○ OFFLINE — backend unreachable";
      conn.className = "live-badge offline";
      conn.setAttribute("aria-label", "Backend offline, no live data");
    }
  }

  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  if (!s || !("total_requests" in s)) { renderOfflineNotice(); return; }

  set("kpiTotalReqs", s.total_requests);
  set("kpiDelivered", s.delivered_count);
  set("kpiDispatched", s.dispatched_count);
  const critEl = document.getElementById("kpiCriticalRate");
  if (critEl) {
    critEl.textContent = `${s.critical_fulfillment_rate}%`;
    critEl.title = `Delivered critical requests / total critical requests (${s.critical_total || 0} critical total). Dispatched-but-undelivered missions are NOT counted.`;
  }
  set("kpiDisruptions", s.active_disruptions_count);
  set("kpiBlocked", s.blocked_count);
  const disBadge = document.getElementById("kpiDisruptions");
  if (disBadge) disBadge.className = s.active_disruptions_count > 0 ? "kpi-value badge-trend-danger" : "kpi-value";

  const planBadge = document.getElementById("headerPlanBadge");
  if (planBadge) {
    if (s.pending_replan_approval) {
      planBadge.className = "plan-badge warning";
      planBadge.textContent = `⚠ PLAN ${s.pending_plan_version} — APPROVAL REQUIRED`;
    } else {
      planBadge.className = "plan-badge";
      const auto = state.current_plan && state.current_plan.auto_approved;
      planBadge.textContent = `⚡ PLAN ${s.current_plan_version} ${auto ? "[system bootstrap]" : "[approved]"} · concordance ${(s.queue_concordance * 100).toFixed(0)}%`;
    }
  }
}

function renderOfflineNotice() {
  const box = document.getElementById("offlineNotice");
  if (box) box.style.display = state.connectedToBackend ? "none" : "block";
}

// ------------------------------------------------------------------
// Crisis map
// ------------------------------------------------------------------
function renderCrisisMap() {
  const svg = document.getElementById("crisisMapSvg");
  if (!svg || !state.connectedToBackend) return;

  const width = svg.clientWidth || 920;
  const height = svg.clientHeight || 560;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const minLat = 14.45, maxLat = 14.75;
  const minLng = 120.83, maxLng = 121.13;

  function project(lat, lng) {
    const baseW = width * state.mapZoom;
    const baseH = height * state.mapZoom;
    const x = ((lng - minLng) / (maxLng - minLng)) * baseW + state.mapPan.x;
    const y = baseH - (((lat - minLat) / (maxLat - minLat)) * baseH) + state.mapPan.y;
    return [x, y];
  }

  let svgHtml = `
    <defs>
      <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
        <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(56, 189, 248, 0.05)" stroke-width="1"/>
      </pattern>
      <radialGradient id="hazardGlow" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="rgba(239, 68, 68, 0.55)"/>
        <stop offset="100%" stop-color="rgba(239, 68, 68, 0)"/>
      </radialGradient>
    </defs>
    <rect width="${width}" height="${height}" fill="url(#grid)" />
    <path d="M 0,${height * 0.35} Q ${width * 0.28},${height * 0.55} ${width * 0.38},${height} L 0,${height} Z"
          fill="rgba(14, 116, 144, 0.14)" stroke="rgba(14, 116, 144, 0.3)" stroke-width="1.5" />
  `;

  if (state.mapFilter === "ALL" || state.mapFilter === "HAZARDS") {
    state.active_disruptions.forEach(dis => {
      if (dis.affected_lat && dis.affected_lng) {
        const [hx, hy] = project(dis.affected_lat, dis.affected_lng);
        svgHtml += `
          <circle cx="${hx}" cy="${hy}" r="70" fill="url(#hazardGlow)" />
          <circle cx="${hx}" cy="${hy}" r="55" fill="none" stroke="#ef4444" stroke-width="2" stroke-dasharray="6,4">
            <title>${escapeHtml(dis.title)} (radius ${dis.hazard_radius_km} km)</title>
          </circle>
          <text x="${hx}" y="${hy - 62}" fill="#ef4444" font-size="11" font-weight="700" text-anchor="middle">
            ${escapeHtml(dis.title)}
          </text>`;
      }
    });
  }

  if (state.mapFilter === "ALL" || state.mapFilter === "IN_TRANSIT") {
    state.vehicles.forEach(veh => {
      if (veh.status === "BROKEN_DOWN") return;
      if (veh.route_waypoints && veh.route_waypoints.length > 1) {
        let pathD = "";
        veh.route_waypoints.forEach((pt, idx) => {
          const [px, py] = project(pt[0], pt[1]);
          pathD += (idx === 0 ? `M ${px},${py}` : ` L ${px},${py}`);
        });
        svgHtml += `<path d="${pathD}" fill="none" stroke="rgba(0, 229, 255, 0.25)" stroke-width="2" stroke-dasharray="4,4" />`;
      }
    });
  }

  state.requests.forEach(req => {
    if (state.mapFilter === "CRITICAL" && req.priority !== "CRITICAL") return;
    if (state.mapFilter === "DELIVERED" && req.status !== "DELIVERED") return;
    if (state.mapFilter === "IN_TRANSIT" && req.status !== "DISPATCHED") return;
    if (state.mapFilter === "HAZARDS") return;

    const [rx, ry] = project(req.location.lat, req.location.lng);
    let color = "#38bdf8", radius = 4;
    if (req.priority === "CRITICAL") { color = "#ef4444"; radius = 6; }
    else if (req.priority === "HIGH") { color = "#f59e0b"; radius = 5; }
    else if (req.status === "DELIVERED") { color = "#10b981"; radius = 4.5; }

    svgHtml += `
      <g onclick="inspectNode('request', '${escapeHtml(req.id)}')" style="cursor: pointer;" role="button" aria-label="Request ${escapeHtml(req.id)} ${escapeHtml(req.priority)}">
        <circle cx="${rx}" cy="${ry}" r="${radius}" fill="${color}" opacity="0.9" />
        ${req.status === "DELIVERED" ? `<text x="${rx}" y="${ry + 3}" fill="#fff" font-size="8" text-anchor="middle">✓</text>` : ""}
      </g>`;
  });

  state.depots.forEach(dep => {
    const [dx, dy] = project(dep.location.lat, dep.location.lng);
    const isFlooded = dep.status !== "OPERATIONAL";
    const depotColor = isFlooded ? "#ef4444" : "#00e5ff";
    svgHtml += `
      <g onclick="inspectNode('depot', '${escapeHtml(dep.id)}')" style="cursor: pointer;" role="button" aria-label="Depot ${escapeHtml(dep.name)}">
        <circle cx="${dx}" cy="${dy}" r="24" fill="none" stroke="${depotColor}" stroke-width="1.5" opacity="0.4" />
        <circle cx="${dx}" cy="${dy}" r="16" fill="none" stroke="${depotColor}" stroke-width="2" />
        <rect x="${dx - 8}" y="${dy - 8}" width="16" height="16" fill="${depotColor}" rx="4" />
        <text x="${dx}" y="${dy + 28}" fill="#fff" font-size="11" font-weight="700" text-anchor="middle">
          ${escapeHtml(dep.name.split(" ")[0])} ${isFlooded ? "[OFFLINE]" : ""}
        </text>
      </g>`;
  });

  state.vehicles.forEach(veh => {
    const [vx, vy] = project(veh.current_lat, veh.current_lng);
    const isBroken = veh.status === "BROKEN_DOWN";
    const vColor = isBroken ? "#ef4444" : "#00e5ff";
    svgHtml += `
      <g onclick="inspectNode('vehicle', '${escapeHtml(veh.id)}')" style="cursor: pointer;" role="button" aria-label="Vehicle ${escapeHtml(veh.id)}">
        <circle cx="${vx}" cy="${vy}" r="8" fill="${vColor}" stroke="#fff" stroke-width="1.5" />
        <text x="${vx + 12}" y="${vy + 4}" fill="${vColor}" font-size="10" font-weight="700">
          ${escapeHtml(veh.id)}
        </text>
      </g>`;
  });

  svg.innerHTML = svgHtml;
}

// ------------------------------------------------------------------
// Node inspector
// ------------------------------------------------------------------
window.inspectNode = function (type, id) {
  const card = document.getElementById("mapInspectorCard");
  if (!card) return;

  if (type === "depot") {
    const d = state.depots.find(x => x.id === id);
    if (!d) return;
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
        <strong style="color:#00e5ff;">🏛️ ${escapeHtml(d.name)}</strong>
        <span class="depot-status-badge ${d.status.toLowerCase()}">${escapeHtml(d.status)}</span>
      </div>
      <div>Sector: ${escapeHtml(d.location.sector)}</div>
      <div style="margin-top:0.5rem; font-weight:600; color:#fff;">Live Inventory Levels:</div>
      <div style="font-size:0.75rem; margin-top:0.25rem;">
        ${Object.entries(d.inventory).map(([k, v]) => `<div>· ${escapeHtml(k)}: ${Math.round(v)}</div>`).join("")}
      </div>
      <button class="btn-secondary" style="width:100%; margin-top:0.75rem;" onclick="document.getElementById('mapInspectorCard').style.display='none'">Close</button>`;
    card.style.display = "block";
  } else if (type === "request") {
    const r = state.requestById[id];
    if (!r) return;
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
        <strong>📍 ${escapeHtml(r.id)}</strong>
        <span class="status-chip ${r.status.toLowerCase()}">${escapeHtml(r.status)}</span>
      </div>
      <div><strong>${escapeHtml(r.requester_name)}</strong> (${escapeHtml(r.location.sector)})</div>
      <div>Priority: <strong>${escapeHtml(r.priority)}</strong> · score ${r.urgency_score ?? "—"}</div>
      <div>Assigned Vehicle: <strong style="color:#00e5ff;">${r.assigned_vehicle_id ? escapeHtml(r.assigned_vehicle_id) : "Not assigned"}</strong></div>
      <div>Assigned Volunteer: ${r.assigned_volunteer_id ? escapeHtml(r.assigned_volunteer_id) : "—"}</div>
      <div style="margin-top:0.5rem;">Items Needed:</div>
      <ul style="font-size:0.75rem;">
        ${r.items.map(it => `<li>${it.quantity} ${escapeHtml(it.unit)} ${escapeHtml(it.item_type)}</li>`).join("")}
      </ul>
      <button class="btn-secondary" style="width:100%; margin-top:0.75rem;" onclick="document.getElementById('mapInspectorCard').style.display='none'">Close</button>`;
    card.style.display = "block";
  } else if (type === "vehicle") {
    const v = state.vehicles.find(x => x.id === id);
    if (!v) return;
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
        <strong style="color:#00e5ff;">🚚 ${escapeHtml(v.id)}: ${escapeHtml(v.name)}</strong>
        <span class="status-chip dispatched">${escapeHtml(v.status)}</span>
      </div>
      <div>Base Hub: <strong>${escapeHtml(v.base_depot_id)}</strong></div>
      <div>Capacity: ${v.capacity_kg} kg | Speed: ${v.speed_kmh} km/h</div>
      <div>Assigned Volunteer: ${v.assigned_volunteer_id ? escapeHtml(v.assigned_volunteer_id) : "—"}</div>
      <div>Odometer: ${Math.round(v.distance_traveled_km)} km</div>
      <div>Assigned stops: ${v.assigned_mission_ids ? v.assigned_mission_ids.length : 0}</div>
      <button class="btn-secondary" style="width:100%; margin-top:0.75rem;" onclick="document.getElementById('mapInspectorCard').style.display='none'">Close</button>`;
    card.style.display = "block";
  }
};

// ------------------------------------------------------------------
// Sidebar: depots + THE DISPATCH QUEUE (plan projection, never resorted)
// ------------------------------------------------------------------
function renderSidebar() {
  const depotContainer = document.getElementById("depotList");
  if (depotContainer) {
    depotContainer.innerHTML = state.depots.map(d => `
      <div class="depot-card ${d.status.toLowerCase()}">
        <div class="depot-meta">
          <span class="depot-name">${escapeHtml(d.name)}</span>
          <span class="depot-status-badge ${d.status.toLowerCase()}">${escapeHtml(d.status)}</span>
        </div>
        <div class="inventory-bars">
          ${["potable_water_liters", "trauma_kits"].map(key => {
            const v = d.inventory[key] || 0;
            const max = key === "potable_water_liters" ? 20000 : 500;
            const pct = Math.min(100, Math.round((v / max) * 100));
            return `
              <div class="inv-row"><span>${key === "potable_water_liters" ? "Water" : "Trauma Kits"} (${Math.round(v)})</span><span>${pct}%</span></div>
              <div class="inv-progress"><div class="inv-fill" style="width:${pct}%"></div></div>`;
          }).join("")}
        </div>
      </div>`).join("");
  }

  const queueContainer = document.getElementById("missionQueueList");
  if (queueContainer) {
    if (!state.connectedToBackend) {
      queueContainer.innerHTML = `<div class="queue-empty">Backend offline — no live queue.</div>`;
      return;
    }
    // The queue comes verbatim from the backend's plan projection.
    // Order = optimizer scheduled_sequence. This code must not re-sort it.
    const shown = state.dispatch_queue.slice(0, 60);
    queueContainer.innerHTML = shown.map(q => `
      <div class="mission-item-card ${q.humanitarian_priority.toLowerCase()} ${q.status.toLowerCase()}"
           onclick="inspectNode('request', '${escapeHtml(q.request_id)}')" role="button"
           aria-label="Queue position ${q.scheduled_sequence}, request ${escapeHtml(q.request_id)}">
        <div class="mission-card-top">
          <span class="mission-id">#${q.scheduled_sequence} · ${escapeHtml(q.request_id)}</span>
          <span class="status-chip ${q.status.toLowerCase()}">${escapeHtml(q.status)}</span>
        </div>
        <div class="mission-card-body">
          <div><strong>${escapeHtml(q.requester_name)}</strong> (${escapeHtml(q.sector)})</div>
          <div style="font-size:0.7rem; margin-top:2px;">
            ${escapeHtml(q.humanitarian_priority)} · ${escapeHtml(q.assigned_vehicle || "—")}
            · ETA ${q.estimated_arrival_min} min
            ${q.assigned_volunteer ? ` · ${escapeHtml(q.assigned_volunteer)}` : ""}
          </div>
        </div>
      </div>`).join("") +
      (state.dispatch_queue.length > 60
        ? `<div class="queue-more">+ ${state.dispatch_queue.length - 60} more in active plan (render limited)</div>`
        : "");
  }

  const blockedContainer = document.getElementById("blockedRequestsList");
  if (blockedContainer) {
    if (!state.blocked_requests.length) {
      blockedContainer.innerHTML = `<div class="queue-empty">No blocked requests in the active plan.</div>`;
    } else {
      blockedContainer.innerHTML = state.blocked_requests.slice(0, 25).map(b => `
        <div class="mission-item-card blocked">
          <div class="mission-card-top">
            <span class="mission-id">${escapeHtml(b.request_id)}</span>
            <span class="status-chip blocked">${escapeHtml(b.feasibility_status)}</span>
          </div>
          <div class="mission-card-body">
            <div><strong>${escapeHtml(b.requester_name)}</strong> (${escapeHtml(b.sector)})</div>
            <div style="font-size:0.7rem; margin-top:2px;">${escapeHtml(b.explanation)}</div>
          </div>
        </div>`).join("") +
        (state.blocked_requests.length > 25
          ? `<div class="queue-more">+ ${state.blocked_requests.length - 25} more blocked (see plan)</div>` : "");
    }
  }
}

// ------------------------------------------------------------------
// Disruptions
// ------------------------------------------------------------------
window.triggerDisruption = async function (type) {
  let payload = {};
  if (type === "BRIDGE_COLLAPSE") {
    payload = { type: "ROAD_BLOCKAGE", title: "Highway A1 River Bridge Collapse",
                description: "Severe structural failure on Highway A1. Central corridor impassable.",
                lat: 14.6195, lng: 120.9842 };
  } else if (type === "DEPOT_FLOOD") {
    payload = { type: "DEPOT_OUTAGE", title: "Depot Bravo Coastal Surge Submersion",
                description: "Tidal storm surge breached seawall; Depot Bravo offline.",
                depot_id: "DEPOT-BRAVO", lat: 14.5495, lng: 120.9442 };
  } else if (type === "VEHICLE_BREAKDOWN") {
    payload = { type: "VEHICLE_BREAKDOWN", title: "Vehicle VEH-04 Mechanical Failure",
                description: "Engine axle fracture on muddy mountain pass route.",
                lat: 14.6595, lng: 121.0142 };
  }
  try {
    const res = await fetch(`${API_BASE}/disrupt`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      await syncStateWithBackend();
      showApprovalBanner();
      return;
    }
    const err = await res.json().catch(() => ({}));
    showToast(`Disruption failed: ${err.detail || res.status}`, "error");
  } catch (e) {
    showToast("Backend unreachable — disruption not injected.", "error");
  }
};

function showApprovalBanner() {
  const banner = document.getElementById("replanApprovalBanner");
  if (banner) {
    renderApprovalDiff();
    banner.classList.add("visible");
    banner.scrollIntoView({ behavior: "smooth" });
  }
}

// Real plan diff from the pending plan's replan_delta — no hardcoded numbers.
function renderApprovalDiff() {
  const tbody = document.getElementById("approvalDiffBody");
  const pp = state.pending_plan;
  if (!tbody || !pp) return;
  const d = pp.replan_delta || {};
  const rows = [
    ["Scheduled missions", d.before_fulfilled ?? "—", d.after_fulfilled ?? "—"],
    ["Planned travel (km)", d.before_distance_km ?? "—", d.after_distance_km ?? "—"],
    ["Completed deliveries preserved", d.preserved_deliveries_count ?? 0, d.preserved_deliveries_count ?? 0],
    ["In-flight commitments kept", d.in_flight_preserved_count ?? 0, d.in_flight_preserved_count ?? 0],
    ["Blocked after replan", d.disrupted_deliveries_count ?? "—", d.blocked_after_replan ?? "—"],
  ];
  tbody.innerHTML = rows.map(([label, before, after]) => `
    <tr><td>${label}</td><td>${before}</td><td>${after}</td></tr>`).join("");
  const expl = document.getElementById("replanExplanation");
  if (expl) expl.textContent = pp.tradeoff_explanation || "";
  const title = document.getElementById("replanApprovalTitle");
  if (title) title.textContent = `🛡️ RECOVERY PLAN ${pp.version_id} — human approval required`;
  const btn = document.getElementById("approveReplanBtn");
  if (btn) btn.textContent = `✓ Review & Authorize Plan ${pp.version_id}`;
}

window.approvePlanV2 = async function () {
  try {
    const res = await fetch(`${API_BASE}/replan/approve`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approver_name: "Mission Coordinator (demo session)" })
    });
    if (res.ok) {
      await syncStateWithBackend();
      document.getElementById("replanApprovalBanner").classList.remove("visible");
      showToast("Recovery plan approved and deployed to the fleet.", "success");
      return;
    }
    const err = await res.json().catch(() => ({}));
    showToast(`Approval failed: ${err.detail || res.status}`, "error");
  } catch (e) {
    showToast("Backend unreachable — plan not approved.", "error");
  }
};

// ------------------------------------------------------------------
// AI triage (Agent 1) — calls the REAL endpoint (path fixed)
// ------------------------------------------------------------------
window.processAITriage = async function () {
  const rawText = document.getElementById("triageInputText").value;
  if (!rawText.trim()) return;

  try {
    const res = await fetch(`${API_BASE}/nlp/triage`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_text: rawText })
    });
    if (res.ok) {
      const data = await res.json();
      displayTriageResult(data.request, data.evidence);
      await syncStateWithBackend();
      return;
    }
    showToast(`Triage failed: ${res.status}`, "error");
  } catch (e) {
    showToast("Backend unreachable — triage not performed (no local fake results).", "error");
  }
};

function displayTriageResult(req, evidence) {
  const outBox = document.getElementById("triageResultBox");
  if (!outBox) return;
  const flags = [];
  if (evidence && evidence.injection_detected) flags.push("⚠ prompt-injection patterns sanitized");
  if (evidence && evidence.duplicate_of_id) flags.push(`⚠ possible duplicate of ${evidence.duplicate_of_id} — human review`);
  if (evidence && evidence.no_items_found) flags.push("⚠ no quantities found — nothing invented, needs human clarification");
  if (evidence && evidence.requires_human_review) flags.push("⚑ flagged for human review");
  outBox.innerHTML = `
    <div style="color:var(--accent-emerald); font-weight:700; margin-bottom:0.4rem;">
      Agent 1 triage complete — structured work order draft
    </div>
    <div><strong>Request ID:</strong> <span style="font-family:var(--font-mono);">${escapeHtml(req.id)}</span></div>
    <div><strong>Priority:</strong> ${escapeHtml(req.priority)} <span style="color:var(--text-muted);">(${escapeHtml(evidence ? evidence.priority_reason : "")})</span></div>
    <div><strong>Status:</strong> ${escapeHtml(req.status)} (draft — human verification required)</div>
    <div style="margin-top:0.4rem;"><strong>Extracted items (with evidence):</strong></div>
    <ul style="font-size:0.75rem;">
      ${req.items.map(it => `<li>${it.quantity} ${escapeHtml(it.unit)} ${escapeHtml(it.item_type)}
        ${it.source_text ? `<div style="color:var(--text-muted);">source: “${escapeHtml(it.source_text)}”</div>` : ""}</li>`).join("")}
    </ul>
    ${flags.map(f => `<div style="margin-top:0.3rem;">${escapeHtml(f)}</div>`).join("")}
    <div style="margin-top:0.5rem; color:var(--accent-cyan); font-size:0.75rem;">
      → Draft injected into mission state machine. The agent never denies assistance and never invents quantities.
    </div>`;
}

window.fillPreset = function (type) {
  const input = document.getElementById("triageInputText");
  if (!input) return;
  if (type === "med") {
    input.value = "Hospital in Sector 4 needs 50 units O-negative blood, 25 trauma kits immediately, water supply pipeline contaminated for 300 patients!";
  } else if (type === "water") {
    input.value = "Coastal shelter with 450 displaced residents completely out of potable drinking water. Urgent request for 2000 liters water and 100 hygiene kits.";
  } else if (type === "power") {
    input.value = "Clinic refrigeration failure in Highland Sector. Require 2 emergency generators and 50 trauma packs to preserve insulin.";
  }
};

// ------------------------------------------------------------------
// Volunteer delivery console
// ------------------------------------------------------------------
let isDrawing = false;
let sigCanvas, sigCtx, signatureDrawn = false;

function initSignaturePad() {
  sigCanvas = document.getElementById("signatureCanvas");
  if (!sigCanvas) return;
  sigCtx = sigCanvas.getContext("2d");
  sigCtx.strokeStyle = "#00e5ff";
  sigCtx.lineWidth = 2.5;
  sigCtx.lineCap = "round";

  function getPos(e) {
    const rect = sigCanvas.getBoundingClientRect();
    const clientX = e.clientX || (e.touches && e.touches[0].clientX);
    const clientY = e.clientY || (e.touches && e.touches[0].clientY);
    return [clientX - rect.left, clientY - rect.top];
  }
  sigCanvas.addEventListener("mousedown", (e) => { isDrawing = true; signatureDrawn = true; const [x, y] = getPos(e); sigCtx.beginPath(); sigCtx.moveTo(x, y); });
  sigCanvas.addEventListener("mousemove", (e) => { if (!isDrawing) return; const [x, y] = getPos(e); sigCtx.lineTo(x, y); sigCtx.stroke(); });
  window.addEventListener("mouseup", () => { isDrawing = false; });
  sigCanvas.addEventListener("touchstart", (e) => { isDrawing = true; signatureDrawn = true; const [x, y] = getPos(e); sigCtx.beginPath(); sigCtx.moveTo(x, y); e.preventDefault(); }, { passive: false });
  sigCanvas.addEventListener("touchmove", (e) => { if (!isDrawing) return; const [x, y] = getPos(e); sigCtx.lineTo(x, y); sigCtx.stroke(); e.preventDefault(); }, { passive: false });
  sigCanvas.addEventListener("touchend", () => { isDrawing = false; });
}

window.clearSignature = function () {
  if (sigCtx && sigCanvas) sigCtx.clearRect(0, 0, sigCanvas.width, sigCanvas.height);
  signatureDrawn = false;
};

window.confirmVolunteerDelivery = async function () {
  const sel = document.getElementById("volunteerMissionSelect");
  const reqId = sel && sel.value;
  if (!reqId) { showToast("Please select a mission to confirm delivery.", "error"); return; }
  if (!signatureDrawn) { showToast("Please draw the recipient's signature first.", "error"); return; }

  try {
    const res = await fetch(`${API_BASE}/deliveries/confirm`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request_id: reqId,
        volunteer_name: "Field Volunteer (demo session)",
        signature_data: signatureDrawn ? "DrawnTouchSignature" : "NoSignature"
      })
    });
    const data = await res.json();
    if (res.ok) {
      await syncStateWithBackend();
      clearSignature();
      showToast(data.duplicate
        ? `Delivery for ${reqId} was already confirmed — receipt returned, inventory NOT deducted twice.`
        : `Delivery confirmed for ${reqId}. Inventory decremented once; receipt ${String(data.signature_hash).slice(0, 12)} logged.`, "success");
      return;
    }
    showToast(`Confirmation failed: ${data.detail || res.status}`, "error");
  } catch (e) {
    showToast("Backend unreachable — delivery not confirmed.", "error");
  }
};

function updateVolunteerSelect() {
  const sel = document.getElementById("volunteerMissionSelect");
  if (!sel) return;
  // Options come from the plan projection (assigned missions only).
  const options = state.dispatch_queue
    .filter(q => q.status === "DISPATCHED" || q.status === "IN_TRANSIT")
    .slice(0, 100);
  if (!options.length) {
    sel.innerHTML = `<option value="">No assigned missions in the active plan</option>`;
    return;
  }
  sel.innerHTML = options.map(q => `
    <option value="${escapeHtml(q.request_id)}">#${q.scheduled_sequence} ${escapeHtml(q.request_id)}: ${escapeHtml(q.requester_name)} (${escapeHtml(q.humanitarian_priority)})</option>`).join("");
}

// ------------------------------------------------------------------
// Benchmark arena — REAL results from the simulation engine
// ------------------------------------------------------------------
window.runBenchmarkMatrix = async function () {
  const btn = document.getElementById("runBenchmarkBtn");
  const seedInput = document.getElementById("benchmarkSeed");
  const seed = seedInput ? parseInt(seedInput.value, 10) || 42 : 42;
  if (btn) btn.textContent = "⏳ Running live simulation (4 strategies)...";
  const sumBanner = document.getElementById("benchmarkSummaryBanner");
  if (sumBanner) sumBanner.textContent = "Executing deterministic scenario simulation — all metrics computed from the execution trace...";

  try {
    const res = await fetch(`${API_BASE}/benchmark/run?seed=${seed}&n_requests=200`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderBenchmarkCards(data.metrics, data.summary, data);
  } catch (e) {
    if (sumBanner) sumBanner.textContent = "Benchmark failed — backend unreachable or error. No fabricated results are shown.";
    const grid = document.getElementById("benchmarkCardsGrid");
    if (grid) grid.innerHTML = "";
  } finally {
    if (btn) btn.textContent = "⚡ Run 200-Mission Live Benchmark";
  }
};

function renderBenchmarkCards(metrics, summary, run) {
  const sumBanner = document.getElementById("benchmarkSummaryBanner");
  if (sumBanner) sumBanner.textContent = summary;
  const cardsContainer = document.getElementById("benchmarkCardsGrid");
  if (!cardsContainer) return;
  cardsContainer.innerHTML = metrics.map(m => {
    const isCandidate = m.strategy_name.startsWith("AIDNEXUS");
    const violations = m.inventory_violations + m.capacity_violations + m.duplicate_dispatches;
    return `
    <div class="bench-card ${isCandidate ? "winner" : ""}">
      <div class="bench-card-title">${escapeHtml(m.strategy_name)}</div>
      <div class="bench-stat-row"><span>Missions Delivered</span><span>${m.fulfilled_count} / ${m.total_requests}</span></div>
      <div class="bench-stat-row"><span>Critical Delivered %</span><span>${m.critical_fulfilled_pct}% (${m.critical_fulfilled_count}/${m.critical_total})</span></div>
      <div class="bench-stat-row"><span>Travel Distance</span><span>${m.total_travel_km} km</span></div>
      <div class="bench-stat-row"><span>Avg Delivery Time</span><span>${m.avg_delivery_time_min} min</span></div>
      <div class="bench-stat-row"><span>On-Time Delivery %</span><span>${m.on_time_delivery_pct}%</span></div>
      <div class="bench-stat-row"><span>Unmet Demand</span><span>${m.unmet_demand_count}</span></div>
      <div class="bench-stat-row"><span>Disruption Recovery %</span><span>${m.disruption_resilience_score}%</span></div>
      <div class="bench-stat-row"><span>Replan Latency</span><span>${m.replan_latency_seconds}s</span></div>
      <div class="bench-stat-row"><span>Planning Time</span><span>${m.planning_time_seconds}s</span></div>
      <div class="bench-stat-row"><span>CO2e (0.21 kg/km)</span><span>${m.carbon_emission_kg} kg</span></div>
      <div class="bench-stat-row ${violations ? "bench-violation" : ""}"><span>Integrity Violations</span><span>${violations === 0 ? "0 ✓" : violations + " ✗"}</span></div>
    </div>`;
  }).join("") + (run ? `
    <div class="bench-note" style="grid-column:1/-1; font-size:0.75rem; color:var(--text-muted);">
      Run ${escapeHtml(run.run_id)} · seed ${run.seed} · n=${run.n_requests} · disruption: depot ${escapeHtml(run.disruption.blocked_depot)} outage + ${run.disruption.hazard_radius_km} km hazard zone at ${Math.round(run.disruption.disruption_after_fraction * 100)}% completion · inventory scarcity ${run.disruption.inventory_scarcity}.
      Results are computed by simulating all four strategies on the identical scenario; they vary by seed and are reproducible via POST /api/v1/benchmark/run?seed=….
    </div>` : "");
}

// ------------------------------------------------------------------
// Evidence ledger — hash-chained, UTC timestamps
// ------------------------------------------------------------------
window.filterAuditLedger = function (keyword) {
  const tbody = document.getElementById("auditLedgerTbody");
  if (!tbody) return;
  const kw = (keyword || "").toLowerCase();
  const filtered = state.audit_events.filter(ev =>
    !kw || ev.event_type.toLowerCase().includes(kw) ||
    ev.summary.toLowerCase().includes(kw) || ev.actor_id.toLowerCase().includes(kw));
  tbody.innerHTML = filtered.slice().reverse().map(ev => `
    <tr>
      <td style="color:var(--text-muted);">${new Date(ev.timestamp * 1000).toISOString().slice(11, 19)} UTC</td>
      <td style="color:var(--accent-cyan); font-weight:600;">${escapeHtml(ev.event_type)}</td>
      <td>${escapeHtml(ev.actor_id)} (${escapeHtml(ev.actor_type)})</td>
      <td>${escapeHtml(ev.summary)}</td>
      <td class="hash-cell" title="hash: ${escapeHtml(ev.sha256_hash)} · prev: ${ev.prev_hash ? escapeHtml(ev.prev_hash.slice(0, 16)) + "…" : "genesis"}">${escapeHtml(ev.sha256_hash.slice(0, 16))}…</td>
    </tr>`).join("");
};

window.exportAuditLedger = function () {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(state.audit_events, null, 2));
  const a = document.createElement("a");
  a.setAttribute("href", dataStr);
  a.setAttribute("download", `aidnexus_audit_ledger_${Date.now()}.json`);
  document.body.appendChild(a);
  a.click();
  a.remove();
};

function renderAuditLedger() { window.filterAuditLedger(""); }

// ------------------------------------------------------------------
// Toasts (non-blocking, screen-reader friendly)
// ------------------------------------------------------------------
function showToast(message, kind) {
  let host = document.getElementById("toastHost");
  if (!host) {
    host = document.createElement("div");
    host.id = "toastHost";
    host.className = "toast-host";
    host.setAttribute("role", "status");
    host.setAttribute("aria-live", "polite");
    document.body.appendChild(host);
  }
  const toast = document.createElement("div");
  toast.className = `toast ${kind || "info"}`;
  toast.textContent = message;
  host.appendChild(toast);
  setTimeout(() => toast.remove(), 6000);
}

// ------------------------------------------------------------------
// Reset
// ------------------------------------------------------------------
window.resetScenarioUI = async function () {
  try {
    await fetch(`${API_BASE}/scenario/reset`, { method: "POST" });
    await syncStateWithBackend();
    document.getElementById("replanApprovalBanner").classList.remove("visible");
    showToast("Scenario reset to clean baseline (seed=42).", "success");
  } catch (e) {
    showToast("Backend unreachable — scenario not reset.", "error");
  }
};

// ------------------------------------------------------------------
// Render everything
// ------------------------------------------------------------------
function renderAll() {
  renderKPIs();
  renderOfflineNotice();
  renderSidebar();
  renderAuditLedger();
  updateVolunteerSelect();
  if (state.activeTab === "mission-command") renderCrisisMap();
}

window.addEventListener("DOMContentLoaded", () => {
  initSignaturePad();
  syncStateWithBackend();
  window.addEventListener("resize", () => {
    if (state.activeTab === "mission-command") renderCrisisMap();
  });
  setInterval(tickSimulationStep, 1000);
});
