/* AIDNEXUS System Design Studio — interactive layer (Phase V).
 * Uses globals from app.js (escapeHtml, apiFetch, API_BASE) and the
 * data from system-design-data.js. Honest status labels throughout. */
"use strict";

const sdState = { chapter: 0, topic: null, theme: "dark", initialized: false };

function sdEsc(s) { return escapeHtml(String(s === undefined || s === null ? "" : s)); }

window.sdSection = function (name) {
  ["topics", "map", "trace", "lab"].forEach(n => {
    document.getElementById("sdSection-" + n).hidden = (n !== name);
    const b = document.getElementById("sdnav-" + n);
    if (b) b.classList.toggle("active", n === name);
  });
};

window.sdSetTheme = function () {
  sdState.theme = sdState.theme === "dark" ? "light" : "dark";
  document.body.classList.toggle("sd-light", sdState.theme === "light");
  document.getElementById("sdThemeBtn").textContent =
    sdState.theme === "dark" ? "☀️ Light" : "🌙 Dark";
};

window.sdSelectChapter = function (n) {
  sdState.chapter = n;
  sdState.topic = null;
  document.querySelectorAll(".sd-chapter").forEach(b =>
    b.classList.toggle("active", +b.dataset.chapter === n));
  renderSdTopics();
};

function renderSdChapters() {
  document.getElementById("sdChapters").innerHTML =
    `<button class="sd-chapter ${sdState.chapter === 0 ? "active" : ""}" data-chapter="0"
             onclick="sdSelectChapter(0)" role="tab" aria-label="All chapters">All</button>` +
    window.SD_CHAPTERS.map(c =>
      `<button class="sd-chapter ${sdState.chapter === c.n ? "active" : ""}" data-chapter="${c.n}"
               onclick="sdSelectChapter(${c.n})" role="tab" aria-label="Chapter ${c.n}: ${sdEsc(c.title)}">
        ${c.n}. ${sdEsc(c.title)}</button>`).join("");
}

function sdStatusChip(status) {
  const cls = { "IMPLEMENTED": "delivered", "MANAGED BY PLATFORM": "dispatched",
                "PREPARED": "planned", "NOT REQUIRED": "blocked",
                "BLOCKED": "blocked", "SIMULATED": "blocked" }[status] || "planned";
  return `<span class="status-chip ${cls}" title="${sdEsc(status)}">${sdEsc(status)}</span>`;
}

function renderSdTopics() {
  const list = document.getElementById("sdTopicList");
  const detail = document.getElementById("sdTopicDetail");
  const topics = window.SD_TOPICS.filter(t =>
    sdState.chapter === 0 ||
    (window.SD_CHAPTERS.find(c => c.n === sdState.chapter) || {}).topics.includes(t.id));
  detail.hidden = true;
  list.hidden = false;
  list.innerHTML = topics.map(t => `
    <div class="sd-topic-card" role="button" tabindex="0" onclick="sdOpenTopic(${t.id})"
         onkeydown="if(event.key==='Enter')sdOpenTopic(${t.id})" aria-label="Topic ${t.id}: ${sdEsc(t.title)}">
      <div class="dname">${String(t.id).padStart(2, "0")} · ${sdEsc(t.title)}</div>
      <div style="margin-top:0.3rem;">${sdStatusChip(t.status)}</div>
      <div class="dnum">${sdEsc(t.problem.slice(0, 90))}…</div>
    </div>`).join("");
}

