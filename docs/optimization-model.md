# Optimization Model — AIDNEXUS ONE

## 1. Problem Formulation

The AIDNEXUS resource allocation problem is a variant of the **Capacitated Vehicle Routing Problem with Pickup and Delivery, Time Windows, and Multiple Depots (CVRPPDTW-MD)**, extended with:

- Multi-commodity inventory constraints
- Priority-weighted demand fulfillment
- Fairness/equity constraints across regions
- Disruption-aware replanning with commitment preservation

## 2. Sets and Indices

```
R = {r₁, r₂, ..., rₙ}          Set of aid requests
D = {d₁, d₂, ..., dₘ}          Set of depots (warehouses)
V = {v₁, v₂, ..., vₖ}          Set of vehicles
W = {w₁, w₂, ..., wₗ}          Set of volunteers
C = {c₁, c₂, ..., cₚ}          Set of item categories (food, water, etc.)
L = set of all locations          Depots ∪ Request locations
T = time periods (discretized)
```

## 3. Parameters

```
demand[r][c]        Quantity of category c requested by r
inventory[d][c]     Available quantity of category c at depot d
capacity[v]         Maximum units vehicle v can carry
base[v] ∈ D         Base depot for vehicle v
distance[i][j]      Travel distance from location i to j
time[i][j]          Travel time from location i to j
deadline[r]         Delivery deadline for request r
priority[r]         Priority weight (CRITICAL=100, HIGH=50, MEDIUM=20, LOW=10)
available[w]        Availability window for volunteer w
blocked[i][j]       1 if route i→j is blocked, 0 otherwise
committed[r]        1 if request r has a completed delivery (immutable)
```

## 4. Decision Variables

```
x[r][d][v] ∈ {0, 1}     1 if request r is served from depot d by vehicle v
y[v][i][j] ∈ {0, 1}     1 if vehicle v traverses arc (i, j)
u[r]       ∈ {0, 1}     1 if request r is unmet (unfulfilled)
a[r]       ≥ 0          Arrival time at request r location
s[r][c]    ≥ 0          Quantity of category c actually allocated to r
```

## 5. Objective Function

```
MINIMIZE:
    α₁ · Σᵣ priority[r] · u[r]                           // Weighted unmet demand
  + α₂ · Σᵥ Σᵢ Σⱼ distance[i][j] · y[v][i][j]          // Total travel distance
  + α₃ · Σᵣ max(0, a[r] - deadline[r])                   // Deadline violations
  + α₄ · (1 - Σᵣ(1-u[r]) / |R|)                         // Coverage gap
  + α₅ · equity_penalty                                   // Regional equity

WHERE:
    α₁ >> α₂  (humanitarian need always dominates travel efficiency)
    
    Recommended weights:
    α₁ = 1000   (unmet demand — highest priority)
    α₂ = 1      (travel distance — lowest priority)  
    α₃ = 100    (deadline violations)
    α₄ = 500    (coverage gap)
    α₅ = 200    (equity penalty)
```

## 6. Hard Constraints

```
C1: Vehicle Capacity
    Σᵣ Σ_c s[r][c] · x[r][d][v] ≤ capacity[v]    ∀v

C2: Inventory Availability
    Σᵣ s[r][c] · x[r][d][v] ≤ inventory[d][c]     ∀d, ∀c

C3: Single Assignment
    Σ_d Σ_v x[r][d][v] + u[r] = 1                  ∀r where committed[r] = 0

C4: Committed Deliveries Preserved
    u[r] = 0 AND x[r][d*][v*] = 1                   ∀r where committed[r] = 1
    (d* and v* are the original assignment)

C5: Blocked Routes
    y[v][i][j] = 0                                   ∀(i,j) where blocked[i][j] = 1

C6: Vehicle Depot Assignment
    x[r][d][v] = 0                                   if base[v] ≠ d
    (vehicles serve from their base depot only — simplification)

C7: Flow Conservation
    Σⱼ y[v][base[v]][j] = 1                          ∀v (each vehicle departs base)
    Σᵢ y[v][i][base[v]] = 1                          ∀v (each vehicle returns to base)
    Σᵢ y[v][i][j] = Σₖ y[v][j][k]                   ∀v, ∀j ∉ D (flow conservation)

C8: Allocation ≤ Demand
    s[r][c] ≤ demand[r][c]                           ∀r, ∀c
```

