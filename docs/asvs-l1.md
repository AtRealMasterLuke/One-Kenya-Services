# OWASP ASVS 4.0.3, Level 1 check

Level 1 is the minimum for any public-facing application. Requirements are grouped by chapter;
**N/A** means the feature doesn't exist in this app. Each line says how it's met, or why not.

## V2 Authentication

| # | Requirement (short) | Status | How |
|---|---|---|---|
| 2.1.1 | Passwords ≥ 12 characters | **Partial** | Minimum is 10 (`AUTH_PASSWORD_VALIDATORS`), a compromise for typing on feature phones. Raise to 12 for production. |
| 2.1.2 | 64+ characters allowed | Met | No maximum below 128 (Django). |
| 2.1.4 | Any printable Unicode allowed | Met | Django does not restrict characters. |
| 2.1.7 | Checked against breached/common passwords | Met | `CommonPasswordValidator` (20,000 common passwords). |
| 2.1.9 | No composition rules | Met | Only length, similarity and common-password checks. |
| 2.2.1 | Anti-automation on sign-in | Met | django-axes: 5 failures → 15-minute lockout per number+IP. `test_lockout_after_five_failures`. |
| 2.2.3 | User notified after credential changes | **Gap** | No password-change flow is exposed to citizens yet. |
| 2.3.1 | Initial passwords random, expire | N/A | Users choose their own. Demo accounts are documented as such. |
| 2.5.x | Credential recovery | **Gap** | No self-service reset. Needs an SMS one-time code (see threat model). |
| 2.7.x | Out-of-band verifiers | **Gap** | Phone ownership isn't verified (threat model gap 1). |

## V3 Session management

| # | Requirement | Status | How |
|---|---|---|---|
| 3.2.1 | New session token on sign-in | Met | Django `login()` rotates the session key. |
| 3.3.1 | Logout invalidates the session | Met | `LogoutView` (POST only) flushes the session. |
| 3.3.2 | Idle/absolute timeout | Met | `SESSION_COOKIE_AGE` = 8 hours. |
| 3.4.1 | Cookie `Secure` | Met | `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` when DEBUG is off. |
| 3.4.2 | Cookie `HttpOnly` | Met | Session and CSRF cookies (ZAP 10010 fixed). |
| 3.4.3 | Cookie `SameSite` | Met | Django default `Lax`. |

## V4 Access control

| # | Requirement | Status | How |
|---|---|---|---|
| 4.1.1 | Enforced server-side | Met | `requests_app/access.py`, `statemachine.role_of`. |
| 4.1.3 | Least privilege | Met | Officers: own department only. Citizens: own cases only. |
| 4.2.1 | IDOR protection | Met | `visible_request_or_404` everywhere; `tests/test_access.py`. |
| 4.2.2 | CSRF protection | Met | Django CSRF on all forms. |
| 4.3.1 | Admin interfaces protected | Met | Django admin needs `is_staff`, given only to administrators. MFA is a gap (threat model 3). |

## V5 Validation, sanitisation and encoding

| # | Requirement | Status | How |
|---|---|---|---|
| 5.1.1–5.1.4 | Input validated by allow-list, type and range | Met | Django forms; phone numbers normalised to E.164; coordinates are floats, then checked against the county polygon; categories from a fixed table. |
| 5.2.x | Sanitisation | Met | Free text is stored as-is and always escaped on output. |
| 5.3.1, 5.3.3 | Output encoding, XSS | Met | Django auto-escaping; CSP without `unsafe-inline`. |
| 5.3.4 | Parameterised queries | Met | ORM throughout; the one raw query (`analytics._SNAPSHOT_SQL`) uses bound parameters. |

## V7 Errors and logging

| # | Requirement | Status | How |
|---|---|---|---|
| 7.1.1 | No credentials or session IDs in logs | Met | Gunicorn access log has no cookies. Open311 query-string keys are a documented exception. |
| 7.4.1 | Generic error messages | Met | DEBUG off in production; Django's default 404/500 pages. |

## V8 Data protection

| # | Requirement | Status | How |
|---|---|---|---|
| 8.2.1 | Anti-caching for sensitive data | Met | Photos `Cache-Control: private`; sign-in pages `no-store`. |
| 8.3.1 | Sensitive data not in URLs | Met | Draft reports are kept in the session, not the query string. Open311 key: see V7. |
| 8.3.4 | Personal data identified and minimised | Met | EXIF stripped; redacted public API; SMS without details (`docs/decisions.md#privacy`). |

## V9 Communications

| # | Requirement | Status | How |
|---|---|---|---|
| 9.1.1 | TLS everywhere | Met | `SECURE_SSL_REDIRECT`, HSTS (30 days) when DEBUG is off; Render terminates TLS. |

## V10 Malicious code / V14 Configuration

| # | Requirement | Status | How |
|---|---|---|---|
| 10.3.2 | Third-party code from trusted sources, pinned | Met | All Python dependencies pinned; Leaflet vendored (1.9.4), no CDN. |
| 14.2.1 | Components up to date | **Ongoing** | No automated dependency alerts yet; enable Dependabot on the repository. |
| 14.4.x | Security headers | Met | CSP, XFO, nosniff, Referrer-Policy, Permissions-Policy, COOP, CORP, HSTS. ZAP baseline: 0 failures. |

## V12 Files and resources

| # | Requirement | Status | How |
|---|---|---|---|
| 12.1.1 | Upload size limits | Met | 5 MB file, 40 MP decoded, 6 MB request. |
| 12.2.1 | File type checked by content | Met | Pillow detects the format from the bytes, not the name. |
| 12.4.1 | Uploads stored outside the web root | Met | In the database, served only through an authorised view. |
| 12.5.x | Execution of uploaded content | Met | Re-encoded JPEG; never served from a static path. |

**Summary:** Level 1 is met except for credential recovery, phone verification and
password-change notification (V2.2.3, V2.5, V2.7), which all need SMS one-time codes, and the
password minimum (10 instead of 12). These are listed as known gaps in the README.
