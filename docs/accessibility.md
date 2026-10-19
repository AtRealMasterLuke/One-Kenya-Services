# Accessibility (WCAG 2.2 AA) and low bandwidth

## Automated

* **axe-core** (`scripts/a11y_check.py`): every page used by a visitor, citizen, officer and
  administrator, at 375 px and 1280 px, against the WCAG 2.0/2.1/2.2 A and AA rule tags. The
  script fails if a signed-in check ever lands on the sign-in page, so a failed login can't
  pass for a clean result (that happened once during development). Results:
  `docs/evidence/axe_results.json`.
* **Lighthouse** on a phone profile with slow 3G (400 kbps, 400 ms round trip, 4× CPU
  slowdown). It must score 100 for accessibility and at least 90 for performance, transfer under
  150 KB per page, and paint within 3 s (first content) and 4 s (largest content). Results:
  `docs/evidence/lighthouse/`.

Automated tools find roughly a third to a half of WCAG problems. The rest were designed in and
checked by hand.

## Manual checklist

| WCAG 2.2 | How it's met |
|---|---|
| 1.1.1 Non-text content | Report photos have alt text naming the report; decorative marks are `aria-hidden`. |
| 1.3.1 Info and relationships | Real `<fieldset>`/`<legend>` for the category and location groups; tables have `<th scope>`; every input has a `<label>`; help text and errors are linked to their field. |
| 1.4.3 Contrast | Every text/background pair measured at ≥ 4.5:1 (lowest: escalated badge 5.6:1, pending badge 5.8:1, muted text 6.5:1; input borders 3.1:1 as non-text); status is never shown by colour alone. Badges carry words ("Overdue"), and overdue rows have a text "… late" as well as the red edge. |
| 1.4.10 Reflow | Single-column layout down to 320 px; wide tables scroll inside their own box, not the page. |
| 2.1.1 Keyboard | Everything is a native link, button or form control. The map (pointer-only by nature) has two keyboard alternatives: "Use my current location" and choosing the ward. |
| 2.4.1 Bypass blocks | "Skip to main content" link. |
| 2.4.3 Focus order | Source order matches visual order; no `tabindex` above 0. |
| 1.4.11 / 2.4.7 / 2.4.11 Focus visible, contrasting, not obscured | Two-tone ring on every focusable element: 3 px near-black outline (16:1 on white) plus a yellow halo (3.5:1 on the green header). The first version used yellow alone, which was 1.8:1 on white; caught by measuring contrast, not by axe. No sticky headers cover focus. |
| 2.5.7 Dragging movements | No dragging needed: the map uses a single tap; the pin is never dragged. |
| 2.5.8 Target size | Buttons and inputs at least 44 px tall. |
| 3.3.1 / 3.3.3 Error identification and suggestion | Errors say what to do ("Enter a Kenyan mobile number, for example 0712 345 678"). |
| 3.3.7 Redundant entry | Category and location are carried from step 1 to step 2; nothing is asked twice. |
| 3.3.8 Accessible authentication | No cognitive test; the phone number and password fields allow paste and password managers (`autocomplete` set). |
| 4.1.3 Status messages | Success and error messages use `role="status"` / `role="alert"`; location results use `aria-live`. |

## Low bandwidth

* Measured on the production build: about 5 KB of HTML per page and 3.4 KB of CSS (gzip, 12 KB raw); no web fonts.
* The only script is the location picker (3.4 KB). Leaflet (42 KB gzip) and map tiles
  load **only** if the citizen taps "Choose on a map".
* Photos are shrunk to at most 1,600 px and re-encoded before saving, so officers on mobile data
  don't download 4 MB camera originals.
* Everything works without JavaScript except the map itself, and the ward list covers that.

## Not done

* **Kiswahili and Gĩkũyũ.** English only for now; the templates are ready for Django's
  translation machinery but no translations exist.
* **Screen-reader testing** with TalkBack (the most common reader on Android in Kenya) has not
  been done; axe can't replace it.
