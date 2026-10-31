# Implementation Roadmap — AIDNEXUS ONE

## Development Window: November 2–9, 2026 (7 days)

## Strategy: Vertical Slice First

Build the thinnest possible end-to-end path first, then widen.

---

## Day 1 (Nov 2): Foundation — Vertical Slice P0

**Goal**: Aid Request → Structured Work Order → Inventory Check → Optimized Assignment → Human Approval → Dispatch → Delivery Confirmation → Audit Evidence

### Morning (4h)
- [ ] Create OutSystems ODC application "AidNexus One"
- [ ] Create core entities: Organization, AidRequest, AidRequestItem, Depot, InventoryItem, Vehicle, Mission, MissionAssignment
- [ ] Create AuditEvent entity
- [ ] Seed demo data: 3 depots, 10 vehicles, sample inventory
- [ ] Create Aid Request intake screen (basic form)

### Afternoon (4h)
- [ ] Create Mission state machine server action (transitions + validation)
- [ ] Create Human Approval screen (review + approve/reject)
- [ ] Create Delivery Confirmation screen
- [ ] Set up Python FastAPI optimizer project (skeleton)
- [ ] Implement basic FIFO allocation as first optimizer endpoint
- [ ] Test end-to-end: create request → approve → mark delivered

### Evening (3h)
- [ ] Implement OR-Tools MIP optimizer (basic version)
- [ ] Connect OutSystems to optimizer via REST integration
- [ ] Verify optimizer returns valid assignments
- [ ] Create audit logging for all state transitions
- [ ] Run first manual test of complete vertical slice

**Day 1 Exit Criteria**: A coordinator can create a request, see an optimized plan, approve it, and a volunteer can confirm delivery. All actions are audited.

---

## Day 2 (Nov 3): Disruption Recovery — P1 Signature

**Goal**: Warehouse failure → Impact detection → Replanning → Plan comparison → Human approval → Updated dispatch

### Morning (4h)
- [ ] Create Disruption entity and disruption injection UI
- [ ] Implement MissionPlanVersion (versioned plans)
- [ ] Implement replanning in optimizer (preserve commitments)
- [ ] Build plan comparison logic (diff old vs new)

### Afternoon (4h)
- [ ] Create recovery approval screen with side-by-side plan comparison
- [ ] Implement "preserve completed deliveries" logic
- [ ] Connect disruption → replan → approve → update flow
- [ ] Create scenario reset functionality

### Evening (3h)
- [ ] Implement deterministic scenario generation (200 requests, seed=42)
- [ ] Test warehouse failure scenario end-to-end
- [ ] Verify completed deliveries are preserved
- [ ] Fix critical bugs from Day 1 and Day 2 testing

**Day 2 Exit Criteria**: Demo the warehouse failure recovery scenario. Completed deliveries preserved. New plan presented for human approval.

---

## Day 3 (Nov 4): Agent Integration — MID-SUBMISSION

**Goal**: LLM-powered request interpretation. Mid-hackathon submission.

### Morning (4h)
- [ ] Set up AWS Bedrock or Azure AI integration in OutSystems
- [ ] Implement Agent 1 (Need-to-Mission) with basic tool calling
- [ ] Create agent trace viewer screen
- [ ] Test agent interpretation of sample requests

### Afternoon (4h)
- [ ] Implement Agent 2 (Resource Strategist) — coordinator of planning flow
- [ ] Implement Agent 3 (Recovery) — coordinator of disruption response
- [ ] Create AgentRun and AgentToolCall logging
- [ ] Prepare and submit mid-hackathon checkpoint

### Evening (2h)
- [ ] Implement fallback mode for when LLM is unavailable
- [ ] Test agent policy engine (tool authorization)
- [ ] Review mid-submission feedback if available

**Day 3 Exit Criteria**: Agents interpret requests and coordinate planning. Mid-submission submitted.

---

## Day 4 (Nov 5): Premium UI — Mission Command

**Goal**: Professional-grade dashboard. Information-dense, beautiful, accessible.

### Morning (4h)
- [ ] Design and build Mission Command dashboard
- [ ] Implement KPI cards (fulfilled, pending, unmet, disruptions)
- [ ] Create scenario map visualization
- [ ] Build pending approval queue component

### Afternoon (4h)
- [ ] Build Disaster Digital Twin screen with failure injection
- [ ] Create before/after allocation comparison visualization
- [ ] Build inventory warning indicators
- [ ] Implement dark/light theme switching

