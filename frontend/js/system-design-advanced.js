/* AIDNEXUS System Design Studio — advanced layer (topics 21–40, Phase VI).
 * Renders data from system-design-advanced-data.js and calls POST /api/v1/sd/lab/{name}
 * (disposable-database experiments). All dynamic strings pass through sdEsc().
 * Knowledge-check scores live in memory only: no persistent learning progress is stored
 * (no per-user progress API exists, so nothing is claimed or kept). */
"use strict";

const advState = { track: "foundations", chapter: 0, scores: {} };

const ADV_STATUS_CLASS = {
  IMPLEMENTED: "delivered", TESTED: "delivered", VERIFIED: "delivered",
  MANAGED_BY_PLATFORM: "dispatched", PLANNED: "planned", SIMULATED: "blocked",
  BLOCKED: "blocked", NOT_REQUIRED: "blocked",
};
const ADV_STATUS_HELP = {
  IMPLEMENTED: "Code exists in this repository", TESTED: "Automated tests cover it",
  VERIFIED: "Measured by a lab run executed in this repo (artifact in benchmarks/phase6/)",
  MANAGED_BY_PLATFORM: "Expected to come from the hosting platform; not deployed here",
  SIMULATED: "Modelled with deterministic code; NOT live infrastructure",
  PLANNED: "Designed, not built", BLOCKED: "Needs an external dependency we do not have",
  NOT_REQUIRED: "Deliberately not adopted",
};

function advChips(list) {
  return (list || []).map(s =>
    `<span class="status-chip ${ADV_STATUS_CLASS[s] || "planned"}" title="${sdEsc(ADV_STATUS_HELP[s] || s)}">${sdEsc(s)}</span>`).join(" ");
}

window.sdSetTrack = function (track) {
  advState.track = track;
  advState.chapter = 0;
  document.getElementById("sdTrackFoundations").classList.toggle("active", track === "foundations");
  document.getElementById("sdTrackAdvanced").classList.toggle("active", track === "advanced");
  document.getElementById("sdAdvBanner").hidden = track !== "advanced";
  if (track === "foundations") {
    sdState.chapter = 0;
    renderSdChapters();
    renderSdTopics();
  } else {
    renderAdvChapters();
    renderAdvTopics();
  }
};

function renderAdvChapters() {
  document.getElementById("sdChapters").innerHTML =
    `<button class="sd-chapter ${advState.chapter === 0 ? "active" : ""}" onclick="advSelectChapter(0)" role="tab">All 21–40</button>` +
    window.SD_ADV_CHAPTERS.map(c =>
      `<button class="sd-chapter ${advState.chapter === c.n ? "active" : ""}" onclick="advSelectChapter(${c.n})" role="tab"
        aria-label="Advanced chapter ${c.n}: ${sdEsc(c.title)}">${c.n}. ${sdEsc(c.title)}</button>`).join("");
}

window.advSelectChapter = function (n) {
  advState.chapter = n;
  renderAdvChapters();
  renderAdvTopics();
};

function renderAdvTopics() {
  const list = document.getElementById("sdTopicList");
  document.getElementById("sdTopicDetail").hidden = true;
  list.hidden = false;
  const ch = window.SD_ADV_CHAPTERS.find(c => c.n === advState.chapter);
  const topics = window.SD_ADV_TOPICS.filter(t => !ch || ch.topics.includes(t.id));
  list.innerHTML = topics.map(t => `
    <div class="sd-topic-card" role="button" tabindex="0" onclick="advOpenTopic(${t.id})"
         onkeydown="if(event.key==='Enter')advOpenTopic(${t.id})" aria-label="Topic ${t.id}: ${sdEsc(t.title)}">
      <div class="dname">${t.id} · ${sdEsc(t.title)}</div>
      <div style="margin-top:0.3rem;">${advChips(t.status)}</div>
      <div class="dnum">${sdEsc(t.decision)} — ${sdEsc(t.problem.slice(0, 80))}…</div>
    </div>`).join("");
}

function advFlow(nodes, label) {
  return `<div class="sd-flow" role="img" aria-label="${sdEsc(label + ": " + nodes.join(" then "))}">` +
    nodes.map((n, i) => `<span class="sd-node">${sdEsc(n)}</span>${i < nodes.length - 1 ? '<span class="sd-arrow" aria-hidden="true">→</span>' : ""}`).join("") + `</div>`;
}

