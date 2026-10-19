# Threat model (STRIDE)

**What we protect:** citizens' identities and phone numbers; where they live (report locations
and photos are often taken at home); the integrity of case history (it's the county's
accountability record); and the service itself.

**Who interacts:** citizens (self-registered, untrusted), county officers (one department each),
administrators, Open311 client apps (with a citizen's key), Africa's Talking (outbound SMS), and
anonymous visitors.

**Trust boundaries:** browser ↔ app (HTTPS); Open311 client ↔ app; app ↔ PostgreSQL (Neon); app ↔
Africa's Talking; app ↔ boundary download at setup (HDX).

| | Threat | Where | Mitigation | Evidence |
|---|---|---|---|---|
| **S**poofing | Password guessing on citizen or officer accounts | Sign-in | Django PBKDF2 hashing; minimum 10 characters plus the common-password and numeric checks; django-axes locks a number+IP for 15 min after 5 failures, counting `07…` and `+2547…` as one number | `test_lockout_after_five_failures` |
| | Stolen Open311 key used to file reports as someone | Open311 POST | Per-citizen keys, stored as SHA-256, shown once, revocable; reports are attributed to the key's owner | `test_revoked_key_is_refused`, `test_keys_are_stored_hashed` |
| | Someone registers another person's phone number, so that person gets SMS | Registration | **Not mitigated**: no OTP check on registration. Impact is limited because messages carry only a reference and a status. See *Known gaps*. | – |
| **T**ampering | Status forced past the rules (e.g. closing without resolving) | Any code path | State machine in the service layer **and** a PostgreSQL trigger generated from the same table | `test_trigger_matches_transition_table` (all 20 pairs), property test |
| | History edited or deleted to hide a missed deadline | DB | Append-only trigger on `CaseEvent` rejects UPDATE/DELETE; admin shows history read-only | `test_history_is_append_only` |
| | Cross-site request forgery against status actions | Forms | Django CSRF on all forms; Open311 POST is CSRF-exempt but needs an API key and ignores cookies | `test_post_without_csrf_token_still_works` |
| | Malicious upload (polyglot, decompression bomb, script) | Photo | Pillow decodes, verifies and **re-encodes** from pixels; JPEG/PNG/WebP only; 4 MB and 40 MP limits; served with `nosniff` from an authorised view | `test_polyglot_payload_does_not_survive`, `test_non_images_are_refused` |
| **R**epudiation | Officer denies having resolved or merged a case | History | Every change records actor, role at the time, timestamp and note; notes are required for resolve, reopen and merge | `history_explains_status` invariant |
| **I**nformation disclosure | Citizen reads another citizen's report by changing the ID (IDOR) | Detail, photo, action URLs | One access function for every case view; strangers get 404, the same as for a missing case | `tests/test_access.py` (14 tests) |
| | Location leaked through photo EXIF | Photo | EXIF stripped by re-encoding; orientation applied first | `test_gps_and_device_exif_are_removed` |
| | Personal data in public Open311 output | Open311 GET | No description, photo or reporter; coordinates rounded to ~110 m | `test_open311_public_view_is_redacted` |
| | Personal data on a phone's lock screen | SMS | Messages carry reference, category and status only | `test_messages_carry_no_description_or_location` |
| | API key in access logs (query string) | Open311 POST | Accepted only because real clients send it there; the body is preferred; documented to client developers | – |
| | Clickjacking, XSS, MIME sniffing | All pages | Django auto-escaping; CSP `default-src 'self'` with no inline script or style; `X-Frame-Options: DENY`; `frame-ancestors 'none'`; `nosniff`; CORP/COOP same-origin | ZAP baseline, `test_security_headers` |
| **D**enial of service | Report flooding by one account | Report form, Open311 | **Partly**: sign-in required for every report; duplicates are collapsed. No per-account rate limit yet. | – |
| | SMS provider outage blocks officers | Status changes | Outbox: SMS sent after commit, failures retried later; a status change never waits on Africa's Talking | `test_provider_failure_is_kept_for_retry` |
| **E**levation of privilege | Officer acts on another department's cases | Actions, queue | Role is computed per case: officer only for their department's categories | `test_officer_of_another_department_cannot_act`, `..._gets_404` |
| | Citizen opens staff pages | Queue, analytics | `staff_required` on every staff view | `test_citizens_cannot_open_staff_pages` |
| | Self-registration as an officer | Registration | The form has no role field; roles are set only in the admin | `RegistrationForm.Meta.fields` |

## Known gaps (accepted for this version)

1. **No phone verification at registration.** A real deployment should send a one-time code
   via Africa's Talking before activating the account.
2. **No per-account rate limit** on creating reports or Open311 POSTs.
3. **The admin has no second factor.** Staff accounts should use 2FA, e.g. `django-otp`.
4. **Demo accounts on the public deployment** share one password. They exist for reviewers and
   must not exist in a real deployment.
