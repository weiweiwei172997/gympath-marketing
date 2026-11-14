"""Independent accounts and saved plans; never open the original GymPath store."""

from collections import OrderedDict, deque
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
from threading import Lock
import time


SESSION_SECONDS = 7 * 24 * 60 * 60
COOKIE_NAME = "gympath_session"
PLAN_LIMIT = 20
ACCOUNT_LIMIT = 200
SCRYPT_N, SCRYPT_R, SCRYPT_P = 16384, 8, 1


class DuplicateUsername(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class PlanLimitReached(Exception):
    pass


class RegistrationClosed(Exception):
    pass


class StorageUnavailable(Exception):
    pass


def account_limit() -> int:
    """Bound the small trial's configurable account/storage quota."""
    value = os.environ.get("GYMPATH_MAX_ACCOUNTS", str(ACCOUNT_LIMIT))
    try:
        quota = int(value)
    except (TypeError, ValueError):
        raise ValueError("GYMPATH_MAX_ACCOUNTS must be an integer from 1 to 1000.") from None
    if not 1 <= quota <= 1000:
        raise ValueError("GYMPATH_MAX_ACCOUNTS must be an integer from 1 to 1000.")
    return quota


def database_path() -> Path:
    default = Path(__file__).resolve().parent.parent / "data"
    return Path(os.environ.get("GYMPATH_DATA_DIR", str(default))).expanduser().resolve() / "gympath.sqlite3"


@contextmanager
def connection():
    path = database_path()
    db = None
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=3)
        if os.name == "posix":
            path.chmod(0o600)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                username_key TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                csrf_token TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
            CREATE TABLE IF NOT EXISTS saved_plans (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                preferences_json TEXT NOT NULL,
                plan_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS plans_owner ON saved_plans(user_id, id);
        """)
        with db:
            yield db
    except sqlite3.IntegrityError:
        raise
    except (sqlite3.DatabaseError, OSError) as error:
        # The HTTP layer maps this to a generic temporary-unavailability
        # response. Never expose SQL, filesystem paths or account values.
        raise StorageUnavailable from error
    finally:
        if db is not None:
            db.close()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt,
                            n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt, digest = stored.split("$")
        if algorithm != "scrypt" or (int(n), int(r), int(p)) != (SCRYPT_N, SCRYPT_R, SCRYPT_P):
            return False
        candidate = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt),
                                   n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(candidate, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session(db, user_id: int):
    now = int(time.time())
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
    # Keep at most five current device sessions for one account.
    db.execute("""DELETE FROM sessions WHERE token_hash IN (
        SELECT token_hash FROM sessions WHERE user_id = ?
        ORDER BY created_at DESC, rowid DESC LIMIT -1 OFFSET 4
    )""", (user_id,))
    db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
               (token_hash(token), user_id, csrf, now, now + SESSION_SECONDS))
    return token, csrf


def register(username: str, password: str):
    quota = account_limit()
    hashed = password_hash(password)
    try:
        with connection() as db:
            # A class trial has a finite storage budget. Serialize the count
            # and insert so concurrent registrations cannot exceed the cap.
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] >= quota:
                raise RegistrationClosed
            cursor = db.execute("INSERT INTO users (username, username_key, password_hash, created_at) VALUES (?, ?, ?, ?)",
                                (username, username.casefold(), hashed, timestamp()))
            user = {"id": cursor.lastrowid, "username": username}
            token, csrf = issue_session(db, user["id"])
    except sqlite3.IntegrityError as error:
        raise DuplicateUsername from error
    return user, token, csrf


def login(username: str, password: str):
    with connection() as db:
        row = db.execute("SELECT id, username, password_hash FROM users WHERE username_key = ?",
                         (username.casefold(),)).fetchone()
        if row is None:
            # Missing and wrong-password cases both perform one expensive hash.
            verify_password(password, f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${'00' * 16}${'00' * 32}")
            raise InvalidCredentials
        if not verify_password(password, row["password_hash"]):
            raise InvalidCredentials
        user = {"id": row["id"], "username": row["username"]}
        token, csrf = issue_session(db, user["id"])
    return user, token, csrf


def session(token: str | None):
    if not token or len(token) > 128 or not database_path().is_file():
        return None
    with connection() as db:
        row = db.execute("""SELECT u.id, u.username, s.csrf_token
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ?""",
                         (token_hash(token), int(time.time()))).fetchone()
    if row is None:
        return None
    return {"user": {"id": row["id"], "username": row["username"]}, "csrf_token": row["csrf_token"]}


def revoke(token: str | None):
    if token and database_path().is_file():
        with connection() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))


def plan_record(row):
    return {"id": row["id"], "title": row["title"], "created_at": row["created_at"],
            "preferences": json.loads(row["preferences_json"]), "plan": json.loads(row["plan_json"])}


def list_plans(user_id: int):
    with connection() as db:
        rows = db.execute("SELECT * FROM saved_plans WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
    return [plan_record(row) for row in rows]


def save_plan(user_id: int, preferences: dict, plan: dict):
    goal = {"muscle_gain": "增肌", "strength_gain": "增强力量", "fat_loss": "减脂", "health": "居家活动"}[preferences["goal"]]
    title = f"{goal} · 安排 {plan['days_per_week']} 次 · 每次可用 {preferences['minutes_per_session']} 分钟"
    with connection() as db:
        # Count and insert share a write transaction, including concurrent requests.
        db.execute("BEGIN IMMEDIATE")
        count = db.execute("SELECT COUNT(*) FROM saved_plans WHERE user_id = ?", (user_id,)).fetchone()[0]
        if count >= PLAN_LIMIT:
            raise PlanLimitReached
        cursor = db.execute("""INSERT INTO saved_plans
            (user_id, title, created_at, preferences_json, plan_json) VALUES (?, ?, ?, ?, ?)""",
                            (user_id, title, timestamp(), json.dumps(preferences, ensure_ascii=False),
                             json.dumps(plan, ensure_ascii=False)))
        row = db.execute("SELECT * FROM saved_plans WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return plan_record(row)


def delete_plan(user_id: int, plan_id: int) -> bool:
    with connection() as db:
        result = db.execute("DELETE FROM saved_plans WHERE id = ? AND user_id = ?", (plan_id, user_id))
    return result.rowcount > 0


class AuthRateLimiter:
    """Bounded per-process limiter keyed by the actual trusted client address."""

    def __init__(self, limit=10, window_seconds=600, max_clients=1024):
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self.clients = OrderedDict()
        self.lock = Lock()

    def allow(self, address: str) -> bool:
        now = time.monotonic()
        with self.lock:
            stale = [key for key, events in self.clients.items() if not events or events[-1] <= now - self.window_seconds]
            for key in stale:
                del self.clients[key]
            if address not in self.clients:
                # At capacity refuse a new bucket rather than evict active limits.
                if len(self.clients) >= self.max_clients:
                    return False
                self.clients[address] = deque()
            events = self.clients[address]
            while events and events[0] <= now - self.window_seconds:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


class PersistentAuthRateLimiter:
    """Atomic, bounded auth budgets shared by workers and preserved on reload.

    Only address hashes and short-lived attempt timestamps are stored. This
    private file is separate from accounts so invalid input cannot create an
    account database. The global budget bounds password-hash work even when
    requests originate from many different addresses.
    """

    def __init__(self, limit=10, window_seconds=600, max_clients=1024, global_limit=240):
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self.global_limit = global_limit

    @staticmethod
    def path() -> Path:
        return database_path().with_name("abuse.sqlite3")

    def allow(self, address: str) -> bool:
        path = self.path()
        now = int(time.time())
        cutoff = now - self.window_seconds
        key = "ip:" + hashlib.sha256(address.encode("utf-8")).hexdigest()
        try:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            # A short lock timeout avoids indefinitely tying up request
            # workers; storage/lock failures deny costly auth operations.
            with sqlite3.connect(path, timeout=2) as db:
                if os.name == "posix":
                    path.chmod(0o600)
                db.execute("CREATE TABLE IF NOT EXISTS auth_buckets ("
                           "key TEXT PRIMARY KEY, last_attempt INTEGER NOT NULL, events TEXT NOT NULL)")
                db.execute("BEGIN IMMEDIATE")
                db.execute("DELETE FROM auth_buckets WHERE last_attempt <= ?", (cutoff,))
                rows = dict(db.execute("SELECT key, events FROM auth_buckets WHERE key IN (?, 'global')", (key,)))
                if key not in rows:
                    count = db.execute("SELECT COUNT(*) FROM auth_buckets WHERE key != 'global'").fetchone()[0]
                    if count >= self.max_clients:
                        return False
                address_events = [event for event in json.loads(rows.get(key, "[]")) if event > cutoff]
                global_events = [event for event in json.loads(rows.get("global", "[]")) if event > cutoff]
                if len(address_events) >= self.limit or len(global_events) >= self.global_limit:
                    return False
                for bucket, events in ((key, address_events), ("global", global_events)):
                    events.append(now)
                    db.execute("INSERT INTO auth_buckets VALUES (?, ?, ?) "
                               "ON CONFLICT(key) DO UPDATE SET last_attempt = excluded.last_attempt, events = excluded.events",
                               (bucket, now, json.dumps(events, separators=(",", ":"))))
                return True
        except (sqlite3.Error, OSError, ValueError, TypeError):
            return False


rate_limiter = PersistentAuthRateLimiter()
