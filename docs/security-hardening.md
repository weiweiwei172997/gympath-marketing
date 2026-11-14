# Security hardening

Updated: 2026-10-12. Scope: the independent GymPath website and account/plan service.

## Application and trust boundaries

Four native HTML pages use only local CSS, JavaScript and SVG. Browser requests use relative same-origin API URLs. The service exposes 12 named public file routes and nine API operations; there are no uploads, administrative endpoints, webhooks, external AI calls or shell commands driven by visitor input. SQLite accounts and explicitly saved plans are private and separate from the PythonAnywhere code directory. The WSGI adapter trusts exactly one platform proxy for the client address and HTTPS scheme; a directly exposed WSGI socket must not use that adapter.

## Existing protections reviewed

- Passwords use salted scrypt; session tokens have 256 bits of randomness and only their SHA256 digest is stored. Login errors do not distinguish a missing account from a wrong password. Passwords, cookies and CSRF tokens are not written to browser storage or client logs.
- HTTPS session cookies use Secure, HttpOnly and SameSite=Lax. Sessions last seven days and each account has at most five current sessions.
- Account writes require the exact same Origin; saved-plan writes and logout also require a constant-time CSRF check. Requests cannot supply their own saved plan: the server generates it from four validated preferences. Owners are included in all plan reads/deletes, and each owner can save at most 20 plans.
- All SQLite queries use bound parameters. Plan preferences use strict enumerations and bounded integer fields. Account field lengths are bounded; rejected values and credentials are not included in validation errors.
- Public files are an explicit route allowlist. Backend files, references, source manifests, SQLite files and tool files are not publicly served. Dynamic browser text uses textContent/createTextNode; teaching links require HTTPS and exact allowed domains with noopener/noreferrer.

## Changes in this hardening pass

| Risk or protection | Implemented behavior | Verification |
| --- | --- | --- |
| Authentication budgets reset by worker/reload | Private abuse.sqlite3 records atomic attempts across workers and restarts: each address 10 attempts per 600 seconds, global 240 per 600 seconds, at most 1024 address buckets. Stores address hashes and attempt times, not raw addresses or credentials. Storage/lock errors refuse authentication. | Separate limiter instances, a separate Python process, concurrent requests, expiry, capacity and storage failures |
| Unbounded registration storage | Default total account limit 200; count and insert share an immediate write transaction. GYMPATH_MAX_ACCOUNTS accepts 1–1000. Full quota pauses new registration; existing login and saved plans remain usable. | Concurrent quota test and existing-account login/save |
| Oversized, slow or ambiguous JSON | API body limited to 4096 actual bytes, including chunked bodies and dishonest/missing Content-Length; ten-second read timeout, explicit JSON content type, no compressed payloads or duplicate object fields. Very long length headers are rejected without integer conversion errors. | Stream-level tests, bad encoding/nesting/metadata and safe errors |
| Excess password/plan work | Each worker handles at most two concurrent register/login operations and eight other API operations; excess returns 503 with Retry-After. Other API requests have a bounded per-worker 120/minute/address limit. | Counters, cleanup, direct ASGI and WSGI regression |
| Script injection and framing defense | CSP permits only same-origin scripts/styles/images/API requests; no inline execution, plugins, base tags, embedded frames or native form submission. Account form explicitly uses POST as a static fallback. Dynamic text remains safe without relying on CSP. | Four-page resource inspection, 24 URL/text checks and response header tests |
| Credential/error exposure | API responses are no-store. Unavailable storage returns a generic 503; unexpected API exceptions return a generic 500 and log only the exception class. No request body, token, cookie or database path is logged. | Injected storage/unexpected errors and invalid payloads |
| Host spoofing | Validates Host syntax/duplicates; GYMPATH_ALLOWED_HOSTS sets exact hostnames on deployment. Do not use attacker-supplied forwarded host headers. | Exact-host/suffix/duplicate checks |
| Browser/network headers | nosniff, DENY framing, same-origin referrer/resource/opener policy, camera/microphone/location/payment/USB disabled, HTTPS-only HSTS for one year. | Public/API/error responses and untrusted proxy-header test |
| Dependency drift | requirements-runtime.lock pins the 18 runtime/WSGI packages, including Python 3.10 compatibility dependencies; requirements-trial.txt applies the lock as constraints. pip-audit reported no known advisories on 2026-10-12. | artifacts/security-dependency-audit.json |

Linux private account and rate-limit database files use mode 600, with newly created data directories mode 700. Windows permissions use the current user's filesystem ACL. Never map data or the project root to public static files. Authentication-limit address hashes are pseudonymous security records, not a guarantee of anonymity; stale buckets are cleaned when authentication is attempted.

## Validation and deployment

Full regression after the code changes and platform compatibility fix: **583 passed, 2 skipped**. The skipped checks use real Unix fork, which is unavailable on Windows. The independent reviewer checked Python 3.10 syntax, stream-size enforcement, slow reads, CSP compatibility and all public page resources. Existing WSGI checks ensure the password-work budget is released before the adapter finishes the final body. All tests use temporary SQLite databases and synthetic credentials; no load or penetration-testing traffic was sent to the public site.

PythonAnywhere inserts an empty WSGI CONTENT_LENGTH for bodyless requests. The WSGI bridge now normalizes that platform sentinel before a2wsgi translates it into an HTTP header. Regression covers account-state GET, bodyless logout POST and saved-plan DELETE; directly supplied empty HTTP Content-Length remains rejected, and a real oversized body remains limited. The first security Reload exposed this compatibility issue; the corrected package was Reloaded at 23:24 Asia/Shanghai and normal public API GETs were verified as 200 afterward.

The 18 locked runtime packages were queried against the public advisory database with pip-audit. Zero known vulnerabilities is a result for that date and those versions; it is not proof of future safety. Dependency installation/update must use trusted PyPI releases and rerun the regression and advisory check.

The corrected security update was uploaded, remotely hash-verified, extracted and Web Reloaded on 2026-10-12. Benign checks at 23:27:51 Asia/Shanghai confirmed four HTTPS pages, health and anonymous account-state endpoints return 200 with the expected CSP, HSTS and other protections; APIs use no-store, five private file paths return 404, and HTTP redirects to HTTPS without sending HSTS. Evidence: artifacts/pythonanywhere-security-validation.json. This increment used zero authentication calls and did not read account contents. Earlier account/plan and real-phone core-flow results remain historical evidence; this pass does not claim a new exhaustive phone test or a professional penetration-test certification.

## Operation and remaining limits

- Free classroom hosting and these application budgets do not provide network-layer DDoS protection or a continuous-uptime guarantee. General API/concurrency budgets are per worker; authentication budgets share a private SQLite store.
- Multiple students sharing a campus public address also share the 10-attempt/10-minute authentication allowance. The website returns a waiting message and Retry-After instead of repeatedly computing passwords. No CAPTCHA, email verification, invitation code or password recovery is implemented. Distributed malicious signups can still consume the 200-account quota; observe usage before widening public access.
- Keep private backups of the external SQLite account directory and restrict platform access. Do not include backups, rate-limit data, passwords, session files or personal screenshots in submitted/source archives. Review platform error logs without exposing them publicly.
- Set GYMPATH_ALLOWED_HOSTS to the deployment hostname before importing the app. Local use may set localhost,127.0.0.1; an unset list allows syntactically valid hostnames for portable source copies and test fixtures.
- The free Web app currently shows expiry 2026-11-12 and needs renewal. Avoid increasing the default account quota without reviewing the 512 MiB storage allocation.