## 7. Soft Constraints (Penalized in Objective)

```
S1: Deadline Preference
    Penalize a[r] > deadline[r] proportionally

S2: Regional Equity
    equity_penalty = Σ_region |fulfillment_rate[region] - avg_fulfillment_rate|
    (Minimize variance in fulfillment rates across regions)

S3: Volunteer Workload Balance
    Penalize max volunteer hours - min volunteer hours
```

## 8. Solver Strategy

### Primary: Mixed Integer Programming (MIP)

Use OR-Tools `pywraplp` with SCIP or GLOP backend:
- Good for allocation + inventory constraints
- Handles the assignment problem well
- Can solve 200-request instances in < 10s

### Alternative: Constraint Programming (CP-SAT)

Use OR-Tools `cp_model` for:
- Complex routing with time windows
- Better at combinatorial scheduling
- More flexible constraint expression

### Hybrid Approach (Recommended)

1. **Phase 1 (MIP)**: Solve allocation — assign requests to depots considering inventory, capacity, and priority
2. **Phase 2 (VRP)**: Given allocations, solve vehicle routing per depot using OR-Tools VRP solver

This decomposition is more tractable than solving the full problem monolithically.

## 9. Replanning Extension

When a disruption occurs:

```
1. Mark disrupted depot/routes/vehicles:
   - Set inventory[d_failed][c] = 0 for all c
   - Set blocked[i][j] = 1 for affected routes

2. Identify committed assignments:
   - Any assignment with DeliveryReceipt → committed = 1
   - Any assignment with status = IN_TRANSIT → optionally preserve

3. Re-solve with updated parameters:
   - committed[] prevents reassignment of completed deliveries
   - Reduced inventory and vehicle pool
   - May produce higher unmet demand (honest outcome)

4. Generate diff:
   - New assignments added
   - Reassigned requests (depot changed)
   - Newly unmet requests
   - Preserved assignments
```

## 10. Benchmark Baselines

### Baseline A: FIFO (First-Come-First-Served)

```pseudocode
SORT requests by CreatedAt ascending
FOR each request r:
    FOR each depot d (in order):
        IF inventory[d] can fulfill r:
            ASSIGN r to d using nearest available vehicle
            DECREMENT inventory
            BREAK
    IF not assigned:
        MARK r as unmet
```

### Baseline B: Nearest-Greedy

```pseudocode
FOR each request r (sorted by priority DESC):
    nearest_depot = argmin(distance[r.location][d.location]) for d in depots
    IF nearest_depot has sufficient inventory:
        ASSIGN r to nearest_depot
    ELSE:
        TRY next nearest depot
    IF not assigned:
        MARK r as unmet
```

### Baseline C: Static Optimization (No Replanning)

Same as AIDNEXUS optimizer, but when a disruption occurs:
- Affected assignments are simply CANCELLED
- No replanning attempt
- Unmet demand increases without recovery

### AIDNEXUS (Full System)

Full optimizer with disruption-aware replanning as described above.

## 11. Scaling Considerations

| Scenario Size | Expected Solve Time | Approach |
|--------------|-------------------|----------|
| 25 requests | < 1s | Exact MIP |
| 50 requests | < 3s | Exact MIP |
| 100 requests | < 10s | Exact MIP with time limit |
| 200 requests | < 15s | Hybrid MIP + heuristic |
| 500 requests | < 30s | Heuristic with local search |

For hackathon demo: 200-request scenario is the primary target.
