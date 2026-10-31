# OutSystems Integration Guide — AIDNEXUS ONE

## 1. OutSystems Developer Cloud (ODC) Setup

### Application Creation
```
Application Name: AidNexus One
Application Type: Web Application (Reactive)
Description: Humanitarian mission-control system with AI-powered disruption recovery
Icon: Shield with network pattern (teal/navy)
```

### ODC Features Used

| Feature | Usage | Priority |
|---------|-------|----------|
| ODC Entities | All 27 data entities | P0 |
| ODC Screens | 10 application screens | P0 |
| Server Actions | State machine, planning, approvals | P0 |
| Client Actions | UI interactivity, theme switching | P1 |
| REST Integrations | Optimizer service, LLM providers | P0 |
| Site Properties | Configuration (URLs, keys, feature flags) | P0 |
| Roles | 5 authorization roles | P0 |
| Timers | Periodic disruption check, agent queue | P2 |
| Agent Experience | Agent orchestration (if available) | P1 |

### Site Properties
```
OptimizerBaseURL: TEXT = "https://optimizer.aidnexus.example.com"
LLMProvider: TEXT = "aws_bedrock" | "azure_openai" | "disabled"
AWSBedrockRegion: TEXT = "us-east-1"
AWSBedrockModelId: TEXT = "anthropic.claude-3-sonnet-20240229-v1:0"
AzureOpenAIEndpoint: TEXT = ""
DemoMode: BOOLEAN = TRUE
MaxOptimizationTimeSeconds: INTEGER = 30
DefaultScenarioSeed: TEXT = "42"
```

### Secrets Management
- Store API keys in ODC's secure configuration (not in entity data)
- AWS credentials: Use IAM role-based authentication where possible
- Optimizer service: Internal network, no auth required (or simple API key)

## 2. OutSystems Agent Experience Integration

### If ODC Agent Experience Is Available

```
Agent Configuration:
  Name: "AidNexus Need-to-Mission Agent"
  Description: "Interprets humanitarian aid requests and creates structured work orders"
  Model Provider: AWS Bedrock (Claude 3 Sonnet)
  
  Tools:
    1. ExtractAidItems
       Input: RequestText (Text)
       Output: Items (JSON array)
       Server Action: Agent_ExtractAidItems
       
    2. ClassifyUrgency
       Input: RequestText (Text), ExtractedItems (JSON)
       Output: Priority (Text), Confidence (Decimal)
       Server Action: Agent_ClassifyUrgency
       
    3. CheckDuplicates
       Input: RequestId (GUID), Region (Text), Items (JSON)
       Output: IsDuplicate (Boolean), CandidateId (GUID nullable)
       Server Action: Agent_CheckDuplicates

  System Prompt: [See agent-design.md for full prompt]
  Max Tokens: 4096
  Temperature: 0.2
```

### If Agent Experience Is NOT Available

Implement direct LLM API calls via REST integration:

```
Server Action: InvokeAgentDirect
  1. Construct messages array with system prompt + user request
  2. Call AWS Bedrock REST API
  3. Parse structured JSON output from response
  4. Call individual tool Server Actions based on parsed output
  5. Log AgentRun and AgentToolCall records
```

## 3. REST Integration Setup

### Optimizer Service Integration
```
Name: OptimizerService
Base URL: [Site Property: OptimizerBaseURL]
Methods:
  POST /api/v1/optimize
  POST /api/v1/benchmark
  GET /health
Timeout: 60000 ms
Authentication: None (or API Key header)
```

### AWS Bedrock Integration
```
Name: AWSBedrockLLM
Base URL: https://bedrock-runtime.{region}.amazonaws.com
Authentication: AWS Signature V4 (configured in ODC)
Methods:
  POST /model/{model-id}/invoke
Headers:
  Content-Type: application/json
  Accept: application/json
```

## 4. Deployment Checklist

### Pre-Deployment
- [ ] All entities created with proper relationships
- [ ] All server actions tested individually
- [ ] REST integrations configured with correct URLs
- [ ] Site properties set for target environment
- [ ] Roles assigned to test users
- [ ] Demo scenario seed data script ready

### Deployment Steps
1. Publish application to ODC (Staging first)
2. Configure Site Properties for staging environment
3. Verify REST integration connectivity (optimizer health check)
4. Run scenario seeding action
5. Test end-to-end: request → plan → approve → deliver
6. Test disruption scenario
7. Promote to Production (if separate environment)

### Post-Deployment Verification
- [ ] All screens load without errors
- [ ] State machine transitions work correctly
- [ ] Optimizer integration returns valid responses
- [ ] Audit events are being created
- [ ] Role-based access control enforced
- [ ] Demo reset button works
- [ ] Benchmark results page shows computed data
