"""Synagogue Digital Board API — one synagogue, Hebrew RTL admin + read-only TV display."""
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import get_settings
from .db import SessionLocal
from .routers import announcements, auth, display, halachot, maintenance, media, people, schedules, screens, settings

log = logging.getLogger("synagogue")
API_VERSION = "1.0.0"

app = FastAPI(title="Synagogue Digital Board API", version=API_VERSION, docs_url="/docs", openapi_url="/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=2048)
_origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Content-Type", "X-CSRF-Token", "Authorization"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("X-Frame-Options", "DENY")
    if get_settings().cookie_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def _error(status: int, message: str, details=None):
    return JSONResponse(status_code=status, content={"error": {"code": status, "message": message, "details": details},
                                                     "detail": message})


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    return _error(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(x) for x in e.get("loc", [])[1:]), "message": str(e.get("msg", "")).replace("Value error, ", "")}
               for e in exc.errors()]
    msg = "; ".join(f"{d['field']}: {d['message']}" if d["field"] else d["message"] for d in details[:3])
    return _error(422, "נתונים לא תקינים — " + msg, details)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("unhandled error", exc_info=exc)
    return _error(500, "שגיאת שרת פנימית")


for r in (auth, settings, media, screens, announcements, schedules, halachot, people, display, maintenance):
    app.include_router(r.router)


@app.get("/api/health", tags=["health"])
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("select 1"))
        return {"status": "ok", "database": "ok", "version": API_VERSION}
    except Exception:  # noqa: BLE001
        raise HTTPException(503, detail="database unavailable")


def _spa(mount: str, directory: Path | None):
    """Serve a built single-page app (optional single-origin deployment)."""
    if not directory or not Path(directory).exists():
        return
    directory = Path(directory)
    app.mount(f"/{mount}/assets", StaticFiles(directory=directory / "assets"), name=f"{mount}-assets")

    @app.get(f"/{mount}/{{path:path}}", include_in_schema=False)
    def spa(path: str):
        target = (directory / path).resolve()
        if path and target.is_file() and directory.resolve() in target.parents:
            headers = {"Cache-Control": "no-cache"} if path in ("sw.js", "index.html", "precache-manifest.json") else {}
            if path == "sw.js":
                headers["Service-Worker-Allowed"] = f"/{mount}/"
            return FileResponse(target, headers=headers)
        return FileResponse(directory / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get(f"/{mount}", include_in_schema=False)
    def spa_root():
        return RedirectResponse(f"/{mount}/")


_spa("admin", get_settings().admin_static_dir)
_spa("display", get_settings().display_static_dir)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/admin/" if get_settings().admin_static_dir else "/docs")
