"""Expose the existing FastAPI app inside PythonAnywhere's WSGI web process.

Only use this adapter behind the platform's single trusted proxy. The normal
local server keeps its own loopback-only proxy policy in start-local.ps1.
The SQLite directory defaults to project/data, a private persistent user file
directory on PythonAnywhere; do not map it as a static directory.
"""

import os
import threading

from a2wsgi import ASGIMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix

from backend.app import app


_asgi_application = None
_asgi_pid = None
_initialization_lock = threading.Lock()


def _reset_after_fork():
    global _asgi_application, _asgi_pid, _initialization_lock
    # Neither a running event-loop thread nor a held threading lock survives
    # fork safely. The child must own a fresh lock and create its own bridge.
    _initialization_lock = threading.Lock()
    _asgi_application = None
    _asgi_pid = None


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_after_fork)


def _worker_application():
    global _asgi_application, _asgi_pid
    pid = os.getpid()
    if _asgi_application is not None and _asgi_pid == pid:
        return _asgi_application
    with _initialization_lock:
        if _asgi_application is None or _asgi_pid != pid:
            # PythonAnywhere imports WSGI in the master before forking workers.
            # a2wsgi starts a thread here, so initialize only on a worker request.
            _asgi_application = ASGIMiddleware(app, wait_time=10)
            _asgi_pid = pid
        return _asgi_application


def _bridge(environ, start_response):
    # WSGI defines an empty CONTENT_LENGTH as an absent length. Some hosts
    # insert it for every bodyless method, including logout POST and DELETE.
    # a2wsgi otherwise turns it into an invalid empty HTTP header. Normalize
    # only this WSGI sentinel; actual API bodies remain bounded downstream.
    if environ.get("CONTENT_LENGTH") == "":
        environ = dict(environ)
        environ.pop("CONTENT_LENGTH")
    # REMOTE_PORT is optional in WSGI, but a2wsgi requires it to preserve the
    # client address. Zero means unknown port; the trusted address stays intact.
    if environ.get("REMOTE_ADDR") and not environ.get("REMOTE_PORT"):
        environ["REMOTE_PORT"] = "0"
    return _worker_application()(environ, start_response)


# Trust the platform's one proxy for client address and HTTPS scheme. Preserve
# Host as received so same-origin/CSRF checks use the public site hostname.
# Never run this adapter on a directly exposed WSGI socket.
application = ProxyFix(
    _bridge,
    x_for=1,
    x_proto=1,
    x_host=0,
    x_port=0,
    x_prefix=0,
)
