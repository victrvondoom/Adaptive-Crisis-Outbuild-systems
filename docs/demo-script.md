# Demo Script — AIDNEXUS ONE (5-Minute Demonstration)

## Pre-Demo Checklist
- [ ] Scenario reset executed (clean state)
- [ ] 200 requests seeded (seed=42)
- [ ] 3 warehouses operational, inventory loaded
- [ ] 10 vehicles available
- [ ] 12 volunteers confirmed
- [ ] AI provider connected (or fallback mode visible)
- [ ] All screens accessible and responsive

---

## Timeline

### 00:00 – 00:35 | THE PROBLEM (35 seconds)

**Narrator**: "After a devastating flood, three nonprofit organizations must coordinate relief for 200 displaced families across five regions. They have three warehouses, limited inventory, ten vehicles, and twelve volunteer teams. The challenge: how do you allocate scarce resources fairly, efficiently, and accountably — and what happens when a warehouse goes down?"

**On screen**: Mission Command Dashboard showing:
- 200 incoming requests
- 3 warehouse markers on map
- Demand heatmap across regions
- Inventory warnings (medicine running low)

---

### 00:35 – 01:10 | INTELLIGENT REQUEST PROCESSING (35 seconds)

**Narrator**: "Requests arrive as unstructured text. Our AI agent interprets each one, extracts specific items and quantities, detects duplicates, and flags uncertain cases for human review."

**On screen**: 
1. Show a raw request: *"Our community of 30 families in the northern district desperately needs 50kg of rice, 200 liters of clean water, and blankets. Children haven't eaten in two days."*
2. Switch to Agent Mission Control — show Agent 1 trace:
   - ExtractAidItems → Rice 50kg, Water 200L, Blankets 30
   - ClassifyUrgency → CRITICAL (children, 2 days)
   - Confidence: 0.92
3. Show the structured AidRequestItem records created
4. Show one flagged-for-review case: "Agent wasn't sure about this request — sent to you for review."

---

### 01:10 – 02:00 | OPTIMIZED ALLOCATION PLAN (50 seconds)

**Narrator**: "With verified requests, our Resource Strategist agent invokes a mathematical optimizer — Google OR-Tools solving a multi-depot vehicle routing problem with inventory constraints."

**On screen**:
1. Click "Generate Mission Plan" button
2. Show optimization running (loading state with progress)
3. Plan appears: 
   - 180 of 200 requests fulfilled (90%)
   - 45 of 47 critical requests fulfilled (96%)
   - Total distance: 1,234 km
   - 20 requests unmet due to inventory constraints
4. Show assignment details — which depot, which vehicle, which volunteer
5. Show the 20 unmet requests explicitly: "These families could not be served. Here's why: insufficient medicine inventory."

**Key talking point**: "The optimizer prioritizes critical humanitarian needs over travel efficiency. It never silently drops a request."

---

### 02:00 – 02:30 | WAREHOUSE FAILURE (30 seconds)

**Narrator**: "The coordinator approves the plan. Dispatches begin. Then — Warehouse B floods. One-third of our supply chain just disappeared."

**On screen**:
1. Click "Approve Plan" on Approval Center → plan approved, dispatches created
2. Switch to Digital Twin screen
3. Click "Inject Failure: Warehouse B"
4. Map shows Warehouse B turn red with alert icon
5. Alert appears: "⚠️ DISRUPTION: Warehouse B unavailable — 62 assignments affected"

---

### 02:30 – 03:15 | INTELLIGENT RECOVERY (45 seconds)

**Narrator**: "This is where AIDNEXUS differs from every other system. Our Recovery Agent automatically identifies affected assignments, preserves completed deliveries, and generates a recovery plan."

**On screen**:
1. Agent 3 trace shows:
   - GetAffectedAssignments → 62 assignments impacted
   - GetCompletedDeliveries → 15 already delivered (preserved ✓)
   - RequestReplanning → optimizer re-runs with Warehouse B disabled
2. **Side-by-side comparison** appears:
   - BEFORE: 180 fulfilled, 1,234 km
   - AFTER: 165 fulfilled, 1,456 km
   - 15 requests newly unmet (honest reporting)
   - 32 assignments reassigned to Warehouses A and C
   - 15 completed deliveries preserved (immutable)
3. Show the tradeoff explanation: "Recovery redistributes 32 assignments. 15 families cannot be served from remaining depots due to distance and inventory limits."

---

### 03:15 – 04:00 | HUMAN APPROVAL & DISPATCH (45 seconds)

**Narrator**: "No AI-generated plan changes real operations without human authorization."

**On screen**:
1. Recovery plan in Approval Center with diff highlights
2. Coordinator reviews:
   - Green rows: preserved assignments
   - Blue rows: reassigned assignments
   - Red rows: newly unmet demand
3. Click "Approve Recovery Plan"
4. Assignments update — volunteers receive revised missions
5. Switch to Field Operations (mobile view):
   - Volunteer sees updated assignment
   - Click "Confirm Delivery" → delivery receipt created
6. Show the immutable audit trail:
   - "10:23 Disruption detected | 10:24 Recovery plan generated | 10:25 Plan approved by Coordinator Maria | 10:26 Assignments updated"

---

### 04:00 – 04:30 | MEASURED IMPACT (30 seconds)

**Narrator**: "Every claim is backed by computed evidence, not hardcoded charts."

**On screen**: Proof of Impact dashboard showing:
1. **Benchmark comparison** (real, computed results):
   - FIFO: 72% fulfilled after disruption
   - Nearest-Greedy: 78%
   - Static Optimization (no recovery): 84%
   - AIDNEXUS (with recovery): 87%
2. **Integrity metrics**: 
   - Zero inventory violations
   - Zero unauthorized dispatches
   - 100% audit coverage
3. **Honest limitations**: "15 families remain unserved. Additional inventory procurement recommended."

---

### 04:30 – 05:00 | CLOSING (30 seconds)

**Narrator**: "AIDNEXUS ONE is a self-healing humanitarian network. It doesn't just plan — it recovers, explains, and proves its impact. Every decision is auditable. Every AI action has a human in the loop. And the system can reset and replay this entire scenario with one click."

**On screen**: 
1. Click "Reset Scenario" button
2. System returns to initial state
3. Show the tag: "Built with OutSystems Developer Cloud + Google OR-Tools + AI Agents"

---

## Contingency Plans

| Failure | Response |
|---------|----------|
| AI provider down | Use fallback mode — show "AI Unavailable" banner, proceed with rule-based processing |
| Optimizer times out | Show timeout message, fall back to FIFO allocation, explain limitation |
| Screen doesn't load | Have screenshots/video backup for each screen |
| Live demo crashes | Switch to pre-recorded video (keep video under 5 min) |
