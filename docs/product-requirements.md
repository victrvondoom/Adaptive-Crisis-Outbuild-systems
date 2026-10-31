# Product Requirements Document — AIDNEXUS ONE

## 1. Problem Statement

During humanitarian crises (floods, earthquakes, displacement events), nonprofit organizations must coordinate the delivery of essential supplies — food, water, medicine, shelter materials — to affected populations. This coordination involves:

- Receiving and triaging hundreds of simultaneous aid requests
- Managing constrained inventory across multiple warehouses
- Allocating limited vehicles and volunteer teams
- Routing deliveries under time pressure
- Adapting plans when infrastructure fails (warehouses flood, roads close, volunteers cancel)

**Current state**: Most NGOs rely on spreadsheets, radio communication, and manual coordination. When disruptions occur, replanning is ad-hoc, slow, and error-prone. Aid reaches some recipients late or not at all. There is no systematic way to verify what was delivered, audit decisions, or measure impact.

**AIDNEXUS ONE solves this** by providing an integrated mission-control system with mathematical optimization, AI-assisted interpretation, and automatic disruption recovery — all under human supervision.

## 2. Target Users

| Role | Description | Key Needs |
|------|-------------|-----------|
| NGO Administrator | Senior staff managing the organization | Organization setup, user management, reporting |
| Mission Coordinator | Operational lead planning relief missions | Request triage, resource allocation, dispatch approval, replanning |
| Field Volunteer | On-the-ground delivery personnel | Assignment viewing, delivery confirmation, exception reporting |
| Auditor | Internal/external compliance reviewer | Audit trail access, decision history, impact reports |
| Observer | Donor, partner, or oversight body | Read-only dashboards, impact metrics |

## 3. Functional Requirements

### P0 — Must Work (MVP for Hackathon Demo)

| ID | Requirement | Acceptance Criteria |
|----|-------------|-------------------|
| P0-1 | Aid request intake | Form captures: requester name (synthetic), location, urgency, items needed, quantities |
| P0-2 | Request verification | Agent reviews request, extracts structured data, flags issues for human review |
| P0-3 | Warehouse inventory model | CRUD for depots, items, quantities; inventory decrement on dispatch |
| P0-4 | Feasible allocation optimizer | Given requests + inventory + vehicles, produce optimal assignments |
| P0-5 | Human approval workflow | Coordinator reviews plan, approves/rejects/modifies before dispatch |
| P0-6 | Mission state machine | Explicit states with valid transitions, rejection of invalid transitions |
| P0-7 | Dispatch execution | Approved plan becomes active assignments viewable by volunteers |
| P0-8 | Delivery confirmation | Volunteer marks delivery complete; state updates; inventory adjusts |
| P0-9 | Audit trail | Append-only log of all state changes with actor, timestamp, reason |

### P1 — Signature Differentiation

| ID | Requirement | Acceptance Criteria |
|----|-------------|-------------------|
| P1-1 | Disruption detection | System detects warehouse unavailability event |
| P1-2 | Impact assessment | Identifies which assignments are affected by disruption |
| P1-3 | Automated replanning | Re-runs optimizer with updated constraints, preserving valid assignments |
| P1-4 | Plan comparison | Side-by-side view of original vs. revised plan with diff highlights |
| P1-5 | Human-approved recovery | Coordinator reviews recovery plan and authorizes changes |
| P1-6 | Reproducible simulation | Deterministic scenario with seed, reset button, replay capability |

### P2 — Judge-Ready Polish

| ID | Requirement | Acceptance Criteria |
|----|-------------|-------------------|
| P2-1 | Premium mission command UI | Professional dashboard with KPIs, map, alerts, approvals |
| P2-2 | Impact dashboard | Completed deliveries, unmet demand, resource efficiency charts |
| P2-3 | Benchmark results | Real computed metrics comparing AIDNEXUS vs. baselines |
| P2-4 | Accessible mobile interface | Field volunteer workflow works on phone screen |
| P2-5 | One-click demo reset | Button resets scenario to initial state for repeatable demo |
| P2-6 | Nonprofit problem validation | Cited sources showing real-world relevance |

### P3 — Optional Stretch

| ID | Requirement |
|----|-------------|
| P3-1 | SMS-based request intake via Twilio |
| P3-2 | Voice assistant for field workers |
| P3-3 | Offline-capable delivery confirmation |
| P3-4 | Cross-NGO resource sharing |
| P3-5 | Demand forecasting from historical patterns |

## 4. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Performance | P95 planning time < 10s for 100 requests |
| Accessibility | WCAG 2.2 AA design targets |
| Security | Role-based access control, prompt injection protection |
| Data Privacy | Synthetic data only in demo; PII minimization |
| Auditability | 100% coverage of dispatch state changes |
| Reliability | Graceful degradation if AI provider unavailable |
| Reproducibility | Deterministic scenarios with fixed seeds |

## 5. Out of Scope

- Real beneficiary data collection
- Medical diagnosis or treatment decisions
- Financial transactions or payment processing
- Real-time GPS tracking of vehicles
- Integration with actual NGO databases
- Multi-language translation (stretch for post-hackathon)