window.advOpenTopic = function (id) {
  const t = window.SD_ADV_TOPICS.find(x => x.id === id);
  if (!t) return;
  const ch = window.SD_ADV_CHAPTERS.find(c => c.topics.includes(id));
  document.getElementById("sdTopicList").hidden = true;
  const d = document.getElementById("sdTopicDetail");
  d.hidden = false;
  const row = (label, val) => `<div class="sd-field"><div class="sd-label">${label}</div><div class="sd-value">${val}</div></div>`;
  const list = (arr, tag = "ul") => `<${tag} class="sd-list">${arr.map(x => `<li>${sdEsc(x)}</li>`).join("")}</${tag}>`;
  d.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; gap:0.5rem; flex-wrap:wrap;">
      <h3 style="font-family:var(--font-heading); color:#fff; margin:0;">${t.id} · ${sdEsc(t.title)}</h3>
      <button class="btn-secondary" style="font-size:0.72rem;" onclick="advSelectChapter(${advState.chapter})" aria-label="Back to topics">← Back</button>
    </div>
    <p style="color:var(--text-secondary); font-size:0.8rem;">Advanced chapter ${ch.n} — ${sdEsc(ch.title)} ·
      Decision: <strong>${sdEsc(t.decision)}</strong></p>
    <div>${advChips(t.status)}</div>
    ${row("Plain-English definition", sdEsc(t.definition))}
    ${row("The problem", sdEsc(t.problem))}
    ${row("Analogy", sdEsc(t.analogy))}
    ${row("Architecture diagram", advFlow(t.diagram, "Architecture"))}
    ${row("Data flow", list(t.dataflow, "ol"))}
    ${row("AIDNEXUS application (what is real, what is not)", sdEsc(t.aidnexus))}
    ${row("Source references", list(t.source))}
    ${row("Technical example", `<pre class="sd-code">${sdEsc(t.code)}</pre>`)}
    ${row("Failure scenario", sdEsc(t.failure))}
    ${row("Performance trade-offs", sdEsc(t.perf))}
    ${row("Cost trade-offs", sdEsc(t.cost))}
    ${row("Security implications", sdEsc(t.security))}
    ${row("When to use it", sdEsc(t.whenUse))}
    ${row("When NOT to use it", sdEsc(t.whenNot))}
    ${row("Engineering takeaway", sdEsc(t.takeaway))}
    ${row("Executable tests", list(t.tests))}
    ${row("Benchmark methodology", sdEsc(t.benchmark))}
    ${row("Architecture decision reference", sdEsc(t.adr))}
    ${t.lab ? `<div class="sd-field"><div class="sd-label">Laboratory</div>
        <button class="btn-primary" onclick="sdRunAdvLab('${sdEsc(t.lab)}','advLabOut')" aria-label="Run the ${sdEsc(t.title)} lab">▶ Run lab: ${sdEsc(t.lab)}</button>
        <span style="font-size:0.72rem; color:var(--text-secondary);"> Runs on a disposable database on the server. Needs a role with optimization rights.</span>
        <div id="advLabOut" class="sd-lab-out" aria-live="polite"></div></div>` : ""}
    <div class="sd-field"><div class="sd-label">Knowledge check</div>
      <div id="advQuiz"></div>
      <div id="advScore" class="sd-value" aria-live="polite" style="font-size:0.78rem;"></div>
    </div>`;
  renderAdvQuiz(t);
  d.scrollIntoView({ behavior: "smooth", block: "start" });
};

function renderAdvQuiz(t) {
  const answered = advState.scores[t.id] = advState.scores[t.id] || {};
  document.getElementById("advQuiz").innerHTML = t.quiz.map((q, qi) => `
    <div class="sd-quiz" role="group" aria-label="Question ${qi + 1}">
      <div class="sd-quiz-q" style="cursor:default;">${qi + 1}. ${sdEsc(q.q)}</div>
      ${q.opts.map((o, oi) => `
        <button class="sd-opt ${answered[qi] === oi ? (o.ok ? "sd-ok" : "sd-bad") : ""}" onclick="advAnswer(${t.id},${qi},${oi})"
                ${answered[qi] !== undefined ? "disabled" : ""}>${sdEsc(o.t)}</button>
        ${answered[qi] !== undefined ? `<div class="sd-why ${o.ok ? "sd-why-ok" : "sd-why-bad"}">${o.ok ? "✓ Correct" : (answered[qi] === oi ? "✗ Your answer — not quite" : "✗ Why not")} — ${sdEsc(o.why)}</div>` : ""}
      `).join("")}
    </div>`).join("");
  const n = Object.keys(answered).length;
  const right = Object.entries(answered).filter(([qi, oi]) => t.quiz[qi].opts[oi].ok).length;
  document.getElementById("advScore").textContent =
    n ? `This session: ${right}/${n} correct (not saved anywhere).` : "Answer to see explanations for every wrong choice.";
}
window.advAnswer = function (tid, qi, oi) {
  const t = window.SD_ADV_TOPICS.find(x => x.id === tid);
  advState.scores[tid][qi] = oi;
  renderAdvQuiz(t);
};

/* ---------- lab runner + generic result renderer ---------- */
async function labFetch(name) {
  for (let attempt = 0; attempt < 4; attempt++) {
    const r = await apiFetch(`${API_BASE}/sd/lab/${encodeURIComponent(name)}`, { method: "POST" });
    if (r.status === 429) {
      const wait = Math.min(parseFloat(r.headers.get("Retry-After") || "10"), 20);
      await new Promise(res => setTimeout(res, wait * 1000));
      continue;
    }
    if (r.status === 403) throw new Error("Your role may not run labs (needs optimization rights, e.g. NGO admin).");
    if (!r.ok) throw new Error("Lab failed: HTTP " + r.status);
    return r.json();
  }
  throw new Error("Rate limited (expensive-compute budget). Wait a minute and retry.");
}

function advCompact(o) {
  if (o === null || typeof o !== "object") return String(o);
  return Object.entries(o).map(([k, v]) => {
    const s = (typeof v === "object" && v !== null) ? JSON.stringify(v) : String(v);
    return `${k}: ${s.length > 120 ? s.slice(0, 117) + "…" : s}`;
  }).join(" · ");
}

function renderLabResult(r) {
  const real = r.mode !== "SIMULATED";
  const chip = real ? `<span class="status-chip delivered">REAL MEASURED</span>` : `<span class="status-chip blocked">SIMULATED</span>`;
  const env = r.environment && r.environment.engine ? `${r.environment.engine}, ${r.environment.database}` : (r.environment && r.environment.note) || "";
  let html = `<div class="atlas-feature">${chip}
      <div class="fname">Topic ${sdEsc(r.topic)} lab — ${sdEsc(r.lab_name)} (${sdEsc(r.wall_ms)} ms wall)</div>
      <div class="fdesc">${sdEsc(r.run_label)}<br>Under test: <code>${sdEsc(r.implementation_under_test || "")}</code><br>Environment: ${sdEsc(env)}</div></div>`;
  if (r.invariants) {
    html += `<ul class="sd-list sd-inv" aria-label="Invariants">` + Object.entries(r.invariants).map(([k, v]) =>
      `<li class="${v ? "sd-inv-ok" : "sd-inv-bad"}">${v ? "✓" : "✗"} ${sdEsc(k.replace(/_/g, " "))}</li>`).join("") + `</ul>`;
  }
  if (r.verdicts) {   // index lab
    html += `<table class="sd-table"><caption>Before / after (median ms, ${sdEsc(r.repeats)} repeats, SQLite)</caption>
      <thead><tr><th>Query</th><th>Before</th><th>After</th><th>Speedup</th><th>Adopt?</th></tr></thead><tbody>` +
      Object.keys(r.verdicts).map(q => `<tr><td>${sdEsc(q)}<br><small>${sdEsc((r.before[q].plan || []).join(" | "))}<br>→ ${sdEsc((r.after[q].plan || []).join(" | "))}</small></td>
        <td>${sdEsc(r.before[q].timing.median_ms)}</td><td>${sdEsc(r.after[q].timing.median_ms)}</td>
        <td>${sdEsc(r.verdicts[q].median_speedup_x)}×</td><td>${r.verdicts[q].evidence_supports_index ? "✓ adopted" : "✗ rejected"}</td></tr>`).join("") + `</tbody></table>`;
  }
  for (const key of ["timeline", "steps", "log", "attempts", "checks"]) {
    if (Array.isArray(r[key])) {
      html += `<ol class="sd-list sd-steps" aria-label="${sdEsc(key)}">` + r[key].map(s => `<li>${sdEsc(advCompact(s))}</li>`).join("") + `</ol>`;
    }
  }
  if (r.policies) html += `<pre class="sd-code">${sdEsc(JSON.stringify(r.policies, null, 1))}</pre>`;
  if (r.spans) {
    html += `<div class="sd-label">Trace ${sdEsc(r.trace_id)}</div><ul class="sd-list">` +
      r.spans.map(s => `<li>${sdEsc(s.name)} — ${sdEsc(s.ms)} ms <small>(parent ${sdEsc((s.parent || "root").slice(0, 8))})</small></li>`).join("") + `</ul>`;
  }
  if (r.limitations) html += `<div class="sd-label">Limitations</div><ul class="sd-list">${r.limitations.map(x => `<li>${sdEsc(x)}</li>`).join("")}</ul>`;
  html += `<details><summary>Raw result (JSON)</summary><pre class="sd-code">${sdEsc(JSON.stringify(r, null, 1))}</pre></details>`;
  return html;
}

window.sdRunAdvLab = async function (name, outId) {
  const out = document.getElementById(outId);
  out.innerHTML = `<div class="queue-empty">Running ${sdEsc(name)} on a disposable database…</div>`;
  try { out.innerHTML = renderLabResult(await labFetch(name)); }
  catch (e) { out.innerHTML = `<div class="queue-empty">${sdEsc(e.message || String(e))}</div>`; }
};

/* ---------- Failure lab additions ---------- */
const ADV_LABS = [
  ["contention", "Topic 23 — Simultaneous inventory updates"], ["index", "Topic 22 — Indexed vs unindexed queries"],
  ["pool", "Topic 24 — Connection pool saturation"], ["replica", "Topic 25 — Stale replica (simulated)"],
  ["sharding", "Topic 26 — Shard routing & hot partitions (simulated)"], ["cap", "Topic 27 — Network partition (simulated)"],
  ["lease", "Topic 28 — Two workers, one lease"], ["storage", "Topic 30 — Authorised vs unauthorised file access"],
  ["cdn", "Topic 31 — Edge cache decisions (real headers, simulated edge)"], ["search", "Topic 32 — Search index lag"],
  ["realtime", "Topic 33 — Disconnect & reconnect (simulated)"], ["backpressure", "Topic 34 — Slow consumer"],
  ["schema", "Topic 35 — Expand / backfill / contract"], ["trace", "Topic 36 — One request, many services"],
  ["slo", "Topic 37 — Error budget from measured traffic"], ["secrets", "Topic 38 — Rotate a test credential"],
  ["region", "Topic 39 — Regional outage (simulated)"], ["backup", "Topic 40 — Restore a disposable backup"],
  ["integrity", "Topic 21 — Constraint probes"],
];
const ADV_LAB_SIM = new Set(["replica", "sharding", "cap", "cdn", "realtime", "region"]);

function renderAdvLabCards() {
  const host = document.getElementById("sdLabList");
  host.insertAdjacentHTML("beforeend", ADV_LABS.map(([id, title]) => `
    <div class="sd-topic-card" role="button" tabindex="0" onclick="sdRunAdvLab('${id}','sdLabResult')"
         onkeydown="if(event.key==='Enter')sdRunAdvLab('${id}','sdLabResult')" aria-label="${sdEsc(title)}">
      <div class="dname">${sdEsc(title)}</div>
      <div style="margin-top:0.3rem;"><span class="status-chip ${ADV_LAB_SIM.has(id) ? "blocked" : "delivered"}">${ADV_LAB_SIM.has(id) ? "SIMULATED" : "REAL (disposable DB)"}</span></div>
    </div>`).join(""));
}

/* ---------- Architecture explorer additions ---------- */
function renderAdvMap() {
  document.getElementById("sdMapGrid").insertAdjacentHTML("beforeend", window.SD_ADV_MAP.map((c, i) => `
    <div class="sd-map-card" role="button" tabindex="0" onclick="advMapDetail(${i})"
         onkeydown="if(event.key==='Enter')advMapDetail(${i})" aria-label="Inspect component ${sdEsc(c.name)}">
      <div class="sd-area">Advanced</div><div class="dname">${sdEsc(c.name)}</div>
      <div style="margin-top:0.3rem;">${advChips(c.status)}</div></div>`).join(""));
}
window.advMapDetail = function (i) {
  const c = window.SD_ADV_MAP[i];
  const f = (l, v) => `<tr><th scope="row">${l}</th><td>${sdEsc(v)}</td></tr>`;
  document.getElementById("sdMapDetail").innerHTML = `
    <div class="atlas-feature"><div class="fname">${sdEsc(c.name)}</div><div>${advChips(c.status)}</div>
    <table class="sd-table"><tbody>
      ${f("Responsibility", c.resp)}${f("Source path", c.src)}${f("Configuration", c.cfg)}${f("API reference", c.api)}
      ${f("Database dependencies", c.dbdep)}${f("Security boundary", c.sec)}${f("Failure mode", c.fail)}
      ${f("Tests", c.tests)}${f("Benchmark", c.bench)}${f("Decision record", c.adr)}
    </tbody></table>
    <div class="fdesc">No secret values are ever shown. SIMULATED / PLANNED / NOT_REQUIRED components are not live infrastructure.</div></div>`;
};

/* ---------- Production engineering (real telemetry) ---------- */
window.sdLoadProd = async function () {
  const out = document.getElementById("sdProdLive");
  out.innerHTML = `<div class="queue-empty">Loading REAL process telemetry…</div>`;
  try {
    const [tr, sr] = await Promise.all([apiFetch(`${API_BASE}/sd/telemetry`), apiFetch(`${API_BASE}/sd/slo`)]);
    if (tr.status === 403) { out.innerHTML = `<div class="queue-empty">Telemetry needs audit-read permission (auditor / NGO admin).</div>`; return; }
    const t = await tr.json(), s = await sr.json();
    const sli = t.api_sli;
    const slo = s.api_availability;
    out.innerHTML = `
      <div class="atlas-feature"><span class="status-chip delivered">REAL TELEMETRY</span>
        <div class="fname">This process, uptime ${sdEsc(t.uptime_s)} s — ${sdEsc(t.requests_recorded)} requests, ${sdEsc(t.spans_recorded)} spans</div>
        <div class="fdesc">${sli.status === "MEASURED"
          ? `Availability SLI ${sdEsc(sli.availability)} (${sdEsc(sli.good_requests)}/${sdEsc(sli.eligible_requests)}) · p50 ${sdEsc(sli.latency_ms.p50)} ms · p95 ${sdEsc(sli.latency_ms.p95)} ms`
          : `NOT MEASURED — ${sdEsc(sli.reason)}`}</div>
        <div class="fdesc">Exporter: ${sdEsc(t.exporter)}. Not measured: ${sdEsc((t.not_measured || []).join("; "))}.</div></div>
      <div class="atlas-feature"><span class="status-chip blocked">CANDIDATE OBJECTIVE (not an SLA)</span>
        <div class="fname">Error budget vs ${sdEsc(s.candidate_slo)} — ${sdEsc(s.window)}</div>
        <div class="fdesc">${slo.status === "MEASURED"
          ? `Budget consumed ${sdEsc(slo.budget_consumed_pct)}% (${sdEsc(slo.bad_events)} bad of ${sdEsc(slo.allowed_bad_events)} allowed); within SLO: ${sdEsc(slo.within_slo)}`
          : "NOT MEASURED — not enough eligible requests yet. Use the app, then refresh."}</div></div>
      <table class="sd-table"><caption>Slowest routes (real, p95)</caption><thead><tr><th>Route</th><th>n</th><th>p50 ms</th><th>p95 ms</th></tr></thead><tbody>
      ${(t.routes || []).map(r => `<tr><td>${sdEsc(r.route)}</td><td>${sdEsc(r.n)}</td><td>${sdEsc(r.p50_ms)}</td><td>${sdEsc(r.p95_ms)}</td></tr>`).join("")}</tbody></table>
      <table class="sd-table"><caption>Span summary (db.query, optimizer, agents)</caption><thead><tr><th>Span</th><th>n</th><th>p50 ms</th><th>p95 ms</th></tr></thead><tbody>
      ${(t.span_summary || []).map(r => `<tr><td>${sdEsc(r.span)}</td><td>${sdEsc(r.n)}</td><td>${sdEsc(r.p50_ms)}</td><td>${sdEsc(r.p95_ms)}</td></tr>`).join("")}</tbody></table>`;
  } catch (e) { out.innerHTML = `<div class="queue-empty">${sdEsc(e.message || String(e))}</div>`; }
};

function renderProdMatrix() {
  document.getElementById("sdProdMatrix").innerHTML = `<table class="sd-table"><caption>Decision & status per advanced topic</caption>
    <thead><tr><th>#</th><th>Topic</th><th>Decision</th><th>Status</th></tr></thead><tbody>` +
    window.SD_ADV_TOPICS.map(t => `<tr><td>${t.id}</td><td>${sdEsc(t.title)}</td><td>${sdEsc(t.decision)}</td><td>${advChips(t.status)}</td></tr>`).join("") + `</tbody></table>`;
}

