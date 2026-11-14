"""Serve the native website, visitor plans and independent account storage.

Run from the website directory with:
    python -m uvicorn backend.app:app --host 127.0.0.1 --port 8081

Only named public files are served. The project root is never mounted because
it also contains private development notes and original-code references.
"""

from pathlib import Path
import hmac
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator
from pydantic_core import PydanticCustomError

from . import auth
from .plan_adapter import generate_fitted_plan
from .security import SecurityMiddleware


SITE_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_FILES = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/demo.html": ("demo.html", "text/html"),
    "/trial.html": ("trial.html", "text/html"),
    "/styles.css": ("styles.css", "text/css"),
    "/script.js": ("script.js", "application/javascript"),
    "/trial.js": ("trial.js", "application/javascript"),
    "/account.html": ("account.html", "text/html"),
    "/account.js": ("account.js", "application/javascript"),
    "/assets/mark.svg": ("assets/mark.svg", "image/svg+xml"),
    "/assets/training-path.svg": ("assets/training-path.svg", "image/svg+xml"),
    "/favicon.ico": ("assets/mark.svg", "image/svg+xml"),
}

app = FastAPI(
    title="GymPath local visitor trial",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(SecurityMiddleware)


class PlanRequest(BaseModel):
    """Only four non-identifying training preferences are accepted."""

    model_config = ConfigDict(extra="forbid")

    level: Literal["beginner", "restarting", "experienced"]
    goal: Literal["muscle_gain", "strength_gain", "fat_loss", "health"]
    days_per_week: Annotated[StrictInt, Field(ge=1, le=7)]
    minutes_per_session: Annotated[StrictInt, Field(ge=15, le=180)]


class AccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: Annotated[StrictStr, Field(min_length=2, max_length=20, pattern=r"^[\u4e00-\u9fffA-Za-z0-9_-]+$")]
    # Login accepts existing passwords without applying newer registration rules.
    password: Annotated[StrictStr, Field(min_length=1, max_length=128)]

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 256:
            raise PydanticCustomError("password_too_long", "Password too long.")
        return value


class RegisterRequest(AccountRequest):
    password: Annotated[StrictStr, Field(min_length=8, max_length=128)]

    @field_validator("password")
    @classmethod
    def password_characters(cls, value: str) -> str:
        has_letter = any("a" <= char <= "z" or "A" <= char <= "Z" for char in value)
        has_number = any("0" <= char <= "9" for char in value)
        if not has_letter or not has_number:
            raise PydanticCustomError("password_policy", "Password must include a letter and a number.")
        return value


class SavedPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferences: PlanRequest


def same_origin(request: Request):
    # Uvicorn interprets proxy headers only from deployment-configured trusted
    # addresses. Do not trust arbitrary X-Forwarded-* headers ourselves.
    expected = f"{request.url.scheme}://{request.url.netloc}".lower()
    origin = request.headers.get("origin", "").lower()
    if not origin or origin != expected:
        raise HTTPException(status_code=403, detail="请从本站页面发起操作。")


def auth_attempt(request: Request):
    same_origin(request)
    address = request.client.host if request.client else "unknown"
    if not auth.rate_limiter.allow(address):
        raise HTTPException(status_code=429, detail="操作过于频繁，请 10 分钟后再试。", headers={"Retry-After": "600"})


def current_session(request: Request):
    session = auth.session(request.cookies.get(auth.COOKIE_NAME))
    if session is None:
        raise HTTPException(status_code=401, detail="请先登录。")
    return session


def protected_session(request: Request, session=Depends(current_session)):
    same_origin(request)
    if not hmac.compare_digest(request.headers.get("x-csrf-token", "").encode("utf-8"), session["csrf_token"].encode("ascii")):
        raise HTTPException(status_code=403, detail="登录验证已失效，请刷新页面后重试。")
    return session


def set_session_cookie(response: Response, request: Request, token: str):
    response.set_cookie(auth.COOKIE_NAME, token, max_age=auth.SESSION_SECONDS,
                        httponly=True, secure=request.url.scheme == "https", samesite="lax", path="/")


@app.exception_handler(auth.StorageUnavailable)
async def storage_error_handler(request: Request, error: auth.StorageUnavailable):
    return JSONResponse(status_code=503, content={"detail": "服务暂时不可用，请稍后重试。"}, headers={"Retry-After": "5"})


@app.post("/api/auth/register", status_code=201, dependencies=[Depends(auth_attempt)])
def register_account(body: RegisterRequest, request: Request, response: Response):
    try:
        user, token, csrf = auth.register(body.username, body.password)
    except auth.DuplicateUsername as error:
        raise HTTPException(status_code=409, detail="用户名已被使用，请换一个。") from error
    except auth.RegistrationClosed as error:
        raise HTTPException(status_code=503, detail="试用账号已满，请稍后再试。") from error
    auth.revoke(request.cookies.get(auth.COOKIE_NAME))
    set_session_cookie(response, request, token)
    return {"user": user, "csrf_token": csrf}


@app.post("/api/auth/login", dependencies=[Depends(auth_attempt)])
def login_account(body: AccountRequest, request: Request, response: Response):
    try:
        user, token, csrf = auth.login(body.username, body.password)
    except auth.InvalidCredentials as error:
        raise HTTPException(status_code=401, detail="用户名或密码不正确。") from error
    auth.revoke(request.cookies.get(auth.COOKIE_NAME))
    set_session_cookie(response, request, token)
    return {"user": user, "csrf_token": csrf}


@app.get("/api/auth/me")
def account_me(request: Request):
    return auth.session(request.cookies.get(auth.COOKIE_NAME)) or {"user": None, "csrf_token": None}


@app.post("/api/auth/logout", status_code=204)
def logout_account(request: Request, session=Depends(protected_session)):
    auth.revoke(request.cookies.get(auth.COOKIE_NAME))
    response = Response(status_code=204)
    response.delete_cookie(auth.COOKIE_NAME, path="/", httponly=True,
                           secure=request.url.scheme == "https", samesite="lax")
    return response


@app.get("/api/plans")
def account_plans(session=Depends(current_session)):
    return {"plans": auth.list_plans(session["user"]["id"])}


@app.post("/api/plans", status_code=201)
def save_account_plan(body: SavedPlanRequest, session=Depends(protected_session)):
    preferences = body.preferences.model_dump()
    try:
        plan = generate_fitted_plan(**preferences)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="无法生成该安排，请调整训练偏好。") from error
    try:
        return auth.save_plan(session["user"]["id"], preferences, plan)
    except auth.PlanLimitReached as error:
        raise HTTPException(status_code=409, detail="最多保存 20 份计划，请先删除旧计划。") from error


