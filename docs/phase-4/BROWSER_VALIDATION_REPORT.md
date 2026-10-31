# Browser Validation Report (Phase IV)

Run: `cd backend && python -m pytest tests/browser -m browser` — **10/10 journeys
green** against a live uvicorn server with real Chromium (Playwright).

| # | Journey | Verifies |
|---|---|---|
| 1 | login_and_dashboard | synthetic identity login, live KPIs |
| 2 | triage_journey | Agent 1 intake → CRITICAL classification in UI |
| 3 | disruption_and_approval_journey | disruption → pending replan → human approval |
| 4 | volunteer_delivery_journey | mission select → signature canvas → POD confirmation |
| 5 | cross_tenant_isolation_in_ui | Highland-only identity cannot see Pacific data |
| 6 | feature_atlas_journey | live portfolio: 1080 summary, 36 domains, drill-down, search |
| 7 | **ngo_workflows_journey (Phase IV)** | structured intake w/ consent → work order created; impact report renders evidence-linked stats + provenance hash + audit-chain status |
| 8 | screenshots_three_viewports | desktop/tablet/mobile captures |
| 9 | accessibility_scan | axe-core critical-rule scan (color-contrast, button-name, label, aria-valid-attr, html-has-lang) |
| 10 | responsive_no_horizontal_overflow | mobile viewport ≤2px overflow |

Screenshots (evidence): `docs/phase-2/screenshots/` — dashboard_{desktop,tablet,
mobile}.png, feature_atlas_desktop.png, **ngo_workflows_desktop.png** (Phase IV).

## Phase IV UI observations (taste review inputs)

- The new NGO Workflows tab reuses the established panel/card language, status
  chips and empty-state patterns — no new visual grammar introduced.
- All dynamic strings render through `escapeHtml` (XSS regression covered by
  the security suite; UI never renders unescaped backend data).
- Honest states: intake rejections render the backend's real error detail;
  the impact report shows "—" for undefined rates rather than fake zeros.
- Accessibility: form controls carry labels; interactive domain cards have
  role/aria-label + keyboard activation; axe-core critical rules pass.
- Known gap (honest): the Phase IV surfaces present data + primary actions
  (intake, transfer proposal, report generation); transfer approval steps are
  exercised through the API/tests, not yet as in-UI approval buttons — tracked
  in OPEN_ISSUES.md.
