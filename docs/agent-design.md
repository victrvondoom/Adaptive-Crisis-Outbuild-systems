# Agent Design — AIDNEXUS ONE

## 1. Agent Architecture Principles

1. **Agents are advisors, not decision-makers**. Every consequential action requires human approval.
2. **Deterministic for validation, probabilistic for interpretation**. Use LLMs for understanding text and generating explanations; use deterministic logic for inventory checks, state transitions, and constraint validation.
3. **Tool-mediated actions only**. Agents cannot directly modify database state — they call defined tools that enforce authorization and validation.
4. **Auditable execution**. Every agent invocation produces an AgentRun record with all tool calls, inputs, outputs, and timing.
5. **Graceful degradation**. If the LLM provider is unavailable, the system falls back to manual workflows with visible limitations.

## 2. Agent 1: Need-to-Mission

### Purpose
Interpret incoming humanitarian aid requests, extract structured data, detect issues, and prepare work orders for planning.

### Trigger
New AidRequest created (status = REQUESTED).

### System Prompt (Specification)
```
You are a humanitarian aid request analyst. Your job is to:
1. Read the raw request text carefully
2. Extract specific aid items and quantities mentioned
3. Classify the urgency based on the content
4. Check if this might be a duplicate of an existing request
5. Flag anything uncertain for human review

RULES:
- Only extract items explicitly mentioned in the text
- Never invent quantities not in the source
- If the text mentions medical symptoms, flag for human review — do NOT classify medical conditions
- If confidence in any extraction is below 70%, flag for human review
- Always reference specific phrases from the original text as evidence
- Use ONLY the tools provided — never suggest actions outside your tool set
```

### Tools
| Tool | Description | Authorization |
|------|-------------|--------------|
| ExtractAidItems | Parse text → list of {category, item, quantity} | Agent-only |
| ClassifyUrgency | Assign CRITICAL/HIGH/MEDIUM/LOW based on content | Agent-only |
| CheckDuplicates | Compare against requests from same region in last 7 days | Agent-only |
| FlagForHumanReview | Mark request as needing coordinator attention | Agent-only |
| SaveAidRequestItems | Persist extracted items to database | Agent + validation |
| UpdateRequestStatus | Transition request state | Agent + state machine check |

### Output Contract
```json
{
  "request_id": "GUID",
  "extracted_items": [
    {"category": "FOOD", "item": "Rice", "quantity": 50, "unit": "kg", "source_text": "we need 50kg of rice"},
    {"category": "WATER", "item": "Drinking water", "quantity": 200, "unit": "liters", "source_text": "200 liters of clean water"}
  ],
  "urgency": "HIGH",
  "urgency_reason": "Text mentions 'children without food for 2 days'",
  "is_potential_duplicate": false,
  "duplicate_candidate_id": null,
  "confidence": 0.85,
  "flags": [],
  "requires_human_review": false,
  "evidence_references": ["Line 1: 'Our community of 30 families...'", "Line 3: '50kg of rice...'"]
}
```

### Guardrails
- Input text is sanitized before agent processing (strip HTML, limit length to 5000 chars)
- Agent cannot access requests from other organizations
- Agent cannot modify inventory or create dispatches
- Medical keyword detection triggers automatic human review bypass

## 3. Agent 2: Resource Strategist

### Purpose
Create feasible resource allocation plans by coordinating between inventory data, vehicle/volunteer availability, and the optimization engine.

### Trigger
Coordinator requests planning for verified requests; OR Agent 3 requests replanning.

### System Prompt (Specification)
```
You are a humanitarian resource allocation strategist. Your job is to:
1. Gather current inventory levels from all operational depots
2. Check available vehicles and their capacities
3. Review volunteer availability
4. Prepare optimization inputs and invoke the optimizer
5. Interpret the results and explain tradeoffs to the coordinator

RULES:
- Use ONLY the inventory data from GetInventory — never estimate or guess stock levels
- If the optimizer returns INFEASIBLE, report this honestly with reasons
- Explain any unmet demand clearly — never hide unfulfilled requests
- When replanning, always specify which existing assignments to preserve
- Present the comparison between old and new plans when replanning
```

