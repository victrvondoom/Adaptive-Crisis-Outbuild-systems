# Deployment Guide — AIDNEXUS ONE

## Overview

AIDNEXUS ONE consists of two deployable components:
1. **OutSystems ODC Application** — The primary business application
2. **Python Optimizer Service** — External microservice for mathematical optimization

## 1. OutSystems ODC Application

### Prerequisites
- OutSystems Developer Cloud account with application creation permissions
- ODC Studio installed (or browser access to ODC Portal)
- Registered team on TAIKAI Build for the Future 2026

### Deployment Steps

```
1. Create application in ODC Studio
   - Name: "AidNexus One"
   - Template: Blank Reactive Web App

2. Create all entities (see data-entities.md)
   - Import entity definitions in order (Organization first, then dependent entities)

3. Create server actions (see server-actions.md)
   - State machine transitions
   - Planning and approval actions
   - Delivery confirmation
   - Scenario management

4. Create screens (see screen-specifications.md)
   - Start with basic CRUD screens
   - Apply design system progressively

5. Configure REST integrations
   - Optimizer Service: POST /api/v1/optimize
   - AWS Bedrock: POST /model/{model-id}/invoke

6. Set Site Properties
   - OptimizerBaseURL = deployed service URL
   - LLMProvider = "aws_bedrock" or "disabled"
   - DemoMode = TRUE

7. Configure Roles
   - Create: NGO_ADMIN, MISSION_COORDINATOR, FIELD_VOLUNTEER, AUDITOR, READ_ONLY_OBSERVER
   - Assign to test users

8. Publish to Staging
   - Verify all screens load
   - Test state machine transitions
   - Verify REST integrations

9. Seed demo data
   - Run SeedScenarioData action with seed=42, requestCount=200

10. Promote to Production (if available)
```

## 2. Python Optimizer Service

### Prerequisites
- Python 3.11+
- pip or uv package manager
- Hosting environment (Railway, Azure App Service, AWS Lambda + API Gateway, or local)

### Setup
```bash
# Clone repository
git clone <repo-url>
cd aidnexus-one/services/optimizer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Verify OR-Tools installation
python -c "from ortools.linear_solver import pywraplp; print('OR-Tools OK')"

# Run service
uvicorn main:app --host 0.0.0.0 --port 8080

# Verify
curl http://localhost:8080/health
```

### requirements.txt (specification)
```
fastapi>=0.104.0
uvicorn>=0.24.0
ortools>=9.10.4067
pydantic>=2.5.0
numpy>=1.24.0
```

### Hosting Options

| Option | Pros | Cons | Cost |
|--------|------|------|------|
| Railway | Easy deploy, auto-SSL | Limited free tier | ~$5/mo |
| Azure App Service | Stable, Azure integration | More setup | ~$10/mo |
| AWS Lambda + Gateway | Serverless, pay-per-use | Cold starts, 15min timeout | ~$1/mo |
| Render | Free tier available | Cold starts | Free/$7 |
| Local (demo only) | No cost, fast iteration | Not accessible externally | Free |

### Environment Variables
```
OPTIMIZER_HOST=0.0.0.0
OPTIMIZER_PORT=8080
MAX_SOLVE_TIME_SECONDS=30
LOG_LEVEL=INFO
CORS_ORIGINS=https://your-odc-app.outsystems.dev
```

## 3. Cloud AI Provider Setup

### AWS Bedrock
```
1. Enable AWS Bedrock in your AWS account
2. Request access to Anthropic Claude 3 Sonnet model
3. Create IAM user with bedrock:InvokeModel permission
4. Generate access key and secret
5. Configure in OutSystems Site Properties
```

### Azure OpenAI (Fallback)
```
1. Create Azure OpenAI resource
2. Deploy GPT-4o model
3. Note endpoint URL and API key
4. Configure in OutSystems Site Properties
```

## 4. Verification Checklist

After full deployment:

- [ ] OutSystems app accessible at its URL
- [ ] Optimizer service health check returns 200
- [ ] Aid request creation works
- [ ] Optimizer returns valid plan
- [ ] Approval workflow functions
- [ ] Delivery confirmation updates state
- [ ] Disruption injection triggers replanning
- [ ] Scenario reset returns to initial state
- [ ] Audit events are being logged
- [ ] Benchmark endpoint returns results

## 5. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Optimizer timeout | Problem too large or slow solver | Reduce max_solve_time_seconds, reduce request count |
| REST integration 500 | Optimizer service down | Check service logs, restart |
| LLM integration failed | API key expired or quota exceeded | Check credentials, switch to fallback provider |
| State transition rejected | Optimistic lock conflict | Retry after reload |
| Missing audit events | Server action didn't complete | Check action logs for errors |
