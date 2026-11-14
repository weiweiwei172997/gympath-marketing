# Source provenance for the submitted website

This note documents reused code and components. It is not evidence of user
interviews, team contribution percentages or fitness outcomes.

## Application code and assets

- The frontend consists of four semantic HTML pages, one stylesheet and
  three DOM-based JavaScript controllers. It uses local assets and browser
  APIs without a frontend build step.
- Both files in `assets/` are newly authored SVGs. They contain no user photos
  and are not downloaded workout images.
- Fixed examples and demo-feedback rules are separate from the generated
  training plan service. Their forms do not submit or save information.
- The independent account/storage service was written for this project. It
  does not import the former API/storage module or migrate old personal data.

## Training-rule extraction and adaptation

The source version is recorded as Git commit
`b11a43c9794e91f1c592f6988b9e40c7fef80c97`. The source `project.py` SHA256 is
`24aab384f75f0f3974bb5865a00affca55ed809138f57d6bf54a9db2f64a87ca`.
`backend/plan_engine.py` SHA256 at extraction is
`5134e08236755326f61753e51fc4551d30502dcdd5fd006fdf4d19ed4ee43ebc`.

The included `references/gympath-original/plan-engine-source.json` records
each extracted function/constant, source lines and hashes. Extraction copied
30 functions and eight constants using AST dependency selection. Thirty-seven
of 38 source sections were retained byte-for-byte; `enrich_workout_plan` was
replaced at the catalog boundary to avoid importing the complete original
application/data catalog.

`backend/plan_adapter.py` reorganizes those source actions into the requested
time budget and caps frequency without increasing the requested number of
sessions. `backend/locale_zh.py` translates display strings while preserving
source names/prescriptions for provenance. These changes are not evidence
that the plans have been clinically or experimentally validated.

The source manifest identifies the functions and constants used by the
training engine. It is a code acknowledgement, not a runtime dependency.

## Components and official documentation

| Component | Use and source |
| --- | --- |
| HTML/CSS/JavaScript | Native frontend; https://developer.mozilla.org/ |
| FastAPI | Independent local API; https://fastapi.tiangolo.com/ |
| Pydantic 2 | Strict request validation; https://docs.pydantic.dev/latest/ |
| uvicorn | Local ASGI server; https://www.uvicorn.org/ |
| SQLite / sqlite3 | New local account/plan database; https://www.sqlite.org/ and https://docs.python.org/3/library/sqlite3.html |
| hashlib.scrypt | Salted password verification; https://docs.python.org/3/library/hashlib.html#hashlib.scrypt |
| a2wsgi | Optional ASGI-to-WSGI bridge; https://pypi.org/project/a2wsgi/ |
| Werkzeug | Optional WSGI proxy integration; https://werkzeug.palletsprojects.com/ |
| pytest / HTTPX | Regression and isolated API checks; https://docs.pytest.org/ and https://www.python-httpx.org/ |

No frontend template, CDN, external font or frontend framework is used.
Dependency ranges and optional pinned bridge version are in the three
`requirements-*.txt` files. Exact resolved environments can vary; regression
checks should be run when installing or updating them.

The submitted `requirements-runtime.lock` pins the runtime versions resolved
in an independent environment, including a Python 3.10 compatibility marker.