### Tools
| Tool | Description | Authorization |
|------|-------------|--------------|
| GetInventory | Read current stock levels for all depots | Agent-only (read) |
| GetAvailableVehicles | List vehicles with capacity and availability | Agent-only (read) |
| GetAvailableVolunteers | List volunteers with time windows | Agent-only (read) |
| GetRouteDistances | Read distance matrix | Agent-only (read) |
| GetBlockedRoutes | List currently blocked routes | Agent-only (read) |
| GetExistingCommitments | List completed/in-progress assignments | Agent-only (read) |
| InvokeOptimizer | Call OR-Tools service with parameters | Agent + rate limit |
| ComparePlans | Generate diff between two plan versions | Agent-only |
| ExplainTradeoffs | Generate human-readable plan explanation | Agent + LLM |
| CreateMissionPlanVersion | Save new plan to database | Agent + validation |

### Optimization Invocation Protocol
1. Gather all read-only data via tools
2. Construct optimization request payload
3. Call InvokeOptimizer
4. Validate response (no hard constraint violations)
5. If INFEASIBLE: generate explanation, suggest relaxations
6. If FEASIBLE/OPTIMAL: generate tradeoff explanation
7. Save as MissionPlanVersion with status PENDING_APPROVAL

## 4. Agent 3: Recovery & Accountability

### Purpose
Detect and respond to operational disruptions, coordinate replanning, and ensure accountability through evidence-linked explanations.

### Trigger
Disruption event created (warehouse failure, route closure, etc.).

### System Prompt (Specification)
```
You are a humanitarian crisis recovery coordinator. When a disruption occurs, you must:
1. Assess the impact — which missions and assignments are affected?
2. Identify what is already completed and must be preserved
3. Identify what is still valid and unaffected
4. Request a new optimization run with updated constraints
5. Compare the original and recovery plans
6. Generate a clear explanation of what changed and why
7. Submit the recovery plan for human approval

RULES:
- NEVER modify completed deliveries
- NEVER apply a recovery plan without human approval
- Always explain what demand cannot be fulfilled and why
- Be specific about which assignments changed and which are preserved
- Include the disruption event as evidence in your explanation
```

### Tools
| Tool | Description | Authorization |
|------|-------------|--------------|
| GetDisruptionDetails | Read the disruption record | Agent-only (read) |
| GetAffectedAssignments | List assignments impacted by disruption | Agent-only (read) |
| GetCompletedDeliveries | List immutable completed assignments | Agent-only (read) |
| GetValidAssignments | List unaffected active assignments | Agent-only (read) |
| RequestReplanning | Invoke Agent 2 with updated constraints | Agent → Agent |
| GenerateImpactReport | Summarize disruption consequences | Agent + LLM |
| GenerateRecoveryExplanation | Create human-readable recovery narrative | Agent + LLM |
| CreateApprovalRequest | Submit recovery plan for coordinator review | Agent + validation |

### Recovery Protocol
```
1. DETECT: Receive disruption event
2. ASSESS: Query affected assignments
3. PRESERVE: Lock completed deliveries and valid assignments
4. REPLAN: Invoke Agent 2 with:
   - Disabled depot (if warehouse failure)
   - Blocked routes (if route closure)
   - Reduced vehicle fleet (if vehicle breakdown)
   - Existing commitments to preserve
5. COMPARE: Generate side-by-side plan diff
6. EXPLAIN: Create narrative of changes with evidence
7. PROPOSE: Submit to coordinator for approval
8. WAIT: Do NOT apply changes until approved
9. APPLY: After approval, update assignments exactly once
10. RECORD: Log all actions to audit trail
```

## 5. Agent Policy Engine

All agent tool calls pass through a server-side policy engine:

```
POLICY RULES:
  P1: Agent cannot call tools outside its authorized tool set
  P2: Write tools require entity-level authorization check
  P3: Rate limit on optimizer invocations (max 5 per minute per org)
  P4: LLM calls have max token budget (4096 output tokens)
  P5: Agent execution timeout (60 seconds per run)
  P6: Cross-organization data access is DENIED
  P7: Sensitive field access (beneficiary details) requires AUDITOR role
  P8: Tool calls are logged before execution (pre-audit)
  P9: Failed policy checks produce AgentToolCall with status=DENIED
```

## 6. Fallback Mode (LLM Unavailable)

When the LLM provider is unavailable:

| Agent Function | Fallback |
|---------------|----------|
| Item extraction | Regex-based keyword matching against known item categories |
| Urgency classification | Rule-based (keywords: "urgent", "critical", "children", "elderly" → HIGH) |
| Duplicate detection | Exact-match on location + item categories within 48 hours |
| Tradeoff explanation | Template-based summary of optimizer metrics |
| Recovery narrative | Template: "Disruption at {depot}. {N} assignments affected. New plan fulfills {M} of {N}." |

Fallback mode is visible to the coordinator with a banner: "⚠️ AI assistance is currently unavailable. Manual review required."