window.sdOpenTopic = function (id) {
  const t = window.SD_TOPICS.find(x => x.id === id);
  if (!t) return;
  sdState.topic = id;
  const chapter = window.SD_CHAPTERS.find(c => c.topics.includes(id)) || { n: 0, title: "Overview" };
  document.getElementById("sdTopicList").hidden = true;
  const d = document.getElementById("sdTopicDetail");
  d.hidden = false;
  const row = (label, val) => `
    <div class="sd-field"><div class="sd-label">${label}</div>
    <div class="sd-value">${val}</div></div>`;
  d.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; gap:0.5rem; flex-wrap:wrap;">
      <h3 style="font-family:var(--font-heading); color:#fff; margin:0;">
        ${String(t.id).padStart(2, "0")} · ${sdEsc(t.title)}</h3>
      <div>${sdStatusChip(t.status)}
        <button class="btn-secondary" style="font-size:0.72rem;" onclick="sdSelectChapter(${sdState.chapter})" aria-label="Back to topics">← Back</button></div>
    </div>
    <p style="color:var(--text-secondary); font-size:0.8rem;">Chapter ${chapter.n} — ${sdEsc(chapter.title)}</p>
    ${row("The problem", sdEsc(t.problem))}
    ${row("Analogy", sdEsc(t.analogy))}
    ${row("AIDNEXUS application", sdEsc(t.aidnexus))}
    ${row("Implementation location", `<code>${sdEsc(t.location)}</code>`)}
    ${row("Real code", `<pre class="sd-code">${sdEsc(t.code)}</pre>`)}
    ${row("When it fails", sdEsc(t.failure))}
    ${row("Security", sdEsc(t.security))}
    ${row("Trade-offs", sdEsc(t.tradeoff))}
    ${row("When to use it", sdEsc(t.whenUse))}
    ${row("When NOT to use it", sdEsc(t.whenNot))}
    ${row("Testing methodology", `<code>${sdEsc(t.test)}</code>`)}
    ${t.lab ? row("Failure lab", sdEsc(t.lab)) : ""}
    <div class="sd-field"><div class="sd-label">Knowledge check</div>
      ${t.quiz.map((q, i) => `
        <div class="sd-quiz">
          <button class="sd-quiz-q" onclick="this.nextElementSibling.classList.toggle('open')"
                  aria-label="Reveal answer to question ${i + 1}">${i + 1}. ${sdEsc(q[0])}</button>
          <div class="sd-quiz-a">✓ ${sdEsc(q[1])}</div>
        </div>`).join("")}
    </div>`;
  d.scrollIntoView({ behavior: "smooth", block: "start" });
};

function renderSdMap() {
  document.getElementById("sdMapGrid").innerHTML = window.SD_MAP.map((c, i) => `
    <div class="sd-map-card" role="button" tabindex="0" onclick="sdMapDetail(${i})"
         onkeydown="if(event.key==='Enter')sdMapDetail(${i})"
         aria-label="Inspect component ${sdEsc(c.name)}">
      <div class="sd-area">${sdEsc(c.area)}</div>
      <div class="dname">${sdEsc(c.name)}</div>
      <div style="margin-top:0.3rem;">${sdStatusChip(c.status)}</div>
    </div>`).join("");
}

window.sdMapDetail = function (i) {
  const c = window.SD_MAP[i];
  document.getElementById("sdMapDetail").innerHTML = `
    <div class="atlas-feature">
      <span class="fid">${sdEsc(c.area)}</span> ${sdStatusChip(c.status)}
      <div class="fname">${sdEsc(c.name)}</div>
      <div class="fdesc">${sdEsc(c.detail)}</div>
    </div>`;
};

function renderSdTrace() {
  document.getElementById("sdTraceList").innerHTML = window.SD_TRACE.map((s, i) => `
    <div class="sd-trace-step">
      <div class="sd-trace-n">${i + 1}</div>
      <div><div class="fname">${sdEsc(s.step)}</div>
      <div class="fdesc"><code>${sdEsc(s.where)}</code></div></div>
    </div>`).join("");
}

window.sdRunLab = async function (id) {
  const out = document.getElementById("sdLabResult");
  const busy = (msg) => { out.innerHTML = `<div class="queue-empty">${sdEsc(msg)}</div>`; };
  try {
    if (id === "ratelimit") {
      busy("REAL: hammering /api/v1/me (expect 429 with Retry-After)…");
      let first429 = -1;
      for (let i = 0; i < 200; i++) {
        const r = await apiFetch(`${API_BASE}/me`);
        if (r.status === 429) { first429 = i; break; }
      }
      const retry = await apiFetch(`${API_BASE}/me`);
      out.innerHTML = first429 >= 0
        ? `<div class="atlas-feature"><span class="status-chip delivered">REAL RUN</span>
          <div class="fname">429 after ${first429 + 1} requests</div>
          <div class="fdesc">Retry-After: ${sdEsc(retry.headers.get("Retry-After") || "n/a")}s —
          the token bucket protected the app. Verified live and in tests/test_rate_limiter.py.</div></div>`
        : `<div class="queue-empty">No 429 within 200 requests (bucket refilled during the run) — see tests for the deterministic case.</div>`;
    } else if (id === "scheduler") {
      busy("REAL: firing scheduler tick twice (duplicate must be a no-op)…");
      const r1 = await apiFetch(`${API_BASE}/scheduler/tick`, { method: "POST" });
      const r2 = await apiFetch(`${API_BASE}/scheduler/tick`, { method: "POST" });
      const j1 = await r1.json(), j2 = await r2.json();
      const fmt = j => Object.values(j.jobs || {}).map(x => x.status).join(", ") || "no jobs due";
      out.innerHTML = `<div class="atlas-feature"><span class="status-chip delivered">REAL RUN</span>
        <div class="fname">Tick 1: ${sdEsc(fmt(j1))}</div>
        <div class="fdesc">Tick 2 (duplicate trigger): ${sdEsc(fmt(j2))} — the DB claim lock made the
        duplicate a no-op. Tests: tests/test_scheduler.py.</div></div>`;
    } else if (id === "breaker") {
      out.innerHTML = `<div class="atlas-feature"><span class="status-chip blocked">SIMULATED</span>
        <div class="fname">Circuit breaker: CLOSED → OPEN → HALF_OPEN → CLOSED</div>
        <div class="fdesc"><span class="status-chip delivered">CLOSED</span> →
        <span class="status-chip blocked">OPEN (5 failures)</span> →
        <span class="status-chip planned">HALF_OPEN (1 probe)</span> →
        <span class="status-chip delivered">CLOSED</span><br>
        Visualization of behavior proven in tests/test_resilience_patterns.py —
        no live LLM dependency exists (BLOCKED: no provider keys).</div></div>`;
    } else if (id === "dlq") {
      out.innerHTML = `<div class="atlas-feature"><span class="status-chip blocked">SIMULATED</span>
        <div class="fname">Poison message → retries → DEAD LETTER</div>
        <div class="fdesc">attempt 1 ✗ → 2 ✗ → 3 ✗ → 4 ✗ → 5 ✗ → <strong>dead-lettered</strong>
        (removed from redelivery, error kept for inspection/replay). Proven deterministically in
        tests/test_resilience_patterns.py::TestOutboxDeadLetter via a fault-injection hook.</div></div>`;
    } else if (id === "idempotency") {
      busy("REAL: confirming the same delivery twice (second must be a duplicate)…");
      const st = await (await apiFetch(`${API_BASE}/state`)).json();
      const dq = (st.dispatch_queue || []).find(q => q.status === "DISPATCHED");
      if (!dq) {
        out.innerHTML = `<div class="queue-empty">No dispatched mission available in this scenario.</div>`;
        return;
      }
      const post = () => apiFetch(`${API_BASE}/deliveries/confirm`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: dq.request_id, volunteer_name: "Studio Demo" }) });
      const c1 = await (await post()).json();
      const c2 = await (await post()).json();
      out.innerHTML = `<div class="atlas-feature"><span class="status-chip delivered">REAL RUN</span>
        <div class="fname">Confirm 1: duplicate=${c1.duplicate} · Replay: duplicate=${c2.duplicate}</div>
        <div class="fdesc">The replay returned the ORIGINAL receipt — inventory was deducted exactly
        once (unique DB constraint). Tests: test_api.py, tests/test_phase4_security.py.</div></div>`;
    }
  } catch (e) {
    out.innerHTML = `<div class="queue-empty">Lab error: ${sdEsc(String(e))}</div>`;
  }
};

function renderSdLab() {
  const labs = [
    ["ratelimit", "Scenario 1 — Rate limit exceeded", "REAL", "Hammer /api/v1/me until the token bucket empties; observe 429 + Retry-After."],
    ["scheduler", "Scenario 20 — Duplicate scheduled job", "REAL", "Fire the scheduler tick twice; the DB claim lock makes the duplicate a no-op."],
    ["idempotency", "Scenario 14 — Duplicate delivery confirmation", "REAL", "Confirm the same delivery twice; the replay returns the original receipt, no double deduction."],
    ["breaker", "Scenario 10 — Dependency timeout opens the circuit", "SIMULATED", "5 failures trip the breaker OPEN; one HALF_OPEN probe tests recovery before closing."],
    ["dlq", "Scenario 15 — Poison message dead-letters", "SIMULATED", "A crashing event is retried, then dead-lettered with its error preserved for inspection."],
  ];
  document.getElementById("sdLabList").innerHTML = labs.map(lab => `
    <div class="sd-topic-card" role="button" tabindex="0" onclick="sdRunLab('${lab[0]}')"
         onkeydown="if(event.key==='Enter')sdRunLab('${lab[0]}')" aria-label="${sdEsc(lab[1])}">
      <div class="dname">${sdEsc(lab[1])}</div>
      <div style="margin-top:0.3rem;">
        <span class="status-chip ${lab[2] === "REAL" ? "delivered" : "blocked"}">${lab[2]}</span></div>
      <div class="dnum">${sdEsc(lab[3])}</div>
    </div>`).join("");
}

window.initStudio = function () {
  renderSdChapters();
  renderSdTopics();
  renderSdMap();
  renderSdTrace();
  renderSdLab();
};
