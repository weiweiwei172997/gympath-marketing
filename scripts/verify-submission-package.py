"""Verify the source ZIP and run core checks from an isolated extraction."""

from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import subprocess
import sys
import tempfile
from threading import Thread
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent.parent
PAGES = ("index.html", "demo.html", "trial.html", "account.html")
RESOURCES = ("styles.css", "script.js", "trial.js", "account.js",
             "assets/mark.svg", "assets/training-path.svg")


class PageStructure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.resources = []
        self.forms = 0
        self.disabled_fieldsets = 0
        self.noscripts = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "form":
            self.forms += 1
        elif tag == "fieldset" and "disabled" in attributes:
            self.disabled_fieldsets += 1
        elif tag == "noscript":
            self.noscripts += 1
        if tag in {"script", "img"} and attributes.get("src"):
            self.resources.append(attributes["src"])
        elif tag == "link" and attributes.get("href"):
            self.resources.append(attributes["href"])


def static_probe(site_dir: Path) -> dict:
    public_paths = {"/", "/favicon.ico"} | {"/" + name for name in PAGES + RESOURCES}

    class LocalPublicFiles(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(site_dir), **kwargs)

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path not in public_paths:
                self.send_error(404)
                return
            if path == "/favicon.ico":
                self.path = "/assets/mark.svg"
            super().do_GET()

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalPublicFiles)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        for page in PAGES:
            with urlopen(f"{base}/{page}", timeout=5) as response:
                assert response.status == 200, page
                content = response.read().decode("utf-8")
            structure = PageStructure()
            structure.feed(content)
            if structure.forms or page == "demo.html":
                assert structure.noscripts, f"Missing noscript fallback: {page}"
            assert structure.disabled_fieldsets >= structure.forms, f"Unsafe no-JS form: {page}"
            for resource in structure.resources:
                parsed = urlsplit(resource)
                assert not parsed.scheme and not parsed.netloc, f"External runtime resource: {resource}"
                filename = unquote(parsed.path)
                assert filename in RESOURCES, f"Unexpected local dependency: {resource}"
                with urlopen(f"{base}/{filename}", timeout=5) as response:
                    assert response.status == 200
        for path in ["/api/health", "/backend/auth.py", "/data/gympath.sqlite3"]:
            try:
                urlopen(base + path, timeout=5)
            except HTTPError as error:
                assert error.code == 404, path
            else:
                raise AssertionError(f"Static fallback exposed backend/private path: {path}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return {"pages_and_resources_loaded": True, "static_api_unavailable": True,
            "no_js_forms_disabled": True, "local_assets_only": True,
            "scope": "HTTP and HTML fallback structure, not browser JavaScript interaction"}


