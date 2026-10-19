"""
Automated accessibility check with axe-core (the engine behind Lighthouse's and Deque's audits),
against every page a citizen, an officer and an administrator use, at phone and desktop sizes.

Fails on any violation of WCAG 2.0/2.1/2.2 level A or AA rules that axe can test. axe catches
roughly a third to a half of WCAG issues; the rest (keyboard order, meaningful wording, the map
alternative) is covered by the manual checklist in docs/accessibility.md.

  docker run --rm --network kenyamojaservices_default -v "$PWD:/w" -w /w \
      mcr.microsoft.com/playwright/python:v1.48.0-jammy \
      sh -c "pip install -q playwright==1.48.0 axe-playwright-python==0.1.7 && python scripts/a11y_check.py http://web-prod:8000"
"""

import json
import os
import sys
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
PASSWORD = os.environ.get("DEMO_PASSWORD", "Murang-a-demo-2026")
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
OUT = Path("docs/evidence/axe_results.json")

PAGES = {
    None: ["/", "/accounts/login/", "/accounts/register/"],
    "+254700000001": ["/requests/", "/requests/new/", "/account/api-keys/"],
    "+254700000010": ["/staff/", "/staff/?status=open&overdue=1"],
    "+254700000099": ["/staff/", "/staff/analytics/", "/staff/analytics/?as_of=2025-03-15T00:00&source=replay"],
}
VIEWPORTS = {"phone": {"width": 375, "height": 812}, "desktop": {"width": 1280, "height": 900}}


def login(page, phone):
    page.goto(f"{BASE}/accounts/login/")
    page.fill("#id_username", phone)
    page.fill("#id_password", PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def main():
    axe = Axe()
    results, failures = [], 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for vp_name, viewport in VIEWPORTS.items():
            for user, paths in PAGES.items():
                context = browser.new_context(viewport=viewport)
                page = context.new_page()
                if user:
                    login(page, user)
                # A case detail page for the signed-in role, found from their own list.
                extra = []
                if user == "+254700000001":
                    page.goto(f"{BASE}/requests/")
                    link = page.query_selector("main a[href^='/requests/'][href$='/']:not([href='/requests/new/'])")
                    if link:
                        extra.append(link.get_attribute("href"))
                if user == "+254700000010":
                    page.goto(f"{BASE}/staff/")
                    link = page.query_selector("main table a[href^='/requests/']")
                    if link:
                        extra.append(link.get_attribute("href"))
                for path in paths + extra:
                    page.goto(f"{BASE}{path}")
                    page.wait_for_load_state("networkidle")
                    landed = page.url.replace(BASE, "")
                    if user and landed.startswith("/accounts/login/"):
                        raise SystemExit(f"sign-in as {user} failed: {path} redirected to {landed}")
                    report = axe.run(page, options={"runOnly": {"type": "tag", "values": TAGS}})
                    violations = report.response["violations"]
                    failures += len(violations)
                    results.append({
                        "viewport": vp_name, "user": user or "anonymous", "path": path, "landed_on": landed,
                        "title": page.title(),
                        "passes": len(report.response["passes"]),
                        "violations": [{"id": v["id"], "impact": v["impact"], "help": v["help"],
                                        "nodes": [n["target"] for n in v["nodes"]][:5]} for v in violations],
                    })
                    status = "ok" if not violations else "; ".join(f"{v['id']} ({len(v['nodes'])})" for v in violations)
                    print(f"{vp_name:8} {user or 'anonymous':15} {path:55} {page.title()[:38]:38} {status}")
                context.close()
        browser.close()
    OUT.write_text(json.dumps({"tags": TAGS, "pages_checked": len(results), "violations": failures,
                               "results": results}, indent=2))
    print(f"\n{len(results)} page views checked, {failures} violation(s). Full results: {OUT}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
