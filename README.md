# AIDNEXUS ONE — Adaptive Crisis Outbuild Systems

> **The Self-Healing Humanitarian Network.**

## Overview

AIDNEXUS ONE is an end-to-end, evidence-driven, agentic humanitarian mission-control system built for the **OutSystems Build for the Future Hackathon 2026**.

It enables nonprofit organizations to receive aid requests, verify operational requirements, allocate scarce resources, coordinate volunteers, approve dispatches, detect disruptions, intelligently replan failed missions, verify deliveries, and measure their real impact.

### Core Differentiator

**Autonomous Humanitarian Disruption Recovery.**

When a warehouse becomes unavailable after a dispatch plan has been approved, AIDNEXUS ONE:

1. Records the disruption with evidence
2. Identifies all impacted assignments
3. Preserves completed deliveries and valid commitments
4. Recalculates feasible alternatives using mathematical optimization
5. Compares original and revised plans side-by-side
6. Displays unresolved demands with explanations
7. Requests human authorization before any changes
8. Applies the new plan exactly once after approval
9. Produces an auditable operational receipt

**No aid recipient is silently rejected by AI. No AI-generated content changes real operational state without human validation.**

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Application Platform | OutSystems Developer Cloud (ODC) |
| AI/Agentic | ODC Agent Experience + AWS Bedrock / Azure AI |
| Optimization Engine | Python + FastAPI + Google OR-Tools |
| Communication | Twilio (SMS notifications) |
| Hosting | OutSystems Cloud + External microservice |

## Project Structure

```
aidnexus-one/
  README.md
  LICENSE
  .gitignore
  .env.example
  docs/                          # All planning and specification documents
  outsystems/                    # OutSystems application blueprints
  services/optimizer/            # Python optimization microservice
  services/agent-adapters/       # Agent integration adapters
  benchmarks/                    # Scenario definitions and results
  tests/                         # Test suites
  scripts/                       # Utility scripts
  assets/                        # Static assets
```

## Competition

- **Hackathon**: OutSystems Build for the Future 2026
- **Development Window**: November 2–9, 2026
- **Category**: Social Good & Impact / Artificial Intelligence

## Quick Start — Run the Dynamic System

### Option 1: 1-Click Launch (Windows)
Double-click `start.bat` in the project root or run:
```powershell
.\start.ps1
```

### Option 2: Direct Command Line
```bash
# 1. Start the FastAPI Simulation & Optimization Engine
cd aidnexus-one/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 2. Open Mission Control in your browser:
# Navigate to: http://127.0.0.1:8000/
```

## Dynamic Capabilities Verified

1. **Mission Command Digital Twin**: Real-time interactive crisis map with coordinate projections, vehicle tracking, dynamic inventory gauges, and live request status badges.
2. **Autonomous Disruption Recovery**: 1-click disaster injectors (bridge collapse, depot flood, vehicle failure) triggering Agent 3 incident analysis, immutable completed delivery preservation, and mathematical replanning.
3. **Human-in-the-Loop Governance**: Side-by-side plan diff with coordinator sign-off requirement before any operational state is mutated.
4. **Agent 1 Need-to-Mission Triage**: Unstructured distress message parser with urgency classification, structured work order extraction, and Sphere Standards compliance verification.
5. **Field Volunteer Mobile Simulator**: Mobile delivery workflow with digital touch-signature capture and real-time depot inventory decrements.
6. **Reproducible Benchmark Arena**: Empirical comparison matrix running 200 requests under dual disruption stress (AIDNEXUS ONE vs Static Greedy vs FCFS).
7. **Evidence & Audit Ledger**: Append-only cryptographic SHA-256 audit log stream.

## License

MIT License — See [LICENSE](./LICENSE) for details.