def backend_probe(site_dir: Path, data_dir: Path) -> dict:
    sys.path.insert(0, str(site_dir))
    os.environ["GYMPATH_DATA_DIR"] = str(data_dir)
    os.environ["GYMPATH_ALLOWED_HOSTS"] = "testserver,submission-check.local,package-check.pythonanywhere.com,localhost,127.0.0.1"
    from fastapi.testclient import TestClient
    from backend import app as site
    from backend import auth

    assert Path(site.__file__).resolve().is_relative_to(site_dir)
    assert site.SITE_ROOT == site_dir
    base = "https://submission-check.local"
    preferences = {"level": "beginner", "goal": "health", "days_per_week": 2,
                   "minutes_per_session": 20}
    credentials = {"username": "SubmissionCheck", "password": "Gp8-" + secrets.token_urlsafe(24)}
    other_credentials = {"username": "SubmissionOther", "password": "Gp8-" + secrets.token_urlsafe(24)}
    private_paths = ["/backend/auth.py", "/backend/security.py", "/data/gympath.sqlite3",
                     "/docs/security-hardening.md", "/SUBMISSION-MANIFEST.json"]
    with TestClient(site.app, base_url=base, headers={"Origin": base}) as client:
        for path in site.PUBLIC_FILES:
            assert client.get(path).status_code == 200, path
        for path in private_paths:
            assert client.get(path).status_code == 404, path
        assert client.post("/api/plan", json=preferences).status_code == 200
        assert not auth.database_path().exists(), "Guest plan initialized account database"
        bad_origin = client.post("/api/auth/register", json=credentials,
                                 headers={"Origin": "https://other.invalid"})
        assert bad_origin.status_code == 403
        registered = client.post("/api/auth/register", json=credentials)
        assert registered.status_code == 201, registered.status_code
        cookie = registered.headers["Set-Cookie"].lower()
        assert all(flag in cookie for flag in ("secure", "httponly", "samesite=lax", "path=/"))
        csrf = {"X-CSRF-Token": registered.json()["csrf_token"]}
        assert client.post("/api/plans", json={"preferences": preferences}).status_code == 403
        saved = client.post("/api/plans", json={"preferences": preferences}, headers=csrf)
        assert saved.status_code == 201, saved.status_code
        plan_id = saved.json()["id"]
        with TestClient(site.app, base_url=base, headers={"Origin": base}) as other:
            second = other.post("/api/auth/register", json=other_credentials)
            assert second.status_code == 201, second.status_code
            assert other.get("/api/plans").json() == {"plans": []}
            other_csrf = {"X-CSRF-Token": second.json()["csrf_token"]}
            assert other.delete(f"/api/plans/{plan_id}", headers=other_csrf).status_code == 404
        assert client.post("/api/auth/logout", headers=csrf).status_code == 204
        assert client.get("/api/plans").status_code == 401
    with TestClient(site.app, base_url=base, headers={"Origin": base}) as fresh:
        login = fresh.post("/api/auth/login", json=credentials)
        assert login.status_code == 200, login.status_code
        plans = fresh.get("/api/plans").json()["plans"]
        assert [entry["id"] for entry in plans] == [plan_id]
        assert plans[0]["preferences"] == preferences
        assert fresh.delete(f"/api/plans/{plan_id}", headers={
            "X-CSRF-Token": login.json()["csrf_token"]}).status_code == 204
        assert fresh.get("/api/plans").json() == {"plans": []}
    assert auth.database_path().is_file()
    assert auth.database_path().resolve().is_relative_to(data_dir)
    assert not (site_dir / "data").exists()

    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    from deployment import pythonanywhere_wsgi

    bridge = Client(pythonanywhere_wsgi.application, Response)
    assert bridge.get("/api/health", base_url="http://package-check.pythonanywhere.com", headers={
        "X-Forwarded-Proto": "https", "X-Forwarded-For": "192.0.2.23",
    }).status_code == 200
    return {"public_files_passed": len(site.PUBLIC_FILES), "private_files_404": len(private_paths),
            "guest_generation_does_not_store": True, "cookie_flags": True,
            "registration_save_logout_login": True, "csrf_and_origin_rejected": True,
            "account_isolation": True, "fresh_client_persistence": True,
            "owner_delete": True, "optional_wsgi_bridge": True,
            "data_outside_extracted_code": True, "credentials_logged": False}


