# Feature Priority Model

Transparent weighted scoring computed by `scripts/generate_feature_atlas.py`:

| Factor | Weight | Source signal |
|---|---|---|
| humanitarian impact | 20% | impact/risk/effort seeds per feature |
| safety correctness | 15% | impact/risk/effort seeds per feature |
| reliability | 15% | impact/risk/effort seeds per feature |
| user demand | 10% | impact/risk/effort seeds per feature |
| differentiation | 10% | impact/risk/effort seeds per feature |
| dependency leverage | 10% | impact/risk/effort seeds per feature |
| feasibility | 5% | impact/risk/effort seeds per feature |
| taste accessibility | 5% | impact/risk/effort seeds per feature |
| cloud leverage | 10% | impact/risk/effort seeds per feature |

Hard overrides: safety, authorization, data-integrity and life-safety issues are P0/P1 regardless of score; BLOCKED_EXTERNAL_DEPENDENCY features are scheduled by dependency resolution, not score. Rejection criteria and rejected candidates are in FEATURE_REJECTION_REGISTER.md. Every record carries `priority_score`, `priority` (P0-P4) and `priority_reason`.
