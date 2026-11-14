# GymPath — BA4043 Case Study 1 source code

This is the website source package, with a native HTML/CSS/JavaScript frontend
and an independent FastAPI/SQLite service. It includes source, local assets,
dependencies, tests, operating instructions and code/resource acknowledgements.
The English Word report is a separate course deliverable.

Public website: https://weiweiwei36157.pythonanywhere.com
The free web app currently needs renewal before 12 November 2026. This source
package runs independently of that hosting account and contains no account
credentials, existing users, saved plans, databases or personal photographs.

## Start the website

For marketing and fixed demonstrations only, open `index.html` or `demo.html`
in a browser. No frontend build, Node.js or Python is required. Demo forms
never send or save their inputs. Enabling JavaScript allows example switching
and demonstration feedback. Without JavaScript, the initial content remains
readable and forms remain disabled.

For real accounts and generated/saved plans, use Python 3.10 or newer. Open a
terminal in the extracted `gympath-marketing` directory:

```text
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS/Linux
source .venv/bin/activate
```

Install dependencies and start:

```text
python -m pip install -r requirements-trial.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8081
```

`requirements-runtime.lock` contains exact runtime versions resolved in an
independent environment. To reproduce those versions, install it with
`python -m pip install -r requirements-runtime.lock` instead of the unpinned
runtime ranges. Its Python-version markers support Python 3.10 and newer.

Open http://127.0.0.1:8081/ . Keep the terminal open; Ctrl+C stops the service.
On Windows, `scripts/start-local.ps1` is an alternative after installation.
Only trusted local proxies should supply forwarded headers; do not expose a
server with unrestricted proxy-header trust.

A new SQLite database is created on first account use, by default at
`data/gympath.sqlite3`. Set `GYMPATH_DATA_DIR` before starting if another
private directory is preferred. Do not include that directory in source
submissions or make it publicly accessible. Existing accounts on the public
website are not copied to the local installation.

## Core review flow

1. Read the homepage and open the fixed training examples.
2. Switch examples/days, expand exercise details and try demo feedback.
3. Open the trial page, choose the four preferences and generate a plan.
4. Register a new test account or log in. New passwords need at least eight
   characters, including an ASCII letter and a digit.
5. Generate a plan and deliberately click **Save to account**. Generation
   alone does not store the preferences or create an account.
6. Open the account page and inspect the saved plan, log out, log in again
   and refresh. The saved plan should remain. Delete a test plan if needed.

Only registration/login and deliberate plan saving use account storage.
There is no collection of email addresses, uploaded photos or old account
data. Training time is an estimate, not a guaranteed completion time.

## File responsibilities

| Files | Responsibility |
| --- | --- |
| `index.html` | Public marketing page and navigation |
| `demo.html`, `script.js` | Fixed examples and local-only feedback |
| `trial.html`, `trial.js` | Anonymous plan generation and explicit saving |
| `account.html`, `account.js` | Real account forms and saved-plan management |
| `styles.css`, `assets/` | Shared responsive styling and two original SVGs |
| `backend/app.py`, `auth.py`, `security.py` | Validated API, account storage and request safeguards |
| `backend/plan_engine.py`, `plan_adapter.py`, `locale_zh.py` | Source rules, time-fit adaptation and display translations |
| `deployment/pythonanywhere_wsgi.py` | Optional WSGI hosting bridge |
| `tests/`, `requirements-test.txt`, `requirements-runtime.lock` | Automated regression checks and reproducible runtime dependencies |
| `docs/`, source manifest | Packaging, safety scope and code/resource acknowledgements |

## Tests and package verification

```text
python -m pip install -r requirements-test.txt -r requirements-deploy.txt
python -m pytest -q
python scripts/build-submission-package.py
python scripts/verify-submission-package.py
```

The WSGI tests use the optional deployment dependencies. Fork-dependent tests
are skipped on Windows. Package verification extracts into a temporary
directory, checks file hashes and private-path exclusion, serves the static
pages, and checks the backend with a new temporary SQLite database. It never
uses accounts or a database from the working website.

`SUBMISSION-MANIFEST.json` records source file sizes and SHA256 values. The
external `GymPath-BA4043-Source.sha256` verifies the complete ZIP. Packaging
uses an explicit allowlist and produces identical bytes for identical source
files on the same Python/zlib environment.

## Optional deployment and security scope

The local backend is sufficient for reviewing the submitted code. Optional
WSGI hosting requires `requirements-deploy.txt` and imports
`deployment.pythonanywhere_wsgi.application` after setting
`GYMPATH_DATA_DIR` to a private directory outside the code directory. Use the
adapter only behind PythonAnywhere's trusted proxy, enable Force HTTPS and
never map the complete code/data directories as static files. Preserve the
database when updating source. Configure the allowed public hostname as
described in `docs/security-hardening.md`.

Security protections and their verified scope are documented in
`docs/security-hardening.md`. A small free-hosted classroom trial does not
provide a dedicated DDoS protection service or an independent penetration
test. Video-link metadata was checked earlier; individual video playback
and actual print-pagination remain outside the completed verification scope.

## Source acknowledgements

See `docs/source-provenance.md` and
`references/gympath-original/plan-engine-source.json`. The frontend is native
HTML/CSS/JavaScript with original SVGs. Backend components are FastAPI,
Pydantic, uvicorn and Python's SQLite/scrypt implementations; a2wsgi and
Werkzeug are optional hosting components.
