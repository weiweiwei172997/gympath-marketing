"""Build the course source ZIP from a reviewed, explicit file allowlist.

No directory recursion, runtime accounts, databases or private evidence are used.
ZIP timestamps, permissions and entry order are fixed for reproducible output.
"""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
PACKAGE_NAME = "GymPath-BA4043-Source.zip"
ARCHIVE_ROOT = "gympath-marketing"
MANIFEST_NAME = "SUBMISSION-MANIFEST.json"
FILES = (
    "README-SUBMISSION.md",
    "index.html", "demo.html", "trial.html", "account.html",
    "styles.css", "script.js", "trial.js", "account.js",
    "assets/mark.svg", "assets/training-path.svg",
    "backend/__init__.py", "backend/app.py", "backend/auth.py",
    "backend/security.py", "backend/plan_engine.py",
    "backend/plan_adapter.py", "backend/locale_zh.py",
    "deployment/__init__.py", "deployment/pythonanywhere_wsgi.py",
    "requirements-trial.txt", "requirements-test.txt", "requirements-deploy.txt", "requirements-runtime.lock",
    "scripts/start-local.ps1", "scripts/build-submission-package.py",
    "scripts/verify-submission-package.py",
    "tests/__init__.py", "tests/conftest.py", "tests/test_accounts.py", "tests/test_trial_api.py",
    "tests/test_plan_adapter.py", "tests/test_deployment_wsgi.py",
    "tests/test_security.py", "tests/test_auth_security.py",
    "docs/source-submission.md", "docs/source-provenance.md",
    "docs/security-hardening.md",
    "references/gympath-original/plan-engine-source.json",
)
FORBIDDEN_PARTS = {
    "data", "tools", "artifacts", "screenshots", "uploads", "photos",
    "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".git",
}
ALLOWED_SUFFIXES = {".html", ".css", ".js", ".svg", ".py", ".ps1", ".txt", ".lock", ".md", ".json"}
PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----")


def validate_name(name: str) -> None:
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts or "\\" in name
            or ":" in name or name != path.as_posix()):
        raise ValueError(f"Unsafe archive path: {name}")
    if FORBIDDEN_PARTS.intersection(part.lower() for part in path.parts):
        raise ValueError(f"Private/runtime path excluded: {name}")
    if path.name.lower().startswith(".env") or path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError(f"Unexpected file type: {name}")


def checked_source(name: str) -> bytes:
    validate_name(name)
    source = ROOT / name
    current = source
    while current != ROOT:
        if current.is_symlink():
            raise ValueError(f"Symlinks are excluded: {name}")
        current = current.parent
    if not source.is_file() or not source.resolve().is_relative_to(ROOT):
        raise ValueError(f"Missing or outside-workspace source: {name}")
    content = source.read_bytes()
    if content.startswith(b"SQLite format 3\x00") or PRIVATE_KEY.search(content):
        raise ValueError(f"Database/private-key content excluded: {name}")
    return content


def fixed_entry(name: str) -> ZipInfo:
    entry = ZipInfo(f"{ARCHIVE_ROOT}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
    entry.create_system = 3
    entry.external_attr = (0o100644 << 16)
    entry.compress_type = ZIP_DEFLATED
    return entry


def build() -> dict:
    if len(FILES) != len(set(FILES)):
        raise ValueError("Duplicate source allowlist entry")
    contents = {name: checked_source(name) for name in sorted(FILES)}
    manifest = {
        "schema_version": 1,
        "package": PACKAGE_NAME,
        "archive_root": ARCHIVE_ROOT,
        "purpose": "BA4043 Case Study 1 website source code; separate English report is not included",
        "includes_runtime_data": False,
        "reproducible": "Sorted entries, fixed ZIP timestamps and permissions; no build timestamp",
        "files": [
            {"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            for name, content in contents.items()
        ],
    }
    encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    ARTIFACTS.mkdir(exist_ok=True)
    package = ARTIFACTS / PACKAGE_NAME
    pending = ARTIFACTS / f"{PACKAGE_NAME}.tmp"
    with ZipFile(pending, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in contents.items():
            archive.writestr(fixed_entry(name), content, compresslevel=9)
        archive.writestr(fixed_entry(MANIFEST_NAME), encoded, compresslevel=9)
    pending.replace(package)
    (ARTIFACTS / "GymPath-BA4043-Source-manifest.json").write_bytes(encoded)
    checksum = hashlib.sha256(package.read_bytes()).hexdigest()
    (ARTIFACTS / "GymPath-BA4043-Source.sha256").write_text(
        f"{checksum}  {PACKAGE_NAME}\n", encoding="utf-8")
    result = {"zip": str(package), "entries": len(contents) + 1,
              "bytes": package.stat().st_size, "sha256": checksum}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    build()
