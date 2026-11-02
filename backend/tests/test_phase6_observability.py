"""Phase VI topics 36-37 (+31 headers): tracing, redaction, SLI/SLO arithmetic, lab endpoints."""
import logging

import pytest

from app import advanced_lab_ext as E, telemetry

OBS = "observer@example.dev"
ADMIN = "ngo-admin@example.dev"


def test_traceparent_parsing():
    ok = telemetry.parse_traceparent("00-" + "a" * 32 + "-" + "b" * 16 + "-01")
    assert ok["source"] == "propagated" and ok["trace_id"] == "a" * 32 and ok["parent_span_id"] == "b" * 16
    for bad in ("garbage", "00-" + "0" * 32 + "-" + "b" * 16 + "-01", "00-short-bad-01", ""):
        r = telemetry.parse_traceparent(bad)
        assert r["trace_id"] != "0" * 32 and len(r["trace_id"]) == 32
        assert r["source"] in ("invalid_replaced", "generated")
    assert telemetry.parse_traceparent(None)["source"] == "generated"


def test_redaction_keys_and_patterns():
    out = telemetry.redact({"requester_name": "Maria", "sector": "North",
                            "msg": "call +63 917 555 0100 or maria@example.org", "nested": [{"phone": "1"}]})
    s = str(out)
    assert "Maria" not in s and "917" not in s and "maria@" not in s and out["sector"] == "North"


def test_spans_nest_and_share_trace():
    telemetry.reset()
    with telemetry.trace_context("c" * 32, None):
        with telemetry.span("outer") as o:
            with telemetry.span("inner"):
                pass
    sp = {s["name"]: s for s in telemetry.get_trace("c" * 32)["spans"]}
    assert sp["inner"]["parent_span_id"] == sp["outer"]["span_id"] and sp["outer"]["parent_span_id"] is None


def test_error_classification_and_propagation():
    telemetry.reset()
    with telemetry.trace_context("d" * 32, None):
        with pytest.raises(TimeoutError):
            with telemetry.span("boom"):
                raise TimeoutError("x")
    s = telemetry.get_trace("d" * 32)["spans"][0]
    assert s["status"] == "ERROR" and s["error_class"] == "timeout"


def test_no_trace_means_no_span_and_no_crash():
    telemetry.reset()
    with telemetry.span("orphan"):
        pass
    assert telemetry.snapshot()["spans_recorded"] == 0


def test_sampling_is_deterministic_and_respects_rate(monkeypatch):
    monkeypatch.setenv("TRACE_SAMPLE_RATE", "0")
    assert not telemetry.sampled("e" * 32)
    monkeypatch.setenv("TRACE_SAMPLE_RATE", "1")
    assert telemetry.sampled("e" * 32)
    monkeypatch.setenv("TRACE_SAMPLE_RATE", "0.5")
    decisions = [telemetry.sampled(f"{i:032x}") for i in range(400)]
    assert decisions == [telemetry.sampled(f"{i:032x}") for i in range(400)]
    assert 120 < sum(decisions) < 280


def test_instrumentation_failure_does_not_break_work(monkeypatch):
    telemetry.reset()
    monkeypatch.setattr(telemetry, "redact", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("bad")))
    with telemetry.trace_context("f" * 32, None):
        with telemetry.span("x", a=1):
            result = 41 + 1
    assert result == 42 and telemetry.INSTRUMENTATION_FAILURES["count"] >= 1


def test_log_filter_redacts_pii():
    rec = logging.LogRecord("t", logging.INFO, "p", 1, "contact maria@example.org at +63 917 555 0100", (), None)
    telemetry.RedactingFilter().filter(rec)
    assert "maria@" not in rec.getMessage() and "917" not in rec.getMessage()