@app.delete("/api/plans/{plan_id}", status_code=204)
def delete_account_plan(plan_id: int, session=Depends(protected_session)):
    if not auth.delete_plan(session["user"]["id"], plan_id):
        raise HTTPException(status_code=404, detail="计划不存在。")
    return Response(status_code=204)


def _validation_message(error: dict[str, Any], *, registration: bool = False) -> str:
    """Describe validation without including rejected values or context."""
    code = error["type"]
    field = error["loc"][-1] if error["loc"] else "body"
    if field == "username":
        return "用户名需为 2–20 个字符，只能使用中文、字母、数字、_ 或 -。"
    if field == "password":
        if code in {"string_too_long", "password_too_long"}:
            return "密码过长，请缩短后重试。"
        if registration:
            return "密码至少 8 个字符，并包含字母和数字。"
        return "请输入密码。"
    if code == "int_type":
        return "Enter a whole number."
    if code == "missing":
        return "This field is required."
    if code == "extra_forbidden":
        return "Unexpected field."
    if code == "literal_error":
        return "Choose one of the available options."
    if code in {"greater_than_equal", "less_than_equal"}:
        field = error["loc"][-1]
        if field == "days_per_week":
            return "Choose between 1 and 7 days."
        if field == "minutes_per_session":
            return "Choose between 15 and 180 minutes."
    if code == "json_invalid":
        return "Send a valid JSON object."
    return "Invalid input."


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Pydantic's default errors include the rejected input. Only safe field
    # paths, codes and our own messages are sent back to the browser.
    errors = []
    for error in exc.errors():
        location = error["loc"]
        path = location[1:] if location and location[0] == "body" else location
        errors.append(
            {
                "field": ".".join(str(part) for part in path) or "body",
                "message": _validation_message(error, registration=request.url.path == "/api/auth/register"),
                "code": error["type"],
            }
        )
    return JSONResponse(
        status_code=422,
        content={
            "detail": "请检查填写内容。" if request.url.path.startswith("/api/auth/") else "Check the training preferences and try again.",
            "errors": errors,
        },
    )


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "service": "gympath-local-trial",
        "capabilities": ["deterministic-plan", "time-fit-v1", "real-accounts", "saved-plans"],
        "stores_inputs": False,
        "account_storage": True,
    }


@app.post("/api/plan")
def create_plan(preferences: PlanRequest) -> dict[str, Any]:
    try:
        plan = generate_fitted_plan(**preferences.model_dump())
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Unable to generate a plan for these preferences.",
        ) from exc
    return {
        **plan,
        "trial_info": {
            "engine": "gympath-rules-adapted",
            "stores_inputs": False,
            "creates_account": False,
        },
    }


def _public_endpoint(filename: str, media_type: str):
    def serve_file() -> FileResponse:
        path = SITE_ROOT / filename
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Page not found.")
        return FileResponse(path, media_type=media_type)

    return serve_file


for public_path, (filename, media_type) in PUBLIC_FILES.items():
    app.add_api_route(
        public_path,
        _public_endpoint(filename, media_type),
        methods=["GET"],
        include_in_schema=False,
        name=f"public:{public_path}",
    )
