# Evidence

| File | What it shows |
|---|---|
| `analytics_app_2025-03-15.json` / `analytics_independent_2025-03-15.json` | App vs independent recomputation of the dashboard: all 434 figures identical |
| `open311_client_check.txt` | Code for America's `open311` client lists, posts and reads requests |
| `ward_source_comparison.txt` | Why the IEBC ward boundaries were chosen |
| `axe_results.json` | axe-core: 0 WCAG A/AA violations across 26 page views |
| `lighthouse/` | Lighthouse on slow 3G: performance 95–98, accessibility 100 |
| `zap/` | OWASP ZAP baseline: 0 failures, 0 warnings |

The property-based state machine test was checked by deliberately breaking the officer
permission rule: the test failed immediately, and it passes on the real code.
