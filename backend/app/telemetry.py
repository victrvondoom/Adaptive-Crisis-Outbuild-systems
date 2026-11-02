"""
AIDNEXUS ONE — Phase VI observability core (topic 36) + SLI source (topic 37).

IMPLEMENTED: in-process W3C-traceparent-compatible trace/span recording,
bounded ring buffers, PII redaction, request statistics for SLIs.
NOT IMPLEMENTED: export to an OpenTelemetry collector / Prometheus / Grafana.
The data model deliberately mirrors OpenTelemetry (trace_id 32 hex, span_id 16
hex, parent span, attributes, status) so an exporter can be added later
without re-instrumenting. Nothing here is fabricated: every number is derived
from requests actually served by this process since it started (in-memory;
lost on restart).
"""
from __future__ import annotations

import contextvars
import functools
import hashlib
import logging
import os
import re
import secrets
import threading
import time
from collections import deque
from contextlib import contextmanager
from typing import Any, Deque, Dict, Optional

_TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")
_SENSITIVE_KEYS = re.compile(
    r"(name|phone|msisdn|address|email|token|authorization|password|secret|signature|note|source_text|cookie)", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")

_trace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("trace_id", default=None)
_span_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("span_id", default=None)

SPAN_BUFFER: Deque[Dict[str, Any]] = deque(maxlen=int(os.environ.get("TELEMETRY_MAX_SPANS", "5000")))
REQUEST_BUFFER: Deque[Dict[str, Any]] = deque(maxlen=int(os.environ.get("TELEMETRY_MAX_REQUESTS", "5000")))
_lock = threading.Lock()
STARTED_AT = time.time()
INSTRUMENTATION_FAILURES = {"count": 0}


def sample_rate() -> float:
    try:
        return max(0.0, min(1.0, float(os.environ.get("TRACE_SAMPLE_RATE", "1.0"))))
    except ValueError:
        return 1.0


def sampled(trace_id: str) -> bool:
    """Deterministic head sampling: same trace_id always gets the same decision."""
    r = sample_rate()
    if r >= 1.0:
        return True
    return (int(hashlib.sha256(trace_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF) < r


def redact_text(s: str) -> str:
    return _PHONE.sub("[REDACTED_PHONE]", _EMAIL.sub("[REDACTED_EMAIL]", s))


def redact(obj: Any) -> Any:
    """Recursively masks values under sensitive keys and PII patterns in strings."""
    if isinstance(obj, dict):
        return {k: ("[REDACTED]" if _SENSITIVE_KEYS.search(str(k)) else redact(v)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


def parse_traceparent(header: Optional[str]) -> Dict[str, Any]:
    """Returns {trace_id, parent_span_id, source}. Invalid/absent headers produce a fresh
    trace (source='generated' or 'invalid_replaced') — never an exception."""
    if header:
        m = _TRACEPARENT.match(header.strip().lower())
        if m and m.group(1) != "0" * 32 and m.group(2) != "0" * 16:
            return {"trace_id": m.group(1), "parent_span_id": m.group(2), "source": "propagated"}
        return {"trace_id": secrets.token_hex(16), "parent_span_id": None, "source": "invalid_replaced"}
    return {"trace_id": secrets.token_hex(16), "parent_span_id": None, "source": "generated"}


def current_trace_id() -> Optional[str]:
    return _trace_id.get()


def current_traceparent() -> Optional[str]:
    t, s = _trace_id.get(), _span_id.get()
    return f"00-{t}-{s}-01" if t and s else None


def _classify(exc: BaseException) -> str:
    n = type(exc).__name__
    if "Timeout" in n:
        return "timeout"
    if "Integrity" in n:
        return "constraint_violation"
    if "Operational" in n:
        return "database_unavailable"
    return "internal_error"


@contextmanager
def trace_context(trace_id: str, parent_span_id: Optional[str] = None):
    t1 = _trace_id.set(trace_id)
    t2 = _span_id.set(parent_span_id)
    try:
        yield
    finally:
        _trace_id.reset(t1)
        _span_id.reset(t2)


@contextmanager
def span(name: str, **attrs: Any):
    """Records a span if a trace is active and sampled. Instrumentation failures never
    break the request (counted in INSTRUMENTATION_FAILURES)."""
    tid = _trace_id.get()
    if tid is None or not sampled(tid):
        yield None
        return
    sid = secrets.token_hex(8)
    parent = _span_id.get()
    tok = _span_id.set(sid)
    start = time.perf_counter()
    rec: Dict[str, Any] = {"trace_id": tid, "span_id": sid, "parent_span_id": parent, "name": name,
                           "attributes": {}, "status": "OK", "error_class": None}
    try:
        rec["attributes"] = redact(attrs)
    except Exception:  # noqa: BLE001
        INSTRUMENTATION_FAILURES["count"] += 1
    try:
        yield rec
    except BaseException as e:
        rec["status"] = "ERROR"
        rec["error_class"] = _classify(e)
        raise
    finally:
        rec["duration_ms"] = round((time.perf_counter() - start) * 1000, 3)
        rec["started_at"] = time.time()
        _span_id.reset(tok)
        try:
            with _lock:
                SPAN_BUFFER.append(rec)
        except Exception:  # noqa: BLE001
            INSTRUMENTATION_FAILURES["count"] += 1


def record_leaf_span(name: str, duration_ms: float, status: str = "OK", error_class=None, **attrs: Any) -> None:
    """Records an already-measured leaf span (no context switch; safe from DB event hooks)."""
    tid = _trace_id.get()
    if tid is None or not sampled(tid):
        return
    try:
        rec = {"trace_id": tid, "span_id": secrets.token_hex(8), "parent_span_id": _span_id.get(), "name": name,
               "attributes": redact(attrs), "status": status, "error_class": error_class,
               "duration_ms": round(duration_ms, 3), "started_at": time.time()}
        with _lock:
            SPAN_BUFFER.append(rec)
    except Exception:  # noqa: BLE001
        INSTRUMENTATION_FAILURES["count"] += 1


def traced(name: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            with span(name):
                return fn(*a, **kw)
        return wrapper
    return deco


_ID_SEG = re.compile(r"/(?:[A-Z]+-[\w-]+|[0-9a-f]{8,}|\d+)(?=/|$)")


def route_group(path: str) -> str:
    return _ID_SEG.sub("/{id}", path)


def record_request(path: str, method: str, status: int, duration_ms: float, trace_id: str) -> None:
    with _lock:
        REQUEST_BUFFER.append({"t": time.time(), "route": f"{method} {route_group(path)}",
                               "path": path, "status": status, "ms": duration_ms, "trace_id": trace_id})


def _pct(vals, p):
    s = sorted(vals)
    return s[max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))] if s else None


EXCLUDED_FROM_SLI = ("/healthz", "/readyz", "/api/v1/sd/", "/api/v1/benchmark/", "/api/v1/sim/")


def snapshot(min_samples: int = 20) -> Dict[str, Any]:
    """Real telemetry from this process. Returns NOT_MEASURED where the sample is too small."""
    with _lock:
        reqs, spans = list(REQUEST_BUFFER), list(SPAN_BUFFER)
    sli_reqs = [r for r in reqs if r["path"].startswith("/api/v1/")
                and not any(r["path"].startswith(x) for x in EXCLUDED_FROM_SLI)]
    out: Dict[str, Any] = {"source": "REAL_TELEMETRY (this process, in-memory)",
                           "uptime_s": round(time.time() - STARTED_AT, 1),
                           "requests_recorded": len(reqs), "spans_recorded": len(spans),
                           "sample_rate": sample_rate(),
                           "instrumentation_failures": INSTRUMENTATION_FAILURES["count"],
                           "exporter": "NONE (no OTel collector / Prometheus configured)"}
    if len(sli_reqs) < min_samples:
        out["api_sli"] = {"status": "NOT_MEASURED", "reason": f"only {len(sli_reqs)} eligible requests (< {min_samples})"}
    else:
        good = sum(1 for r in sli_reqs if r["status"] < 500)
        lat = [r["ms"] for r in sli_reqs]
        out["api_sli"] = {"status": "MEASURED", "eligible_requests": len(sli_reqs), "good_requests": good,
                          "availability": round(good / len(sli_reqs), 6),
                          "error_rate_5xx": round(1 - good / len(sli_reqs), 6),
                          "latency_ms": {"p50": round(_pct(lat, 50), 2), "p95": round(_pct(lat, 95), 2)}}
    by_route: Dict[str, list] = {}
    for r in sli_reqs:
        by_route.setdefault(r["route"], []).append(r["ms"])
    out["routes"] = sorted(({"route": k, "n": len(v), "p50_ms": round(_pct(v, 50), 2), "p95_ms": round(_pct(v, 95), 2)}
                            for k, v in by_route.items()), key=lambda x: -x["n"])[:15]
    by_span: Dict[str, list] = {}
    for sp in spans:
        by_span.setdefault(sp["name"], []).append(sp["duration_ms"])
    out["span_summary"] = sorted(({"span": k, "n": len(v), "p50_ms": round(_pct(v, 50), 3), "p95_ms": round(_pct(v, 95), 3)}
                                  for k, v in by_span.items()), key=lambda x: -x["n"])
    out["not_measured"] = ["queue lag (no external queue)", "model latency (deterministic agents, no LLM provider)",
                           "external provider health (no providers configured)"]
    return out


def get_trace(trace_id: str) -> Dict[str, Any]:
    with _lock:
        spans = [s for s in SPAN_BUFFER if s["trace_id"] == trace_id]
    return {"trace_id": trace_id, "spans": sorted(spans, key=lambda s: s["started_at"])}


def reset() -> None:
    with _lock:
        SPAN_BUFFER.clear()
        REQUEST_BUFFER.clear()
    INSTRUMENTATION_FAILURES["count"] = 0


class RedactingFilter(logging.Filter):
    """Masks emails/phones in any log message passing through the handler."""
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            red = redact_text(msg)
            if red != msg:
                record.msg, record.args = red, ()
        except Exception:  # noqa: BLE001
            INSTRUMENTATION_FAILURES["count"] += 1
        return True