### Evening (3h)
- [ ] Build Agent Mission Control screen (trace viewer)
- [ ] Create confidence indicators and uncertainty display
- [ ] Responsive layout testing
- [ ] Accessibility audit (keyboard nav, focus indicators, labels)

**Day 4 Exit Criteria**: Professional mission control UI with all 5 primary screens at least skeletal.

---

## Day 5 (Nov 6): Benchmarks & Impact

**Goal**: Real benchmark results. Impact dashboard.

### Morning (4h)
- [ ] Implement benchmark runner in Python
- [ ] Implement all 4 planning modes (FIFO, Greedy, Static-OPT, AIDNEXUS)
- [ ] Run benchmark suite for 25, 50, 100, 200 request scenarios
- [ ] Collect raw metrics

### Afternoon (4h)
- [ ] Build Proof of Impact dashboard in OutSystems
- [ ] Display real benchmark results (computed, not hardcoded)
- [ ] Create exportable impact report
- [ ] Build comparison charts (fulfilled %, distance, runtime)

### Evening (3h)
- [ ] Run 500-request scenarios
- [ ] Run multiple seeds for statistical confidence
- [ ] Generate aggregate benchmark report
- [ ] Identify and document scenarios where AIDNEXUS underperforms

**Day 5 Exit Criteria**: Real benchmark results displayed. Impact dashboard shows computed metrics.

---

## Day 6 (Nov 7): Polish & Testing

**Goal**: Bug fixes. Edge cases. Demo rehearsal.

### Morning (4h)
- [ ] Run all test cases (T1-T10 from spec)
- [ ] Fix critical bugs
- [ ] Test concurrent approval scenario
- [ ] Test prompt injection protection
- [ ] Test cross-organization isolation

### Afternoon (4h)
- [ ] Polish UI (animations, loading states, error messages, empty states)
- [ ] Mobile responsive testing for Field Operations screen
- [ ] WCAG 2.2 AA compliance review
- [ ] One-click demo reset button

### Evening (3h)
- [ ] Full demo rehearsal (5-minute walkthrough)
- [ ] Time each demo segment
- [ ] Identify and fix demo-blocking issues
- [ ] Prepare demo narration script

**Day 6 Exit Criteria**: All P0 and P1 features working. Demo rehearsed under 5 minutes.

---

## Day 7 (Nov 8–9): Submission

**Goal**: Final submission with all artifacts.

### Morning (4h)
- [ ] Final bug fixes from demo rehearsal
- [ ] Write submission README
- [ ] Create architecture diagram (final version)
- [ ] Create system workflow diagram
- [ ] Create entity relationship diagram (exported)

### Afternoon (4h)
- [ ] Record demo video (backup if live demo fails)
- [ ] Write honest limitations section
- [ ] Write project impact statement
- [ ] Complete competition compliance checklist
- [ ] Prepare deployment instructions

### Evening (3h)
- [ ] Final submission on TAIKAI platform
- [ ] Verify all links work
- [ ] Verify demo scenario can be reset and replayed
- [ ] Final benchmark run with documented environment

**Day 7 Exit Criteria**: Submission complete. All required artifacts uploaded. Demo repeatable.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| OutSystems MCP/Mentor unavailable | MEDIUM | HIGH | Manual ODC Studio development |
| AWS Bedrock quota exhausted | LOW | MEDIUM | Azure AI failover; rule-based fallback |
| OR-Tools solve time exceeds target | LOW | MEDIUM | Reduce problem size; use heuristics |
| ODC deployment issues | MEDIUM | HIGH | Local preview as backup (clearly labeled) |
| Time overrun on Day 1 vertical slice | MEDIUM | HIGH | Cut Agent integration to Day 3; use manual workflows |
| UI doesn't meet premium standard | MEDIUM | MEDIUM | Focus on 2 screens instead of 5; make them excellent |

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| Oct 27 | PREPARATION MODE | 6 days before dev window; rules scope "work on app" to 7 days |
| Oct 27 | Vertical slice first | P0 completeness > P2 polish |
| Oct 27 | Hybrid optimizer (MIP + VRP) | More tractable than monolithic; good solve times |
| Oct 27 | Python FastAPI for optimizer | OR-Tools native to Python; REST contract to OutSystems |
| Oct 27 | 3 agents (not more) | Minimum viable agent system; each has clear responsibility |
