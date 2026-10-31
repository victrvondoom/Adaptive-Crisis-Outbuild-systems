"""Phase II Milestone 5 tests: agent runtime, context envelopes, provider
abstraction, schema validation, postcondition verification, execution
persistence, and honest provider labeling."""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agents_runtime import (ContextEnvelope, DeterministicProvider, HttpLLMProvider,
                                ProviderError, SchemaValidationError, resolve_provider,
                                run_action, validate_schema, CONTEXT_ENVELOPE_VERSION)


class TestContextEnvelope:
    def _envelope(self, **kw):
        defaults = dict(organization_id="ORG-A", actor_id="U1", actor_role="NGO_ADMIN",
                        mission_id=None, mission_plan_version="v1.0",
                        optimization_run_id="opt-1", policy_version="policy-2026-11-v1",
                        data_snapshot_timestamp=time.time())
        defaults.update(kw)
        return ContextEnvelope(**defaults)

    def test_fresh_context_passes(self):
        e = self._envelope()
        assert e.check_freshness(time.time(), "v1.0", "policy-2026-11-v1") is True
        assert e.stale is False

    def test_stale_snapshot_detected(self):
        e = self._envelope(data_snapshot_timestamp=time.time() - 9999)
        assert e.check_freshness(time.time(), "v1.0", "policy-2026-11-v1") is False
        assert any("TTL" in r for r in e.staleness_reasons)

    def test_plan_version_change_detected(self):
        e = self._envelope(mission_plan_version="v2.0")
        assert e.check_freshness(time.time(), "v3.0", "policy-2026-11-v1") is False
        assert any("plan version" in r for r in e.staleness_reasons)

    def test_policy_version_change_detected(self):
        e = self._envelope(policy_version="policy-old")
        assert e.check_freshness(time.time(), "v1.0", "policy-new") is False

    def test_roundtrip_serialization(self):
        e = self._envelope()
        d = e.to_dict()
        e2 = ContextEnvelope.from_dict(d)
        assert e2.organization_id == "ORG-A"
        assert e2.context_version == CONTEXT_ENVELOPE_VERSION


class TestSchemaValidation:
    def test_valid_output_passes(self):
        validate_schema({"a": "x", "b": True},
                        {"type": "object", "required": ["a"],
                         "properties": {"a": {"type": "string"},
                                        "b": {"type": "boolean"}}})

    def test_missing_required_rejected(self):
        with pytest.raises(SchemaValidationError, match="missing required"):
            validate_schema({}, {"type": "object", "required": ["a"]})

    def test_wrong_type_rejected(self):
        with pytest.raises(SchemaValidationError):
            validate_schema({"a": 5}, {"type": "object",
                                       "properties": {"a": {"type": "string"}}})

    def test_array_items_validated(self):
        with pytest.raises(SchemaValidationError):
            validate_schema({"a": [1, "x"]},
                            {"type": "object", "properties": {"a": {
                                "type": "array", "items": {"type": "number"}}}})


class TestProviderResolution:
    def test_deterministic_without_keys(self, monkeypatch):
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert isinstance(resolve_provider(), DeterministicProvider)

    def test_mistral_selected_when_key_present(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-key-value")
        p = resolve_provider()
        assert p.name == "mistral" and isinstance(p, HttpLLMProvider)


class TestRunAction:
    def _ctx(self):
        return ContextEnvelope(organization_id="ORG-X", actor_id="U1",
                               actor_role="MISSION_COORDINATOR", mission_id=None,
                               mission_plan_version="v1.0", optimization_run_id=None,
                               policy_version="p1", data_snapshot_timestamp=time.time())

    def test_success_requires_postcondition(self):
        created = []
        def handler(ctx):
            created.append("R1")
            return {"request": {"id": "R1"}, "requires_human_review": False}
        def postcondition(out):
            return out["request"]["id"] in created
        rec = run_action("AGENT-01", "CREATE_AID_REQUEST", "ORG-X", self._ctx(),
                         "prompt", {"type": "object", "required": ["request"]},
                         handler, postcondition, persist=False)
        assert rec["status"] == "SUCCEEDED"
        assert rec["postcondition_ok"] is True
        assert rec["provider"] == "deterministic"  # honest label

    def test_failed_postcondition_marks_failure(self):
        def handler(ctx):
            return {"request": {"id": "R1"}, "requires_human_review": False}
        rec = run_action("AGENT-01", "CREATE_AID_REQUEST", "ORG-X", self._ctx(),
                         "p", {"type": "object", "required": ["request"]},
                         handler, postcondition=lambda out: False, persist=False)
        assert rec["status"] == "FAILED"
        assert rec["postcondition_ok"] is False
        assert "postcondition" in rec["error"]

    def test_review_required_is_not_failure(self):
        def handler(ctx):
            return {"request": {"id": "R1"}, "requires_human_review": True}
        rec = run_action("AGENT-01", "CREATE_AID_REQUEST", "ORG-X", self._ctx(),
                         "p", {"type": "object",
                               "required": ["request", "requires_human_review"]},
                         handler, postcondition=lambda out: True, persist=False)
        assert rec["status"] == "REVIEW_REQUIRED"

    def test_provider_failure_persists_and_raises(self, monkeypatch):
        class FailingProvider:
            name = "mistral"
            model = "test-model"
            def complete(self, prompt, schema, context, handler):
                raise ProviderError("provider failed after 2 attempts: network: TimeoutException")
        monkeypatch.setattr("app.agents_runtime.resolve_provider", lambda: FailingProvider())
        with pytest.raises(ProviderError):
            run_action("AGENT-01", "CREATE_AID_REQUEST", "ORG-X", self._ctx(),
                       "p", {"type": "object", "required": ["request"]},
                       handler=lambda ctx: {}, postcondition=lambda o: True,
                       persist=False)

    def test_execution_record_fields(self):
        rec = run_action("AGENT-02", "RUN_OPTIMIZATION", "ORG-X", self._ctx(),
                         "p", {"type": "object", "required": ["ok"]},
                         handler=lambda ctx: {"ok": True},
                         postcondition=lambda o: o["ok"], persist=False)
        for field in ("execution_id", "org_id", "agent_id", "action_id",
                      "provider", "status", "latency_ms", "context"):
            assert field in rec
        assert rec["context"]["organization_id"] == "ORG-X"


class TestTriageViaAPI:
    def test_triage_executes_via_runtime_with_verified_postcondition(self, client):
        """Full-stack: the triage endpoint now runs through the agent runtime;
        success is backed by a persisted request in the correct tenant."""
        r = client.post("/api/v1/nlp/triage", headers=client.login("coordinator@example.dev"),
                        json={"raw_text": "urgent need 100 liters water"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("SUCCEEDED", "REVIEW_REQUIRED")
        assert data["provider"] == "deterministic"
        assert data["execution_id"].startswith("exec-")
        rid = data["request"]["id"]
        # Postcondition evidence: the request is readable from the same tenant
        r2 = client.get(f"/api/v1/missions/{rid}",
                        headers=client.login("coordinator@example.dev"))
        assert r2.status_code == 200
        # ...and NOT from another tenant
        r3 = client.get(f"/api/v1/missions/{rid}",
                        headers=client.login("rival-coordinator@example.dev",
                                             org="ORG-HIGHLAND"))
        assert r3.status_code == 403 or r3.status_code == 404
