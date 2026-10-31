"""State machine enforcement: legal/illegal transitions, terminal states,
idempotent delivery, audit chain integrity."""
import pytest
from app.models import MissionStatus, ActorType
from app.state_engine import CrisisStateEngine


class TestTransitions:
    def test_legal_transition_succeeds(self, engine):
        req = engine.requests["REQ-050"]
        assert req.status == MissionStatus.VERIFIED
        res = engine.transition_mission("REQ-050", MissionStatus.PLANNED, "coord", "test")
        assert res["success"] is True
        assert engine.requests["REQ-050"].status == MissionStatus.PLANNED

    def test_illegal_transition_rejected(self, engine):
        with pytest.raises(ValueError, match="Illegal transition"):
            engine.transition_mission("REQ-050", MissionStatus.DELIVERED, "attacker")

    def test_delivered_is_terminal(self, engine):
        req = next(r for r in engine.requests.values() if r.is_delivered)
        with pytest.raises(ValueError):
            engine.transition_mission(req.id, MissionStatus.REQUESTED, "x")
        with pytest.raises(ValueError):
            engine.transition_mission(req.id, MissionStatus.DISPATCHED, "x")

    def test_cancelled_is_terminal(self, engine):
        engine.transition_mission("REQ-050", MissionStatus.CANCELLED, "coord")
        with pytest.raises(ValueError):
            engine.transition_mission("REQ-050", MissionStatus.DISPATCHED, "x")

    def test_delivered_via_raw_transition_forbidden(self, engine):
        engine.transition_mission("REQ-050", MissionStatus.PLANNED, "coord")
        engine.transition_mission("REQ-050", MissionStatus.PENDING_APPROVAL, "coord")
        engine.transition_mission("REQ-050", MissionStatus.APPROVED, "coord")
        # DISPATCHED -> DELIVERED is legal in the table, but must be refused
        # because delivery requires confirm (inventory + receipt handling).
        engine.transition_mission("REQ-050", MissionStatus.DISPATCHED, "coord")
        with pytest.raises(ValueError, match="delivery confirmation"):
            engine.transition_mission("REQ-050", MissionStatus.DELIVERED, "coord")

    def test_unknown_request_rejected(self, engine):
        with pytest.raises(ValueError, match="not found"):
            engine.transition_mission("NOPE", MissionStatus.PLANNED, "x")


class TestIdempotentDelivery:
    def test_double_confirmation_deducts_inventory_once(self, engine):
        req = next(r for r in engine.requests.values()
                    if r.status == MissionStatus.DISPATCHED and r.assigned_depot_id)
        depot = engine.depots[req.assigned_depot_id]
        item = req.items[0]
        before = depot.inventory[item.item_type]
        r1 = engine.confirm_delivery(req.id, "Volunteer A")
        after1 = depot.inventory[item.item_type]
        r2 = engine.confirm_delivery(req.id, "Volunteer A")
        after2 = depot.inventory[item.item_type]
        assert after1 == before - item.quantity
        assert after2 == after1  # no second deduction
        assert r2["duplicate"] is True

    def test_cancelled_request_cannot_be_delivered(self, engine):
        engine.transition_mission("REQ-050", MissionStatus.CANCELLED, "coord")
        with pytest.raises(ValueError, match="cancelled"):
            engine.confirm_delivery("REQ-050", "Volunteer A")

    def test_delivery_receipt_exists_with_signature_hash(self, engine):
        req = next(r for r in engine.requests.values()
                   if r.status == MissionStatus.DISPATCHED)
        res = engine.confirm_delivery(req.id, "Volunteer A", "sig-data")
        assert res["signature_hash"]
        assert engine.requests[req.id].status == MissionStatus.DELIVERED
        assert engine.requests[req.id].is_delivered is True


class TestAuditChain:
    def test_events_are_hash_chained(self, engine):
        evs = engine.audit_events
        assert all(e.prev_hash for e in evs[1:])  # every event after genesis links
        for i in range(1, len(evs)):
            assert evs[i].prev_hash == evs[i - 1].sha256_hash

    def test_every_event_has_hash(self, engine):
        assert all(e.sha256_hash for e in engine.audit_events)

    def test_sim_delivery_logs_audit(self, engine):
        before = len(engine.audit_events)
        # run enough ticks for at least one arrival
        for _ in range(4000):
            engine.advance_simulation(delta_sec=30.0)
        delivery_events = [e for e in engine.audit_events
                           if e.event_type == "DELIVERY_CONFIRMED"]
        assert len(delivery_events) >= 1
        assert len(engine.audit_events) >= before


class TestPlanVersioning:
    def test_sequential_versions_and_approval_flow(self, engine):
        from app.models import DisruptionType
        engine.inject_disruption(DisruptionType.DEPOT_OUTAGE, "Flood", "d",
                                 depot_id="DEPOT-BRAVO", lat=14.55, lng=120.94)
        assert engine.pending_plan_id == "v2.0"
        engine.approve_pending_plan("Coordinator")
        assert engine.current_plan_id == "v2.0"
        # second disruption -> v3, pending plan NOT overwritten silently
        engine.inject_disruption(DisruptionType.ROAD_BLOCKAGE, "Bridge", "d",
                                 lat=14.62, lng=120.98)
        assert engine.pending_plan_id == "v3.0"
        assert "v2.0" in engine.plans and engine.plans["v2.0"].is_approved
        engine.approve_pending_plan("Coordinator")
        assert engine.current_plan_id == "v3.0"

    def test_approval_without_pending_plan_rejected(self, engine):
        with pytest.raises(ValueError, match="No pending plan"):
            engine.approve_pending_plan("x")

    def test_double_approval_rejected(self, engine):
        from app.models import DisruptionType
        engine.inject_disruption(DisruptionType.ROAD_BLOCKAGE, "B", "d", lat=14.6, lng=120.98)
        engine.approve_pending_plan("C")
        # The approved plan is no longer pending; a second approval must fail.
        with pytest.raises(ValueError, match="No pending plan|already approved"):
            engine.approve_pending_plan("C")

    def test_delivered_requests_immutable_across_replan(self, engine):
        from app.models import DisruptionType
        delivered_before = {r.id: r.delivery_timestamp for r in engine.requests.values()
                             if r.is_delivered}
        engine.inject_disruption(DisruptionType.DEPOT_OUTAGE, "Flood", "d",
                                 depot_id="DEPOT-BRAVO", lat=14.55, lng=120.94)
        engine.approve_pending_plan("C")
        for rid, ts in delivered_before.items():
            req = engine.requests[rid]
            assert req.is_delivered is True
            assert req.delivery_timestamp == ts


class TestVolunteers:
    def test_volunteers_assigned_to_vehicles(self, engine):
        assigned = [v for v in engine.volunteers.values() if v.assigned_vehicle_id]
        assert len(assigned) > 0
        # every assigned vehicle has an assigned volunteer with medical role
        # only when the vehicle type is medical
        for vol in assigned:
            veh = engine.vehicles[vol.assigned_vehicle_id]
            if veh.vehicle_type == "Medical Evac Van":
                assert vol.role in ("Paramedic Lead", "Emergency Nurse")

    def test_requests_reference_assigned_volunteer(self, engine):
        for req in engine.requests.values():
            if req.status == MissionStatus.DISPATCHED and req.assigned_vehicle_id:
                assert req.assigned_volunteer_id is not None
