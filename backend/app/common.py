"""Shared API helpers: serialization, pagination, screen links, HTML sanitization."""
import uuid
from datetime import date, datetime, time
from typing import Any

import nh3
from fastapi import HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import ScreenContentLink, User
from .security import audit, bump_content_revision

ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "p", "br", "ul", "ol", "li", "h3", "h4", "mark", "span", "div", "small"}
ALLOWED_CLASSES = {"span": {"c-gold", "c-red", "c-blue", "c-green", "big", "huge"}, "p": {"center"}, "div": {"center"}}


def sanitize_html(html: str) -> str:
    return nh3.clean(html or "", tags=ALLOWED_TAGS, attributes={}, allowed_classes=ALLOWED_CLASSES,
                     link_rel=None, strip_comments=True)


def jsonable(v: Any) -> Any:
    if isinstance(v, (bytes, memoryview)):
        import base64
        return {"$b64": base64.b64encode(bytes(v)).decode()}
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, time):
        return v.strftime("%H:%M")
    return v


def row(obj, exclude: set[str] = frozenset()) -> dict:
    return {c.key: jsonable(getattr(obj, c.key)) for c in obj.__table__.columns if c.key not in exclude}


def get_or_404(db: Session, model, obj_id, what: str = "הפריט"):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(404, detail=f"{what} לא נמצא")
    return obj


def paginate(db: Session, query, limit: int, offset: int) -> tuple[list, int]:
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    items = db.scalars(query.limit(limit).offset(offset)).all()
    return list(items), int(total or 0)


def get_links(db: Session, content_type: str, content_id) -> list[str]:
    return [str(x) for x in db.scalars(select(ScreenContentLink.screen_id).where(
        ScreenContentLink.content_type == content_type, ScreenContentLink.content_id == content_id)).all()]


def links_map(db: Session, content_type: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for l in db.scalars(select(ScreenContentLink).where(ScreenContentLink.content_type == content_type)).all():
        out.setdefault(str(l.content_id), []).append(str(l.screen_id))
    return out


def set_links(db: Session, content_type: str, content_id, screen_ids: list | None) -> None:
    if screen_ids is None:
        return
    db.execute(delete(ScreenContentLink).where(ScreenContentLink.content_type == content_type,
                                               ScreenContentLink.content_id == content_id))
    for sid in dict.fromkeys(screen_ids):
        db.add(ScreenContentLink(screen_id=sid, content_type=content_type, content_id=content_id))


def commit_change(db: Session, request: Request, user: User, action: str, entity: str, entity_id=None,
                  details: dict | None = None) -> None:
    """Write audit entry, invalidate the display snapshot and commit."""
    audit(db, request, user, action, entity, entity_id, details)
    bump_content_revision(db)
    db.commit()