def load_builder():
    spec = importlib.util.spec_from_file_location("submission_builder", ROOT / "scripts/build-submission-package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify() -> dict:
    builder = load_builder()
    package = ROOT / "artifacts" / builder.PACKAGE_NAME
    checksum = hashlib.sha256(package.read_bytes()).hexdigest()
    checksum_file = ROOT / "artifacts/GymPath-BA4043-Source.sha256"
    assert checksum_file.read_text(encoding="utf-8").strip() == f"{checksum}  {package.name}"
    with tempfile.TemporaryDirectory(prefix="gympath-submission-check-") as scratch:
        scratch_dir = Path(scratch)
        with ZipFile(package) as archive:
            names = archive.namelist()
            assert len(names) == len(set(names)), "Duplicate ZIP entries"
            relative_names = []
            for entry in archive.infolist():
                name = entry.filename
                path = PurePosixPath(name)
                assert path.parts and path.parts[0] == builder.ARCHIVE_ROOT, "Incorrect ZIP root"
                assert not path.is_absolute() and ".." not in path.parts and "\\" not in name and ":" not in name
                assert len(path.parts) > 1 and not entry.is_dir(), "Unexpected directory entry"
                assert stat.S_ISREG(entry.external_attr >> 16), "Symlink or special file in ZIP"
                assert entry.date_time == (1980, 1, 1, 0, 0, 0), "Non-deterministic ZIP timestamp"
                relative = "/".join(path.parts[1:])
                builder.validate_name(relative)
                content = archive.read(name)
                assert not content.startswith(b"SQLite format 3\x00")
                assert not builder.PRIVATE_KEY.search(content), "Private key in ZIP"
                relative_names.append(relative)
            assert set(relative_names) == set(builder.FILES) | {builder.MANIFEST_NAME}, "Source allowlist mismatch"
            manifest_bytes = archive.read(f"{builder.ARCHIVE_ROOT}/{builder.MANIFEST_NAME}")
            assert (ROOT / "artifacts/GymPath-BA4043-Source-manifest.json").read_bytes() == manifest_bytes
            manifest = json.loads(manifest_bytes)
            assert manifest["includes_runtime_data"] is False
            assert [entry["path"] for entry in manifest["files"]] == sorted(builder.FILES)
            for entry in manifest["files"]:
                content = archive.read(f"{builder.ARCHIVE_ROOT}/{entry['path']}")
                assert len(content) == entry["bytes"]
                assert hashlib.sha256(content).hexdigest() == entry["sha256"]
                assert content == builder.checked_source(entry["path"]), f"ZIP is stale: {entry['path']}"
            reproducible = io.BytesIO()
            with ZipFile(reproducible, "w", compression=ZIP_DEFLATED, compresslevel=9) as rebuilt:
                for name in sorted(builder.FILES):
                    rebuilt.writestr(builder.fixed_entry(name), archive.read(f"{builder.ARCHIVE_ROOT}/{name}"), compresslevel=9)
                rebuilt.writestr(builder.fixed_entry(builder.MANIFEST_NAME), manifest_bytes, compresslevel=9)
            assert reproducible.getvalue() == package.read_bytes(), "Reproducible ZIP rebuild mismatch"
            # Extraction is performed only after every archive path and type was checked.
            archive.extractall(scratch_dir)
        site_dir = scratch_dir / builder.ARCHIVE_ROOT
        child_env = os.environ.copy()
        completed = subprocess.run(
            [sys.executable, str(site_dir / "scripts/verify-submission-package.py"),
             "--probe", str(site_dir), str(scratch_dir / "isolated-gympath-data")],
            cwd=site_dir, env=child_env, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        probe = json.loads(completed.stdout)
        result = {
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "package": package.name, "package_sha256": checksum,
            "entries": len(names), "bytes": package.stat().st_size,
            "single_root": builder.ARCHIVE_ROOT, "manifest_hashes_match": True,
            "source_allowlist_complete": True, "matches_current_source": True,
            "private_runtime_paths_excluded": True, "zip_slip_and_symlinks_excluded": True,
            "reproducible_rebuild_matches": True, "isolated_extraction": True,
            "scope": "Local extracted source and fresh temporary data; no public-host or real-phone retest",
            **probe,
        }
    evidence = ROOT / "artifacts/GymPath-BA4043-Source-validation.json"
    evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--probe":
        site_dir = Path(sys.argv[2]).resolve()
        print(json.dumps({"static_fallback": static_probe(site_dir),
                          "backend_core": backend_probe(site_dir, Path(sys.argv[3]).resolve())}))
    else:
        verify()