def test_http_headers_trace_propagation_and_no_store(client):
    h = client.login(ADMIN)
    tp = "00-" + "1" * 32 + "-" + "2" * 16 + "-01"
    r = client.get("/api/v1/me", headers={**h, "traceparent": tp})
    assert r.headers["X-Trace-ID"] == "1" * 32 and r.headers["Cache-Control"] == "no-store" and r.headers["X-Request-ID"]
    r2 = client.get("/api/v1/me", headers=h)                      # missing traceparent => generated
    assert len(r2.headers["X-Trace-ID"]) == 32 and r2.headers["X-Trace-ID"] != "1" * 32
    spans = telemetry.get_trace("1" * 32)["spans"]
    assert any(s["name"] == "http.request" and s["parent_span_id"] == "2" * 16 for s in spans)


def test_static_assets_are_not_marked_no_store(client):
    r = client.get("/js/app.js")
    assert r.status_code == 200 and "no-store" not in r.headers.get("cache-control", "")
    assert r.headers.get("etag") or r.headers.get("last-modified")      # validators exist for edge caching
    cond = client.get("/js/app.js", headers={"If-None-Match": r.headers["etag"]}) if r.headers.get("etag") else None
    if cond is not None:
        assert cond.status_code == 304


def test_error_budget_arithmetic():
    b = E.error_budget(0.99, good=990, total=1000)
    assert b["bad_events"] == 10 and b["allowed_bad_events"] == 10 and b["budget_consumed_pct"] == 100.0 and b["within_slo"]
    assert E.error_budget(0.99, 980, 1000)["within_slo"] is False
    assert E.error_budget(0.99, 0, 0)["status"] == "NOT_MEASURED"
    assert E.error_budget(0.999, 100, 100)["budget_consumed_pct"] == 0.0


def test_sli_not_measured_when_sample_small():
    telemetry.reset()
    assert telemetry.snapshot()["api_sli"]["status"] == "NOT_MEASURED"


def test_sli_excludes_labs_health_and_counts_5xx():
    telemetry.reset()
    for _ in range(30):
        telemetry.record_request("/api/v1/requests", "GET", 200, 5.0, "t")
    for _ in range(10):
        telemetry.record_request("/api/v1/sd/lab/index", "POST", 500, 5.0, "t")   # excluded
        telemetry.record_request("/healthz", "GET", 500, 5.0, "t")                # excluded
    telemetry.record_request("/api/v1/requests", "GET", 503, 5.0, "t")
    s = telemetry.snapshot()["api_sli"]
    assert s["eligible_requests"] == 31 and s["good_requests"] == 30


def test_lab_endpoint_authz_and_unknown(client):
    assert client.post("/api/v1/sd/lab/secrets").status_code in (401, 403)
    obs = client.login(OBS)
    assert client.post("/api/v1/sd/lab/secrets", headers=obs).status_code == 403
    adm = client.login(ADMIN)
    assert client.post("/api/v1/sd/lab/nope", headers=adm).status_code == 404
    r = client.post("/api/v1/sd/lab/secrets", headers=adm)
    assert r.status_code == 200 and r.json()["run_label"].startswith("REAL_MEASURED")
    sim = client.post("/api/v1/sd/lab/region", headers=adm).json()
    assert sim["mode"] == "SIMULATED" and "SIMULATED" in sim["run_label"]


def test_telemetry_endpoint_requires_audit_permission(client):
    assert client.get("/api/v1/sd/telemetry", headers=client.login("volunteer@example.dev")).status_code == 403
    t = client.get("/api/v1/sd/telemetry", headers=client.login("auditor@example.dev"))
    assert t.status_code == 200 and "NONE" in t.json()["exporter"]
    assert client.get("/api/v1/sd/slo", headers=client.login("auditor@example.dev")).status_code == 200


def test_cdn_model_uses_real_headers(client):
    from app import advanced_runner
    r = advanced_runner.run("cdn")
    assert r["invariants"]["api_never_cached"] and r["mode"] == "SIMULATED"


def test_trace_demo_lab():
    r = E.trace_demo()
    assert all(r["invariants"].values()), r["invariants"]
    assert r["instrumentation_overhead_us_per_span"] >= 0