/* ---------- Benchmark laboratory ---------- */
const BENCH_EXTRACT = {
  index: r => Object.keys(r.verdicts).map(q => [`22 · ${q.split(" (")[0]}`, `${r.before[q].timing.median_ms} → ${r.after[q].timing.median_ms} ms median (p95 ${r.before[q].timing.p95_ms} → ${r.after[q].timing.p95_ms}), ${r.verdicts[q].median_speedup_x}×`, r.verdicts[q].evidence_supports_index ? "adopted" : "rejected"]),
  contention: r => [["23 · 24 writers, one row", `median ${r.latency.median_ms} ms, p95 ${r.latency.p95_ms} ms; ok=${r.outcomes.ok}, rejected=${r.outcomes.rejected_negative}, final stock=${r.final_stock}`, "invariants " + (Object.values(r.invariants).every(Boolean) ? "held" : "VIOLATED")]],
  pool: r => [["24 · pool wait", `median ${r.pool_wait.median_ms} ms, p95 ${r.pool_wait.p95_ms} ms; served ${r.outcomes.served}, timed out ${r.outcomes.timed_out}`, "no leaks: " + r.invariants.no_leaks]],
  search: r => [["32 · FTS query", `median ${r.query_latency.median_ms} ms, p95 ${r.query_latency.p95_ms} ms (${r.docs} docs)`, "invariants " + (Object.values(r.invariants).every(Boolean) ? "held" : "VIOLATED")]],
  backpressure: r => Object.entries(r.policies).filter(([k]) => k !== "cancellation").map(([k, v]) => [`34 · ${k}`, `delivered ${v.delivered}/${v.produced}, dropped ${v.dropped}, peak depth ${v.peak_queue_depth}, producer ${v.producer_elapsed_ms} ms`, ""]),
  trace: r => [["36 · span overhead", `${r.instrumentation_overhead_us_per_span} µs/span; ${r.trace_coverage.spans} spans, ${r.trace_coverage.linked_to_parent} linked`, ""]],
  backup: r => [["40 · backup→restore→validate", `backup ${r.backup_ms} ms, restore+validate ${r.measured_restore_and_validate_ms} ms, events lost after backup: ${r.events_lost_after_backup}`, "tiny disposable DB — not a production RTO"]],
  storage: r => [["30 · hostile uploads/downloads", `${r.attempts.filter(a => !a.allowed).length} of ${r.attempts.length} attempts denied (expected 8)`, ""]],
};
window.sdRunBench = async function () {
  const out = document.getElementById("sdBenchOut");
  const rows = [];
  for (const name of Object.keys(BENCH_EXTRACT)) {
    out.innerHTML = `<div class="queue-empty">Running ${sdEsc(name)} (${rows.length}/${Object.keys(BENCH_EXTRACT).length} done)… labs share a rate limit; waits are normal.</div>`;
    try { const r = await labFetch(name); rows.push(...BENCH_EXTRACT[name](r)); }
    catch (e) { rows.push([name, "ERROR: " + (e.message || e), ""]); }
  }
  out.innerHTML = `<div class="atlas-feature"><span class="status-chip delivered">REAL MEASURED — just now</span>
      <div class="fdesc">Single run each on this server (SQLite, disposable DBs). Reproducible multi-run artifacts: <code>benchmarks/phase6/</code> via <code>python -m app.advanced_runner</code>. p99 is NOT_MEASURED where n&lt;100.</div></div>
    <table class="sd-table"><caption>Benchmark laboratory results</caption><thead><tr><th>Experiment</th><th>Measurement</th><th>Note</th></tr></thead><tbody>
    ${rows.map(r => `<tr><td>${sdEsc(r[0])}</td><td>${sdEsc(r[1])}</td><td>${sdEsc(r[2])}</td></tr>`).join("")}</tbody></table>`;
};

/* ---------- wiring ---------- */
(function () {
  const baseInit = window.initStudio;
  window.initStudio = function () {
    baseInit();
    renderAdvLabCards();
    renderAdvMap();
    renderProdMatrix();
  };
})();
