from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..common import get_or_404, row
from ..config import get_settings
from ..db import get_db
from ..models import AuditLog, User, UserSession
from ..security import (
    SESSION_COOKIE, audit, client_ip, create_session, current_session, hash_password,
    login_limiter, require_admin, validate_password_strength, verify_password,
)

router = APIRouter(prefix="/api/v1", tags=["auth"])
# Constant dummy hash so that unknown usernames take the same time as wrong passwords.
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password-1")


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)


def user_out(u: User) -> dict:
    return row(u, exclude={"password_hash"})


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    login_limiter.check(ip, body.username)
    user = db.scalar(select(User).where(func.lower(User.username) == body.username.lower()))
    ok = verify_password(user.password_hash if user else _DUMMY_HASH, body.password)
    if not user or not ok or not user.is_active:
        login_limiter.fail(ip, body.username)
        audit(db, request, None, "login_failed", "auth", details={"username": body.username[:80]})
        db.commit()
        raise HTTPException(401, detail="שם משתמש או סיסמה שגויים")
    login_limiter.reset(ip, body.username)
    token, sess = create_session(db, user, request)
    user.last_login_at = datetime.now(timezone.utc)
    audit(db, request, user, "login", "auth")
    db.commit()
    s = get_settings()
    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=s.cookie_secure, samesite="strict",
                        max_age=s.session_hours * 3600, path="/")
    return {"user": user_out(user), "csrf_token": sess.csrf_token}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, sess: UserSession = Depends(current_session),
           db: Session = Depends(get_db)):
    audit(db, request, sess.user, "logout", "auth")
    db.delete(db.merge(sess))
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/auth/me")
def me(sess: UserSession = Depends(current_session)):
    return {"user": user_out(sess.user), "csrf_token": sess.csrf_token}


@router.post("/auth/change-password", status_code=204)
def change_password(body: ChangePasswordIn, request: Request, sess: UserSession = Depends(current_session),
                    db: Session = Depends(get_db)):
    user = db.merge(sess.user)
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(400, detail="הסיסמה הנוכחית שגויה")
    validate_password_strength(body.new_password)
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    # sign out every other session of this user
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.id != sess.id))
    audit(db, request, user, "change_password", "user", user.id)
    db.commit()


@router.get("/auth/sessions")
def my_sessions(sess: UserSession = Depends(current_session), db: Session = Depends(get_db)):
    rows = db.scalars(select(UserSession).where(UserSession.user_id == sess.user_id)
                      .order_by(UserSession.last_seen_at.desc())).all()
    return [{"id": str(r.id), "created_at": r.created_at.isoformat(), "last_seen_at": r.last_seen_at.isoformat(),
             "ip": r.ip, "user_agent": r.user_agent, "current": r.id == sess.id} for r in rows]


@router.delete("/auth/sessions/{session_id}", status_code=204)
def revoke_session(session_id: str, sess: UserSession = Depends(current_session), db: Session = Depends(get_db)):
    target = db.get(UserSession, session_id)
    if target and target.user_id == sess.user_id:
        db.delete(target)
        db.commit()


# ---------------------------------------------------------------- users (admin only)
class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.\-@]+$")
    display_name: str = Field(default="", max_length=120)
    password: str = Field(min_length=10, max_length=200)
    role: str = Field(default="editor", pattern="^(admin|editor)$")


class UserPatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, pattern="^(admin|editor)$")
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=10, max_length=200)


@router.get("/users")
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [user_out(u) for u in db.scalars(select(User).order_by(User.username)).all()]


@router.post("/users", status_code=201)
def create_user(body: UserIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    validate_password_strength(body.password)
    if db.scalar(select(User).where(func.lower(User.username) == body.username.lower())):
        raise HTTPException(409, detail="שם המשתמש כבר קיים")
    u = User(username=body.username, display_name=body.display_name, role=body.role,
             password_hash=hash_password(body.password), must_change_password=True)
    db.add(u)
    db.flush()
    audit(db, request, admin, "create", "user", u.id, {"username": u.username, "role": u.role})
    db.commit()
    return user_out(u)


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UserPatch, request: Request, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    u = get_or_404(db, User, user_id, "המשתמש")
    data = body.model_dump(exclude_unset=True)
    if u.id == admin.id and (data.get("is_active") is False or data.get("role") == "editor"):
        raise HTTPException(400, detail="לא ניתן להסיר הרשאות או לבטל את המשתמש המחובר")
    if "password" in data and data["password"]:
        validate_password_strength(data["password"])
        u.password_hash = hash_password(data.pop("password"))
        u.must_change_password = True
        db.execute(delete(UserSession).where(UserSession.user_id == u.id))
    data.pop("password", None)
    for k, v in data.items():
        setattr(u, k, v)
    if data.get("is_active") is False:
        db.execute(delete(UserSession).where(UserSession.user_id == u.id))
    audit(db, request, admin, "update", "user", u.id, {k: v for k, v in data.items()})
    db.commit()
    return user_out(u)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = get_or_404(db, User, user_id, "המשתמש")
    if u.id == admin.id:
        raise HTTPException(400, detail="לא ניתן למחוק את המשתמש המחובר")
    if u.role == "admin" and db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) <= 1:
        raise HTTPException(400, detail="חייב להישאר לפחות מנהל אחד")
    audit(db, request, admin, "delete", "user", u.id, {"username": u.username})
    db.delete(u)
    db.commit()


@router.get("/audit-logs")
def audit_logs(limit: int = 100, offset: int = 0, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    limit = max(1, min(limit, 500))
    total = db.scalar(select(func.count()).select_from(AuditLog))
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)).all()
    return {"items": [row(r) for r in rows], "total": total}

