"""Authentication, sessions, CSRF, rate limiting, device tokens and audit logging."""
import hashlib
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import AppState, AuditLog, DisplayDevice, User, UserSession

SESSION_COOKIE = "sdb_session"
CSRF_HEADER = "X-CSRF-Token"

# Argon2id with library defaults (memory-hard); parameters stored inside each hash.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def validate_password_strength(password: str) -> None:
    if len(password) < 10:
        raise HTTPException(422, detail="הסיסמה חייבת להכיל לפחות 10 תווים")
    if password.isdigit() or password.isalpha():
        raise HTTPException(422, detail="הסיסמה חייבת לשלב אותיות וספרות/סימנים")


# ---------------------------------------------------------------- rate limiting
class LoginRateLimiter:
    """In-process sliding window limiter (single API instance). For multiple instances
    move this to Redis/DB — documented in docs/SECURITY.md."""

    def __init__(self):
        self._lock = threading.Lock()
        self._fails: dict[str, list[float]] = {}

    def _key(self, ip: str, username: str) -> str:
        return f"{ip}|{username.lower()}"

    def check(self, ip: str, username: str) -> None:
        s = get_settings()
        window = s.login_window_minutes * 60
        now = time.time()
        with self._lock:
            for key in (self._key(ip, username), self._key(ip, "*")):
                fails = [t for t in self._fails.get(key, []) if now - t < window]
                self._fails[key] = fails
                limit = s.login_max_failures if not key.endswith("|*") else s.login_max_failures * 4
                if len(fails) >= limit:
                    raise HTTPException(429, detail="יותר מדי ניסיונות התחברות. נסו שוב מאוחר יותר.")

    def fail(self, ip: str, username: str) -> None:
        with self._lock:
            for key in (self._key(ip, username), self._key(ip, "*")):
                self._fails.setdefault(key, []).append(time.time())

    def reset(self, ip: str, username: str) -> None:
        with self._lock:
            self._fails.pop(self._key(ip, username), None)


login_limiter = LoginRateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------- sessions
def create_session(db: Session, user: User, request: Request) -> tuple[str, UserSession]:
    token = secrets.token_urlsafe(32)
    sess = UserSession(
        user_id=user.id,
        token_hash=sha256_hex(token),
        csrf_token=secrets.token_urlsafe(24),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=get_settings().session_hours),
        ip=client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:300],
    )
    db.add(sess)
    db.commit()
    return token, sess


def _session_from_request(request: Request, db: Session) -> UserSession | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == sha256_hex(token)))
    if not sess:
        return None
    now = datetime.now(timezone.utc)
    if sess.expires_at < now or not sess.user.is_active:
        db.delete(sess)
        db.commit()
        return None
    if (now - sess.last_seen_at).total_seconds() > 60:
        sess.last_seen_at = now
        db.commit()
    return sess


def optional_session(request: Request, db: Session = Depends(get_db)) -> UserSession | None:
    return _session_from_request(request, db)


def current_session(request: Request, db: Session = Depends(get_db)) -> UserSession:
    sess = _session_from_request(request, db)
    if not sess:
        raise HTTPException(401, detail="נדרשת התחברות")
    # CSRF: every state-changing request must echo the session's CSRF token in a header.
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        sent = request.headers.get(CSRF_HEADER, "")
        if not sent or not secrets.compare_digest(sent, sess.csrf_token):
            raise HTTPException(403, detail="אסימון CSRF חסר או שגוי")
    request.state.user = sess.user
    return sess


def current_user(sess: UserSession = Depends(current_session)) -> User:
    return sess.user


def require_editor(user: User = Depends(current_user)) -> User:
    """Admins and editors may edit content."""
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, detail="פעולה זו מותרת למנהל בלבד")
    return user


# ---------------------------------------------------------------- display devices
def new_device_token() -> str:
    return "dev_" + secrets.token_urlsafe(32)


def device_from_request(request: Request, db: Session) -> DisplayDevice | None:
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else request.query_params.get("token")
    if not token:
        return None
    dev = db.scalar(select(DisplayDevice).where(DisplayDevice.token_hash == sha256_hex(token)))
    if not dev or dev.revoked:
        return None
    return dev


def display_reader(request: Request, db: Session = Depends(get_db)) -> DisplayDevice | User:
    """Read-only access for the TV: a paired device token, or a logged-in admin (preview)."""
    dev = device_from_request(request, db)
    if dev:
        return dev
    sess = _session_from_request(request, db)
    if sess:
        return sess.user
    raise HTTPException(401, detail="התקן תצוגה לא מזוהה. יש לצמד את המסך באמצעות קוד התקן.")


# ---------------------------------------------------------------- audit & revision
def audit(db: Session, request: Request | None, user: User | None, action: str, entity: str,
          entity_id: str | uuid.UUID | None = None, details: dict | None = None) -> None:
    db.add(AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else None,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id else None,
        details=details,
        ip=client_ip(request) if request else None,
    ))


def bump_content_revision(db: Session) -> None:
    """Any content change invalidates the current display snapshot."""
    row = db.get(AppState, "content_revision")
    if row is None:
        db.add(AppState(key="content_revision", value="1"))
    else:
        row.value = str(int(row.value) + 1)
