import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from ..common import commit_change, get_or_404, paginate, row, sanitize_html
from ..db import get_db
from ..models import Announcement, AnnouncementScreen, User
from ..security import current_user, require_editor

router = APIRouter(prefix="/api/v1", tags=["announcements"])


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body_html: str = Field(default="", max_length=20000)
    image_asset_id: uuid.UUID | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    priority: int = Field(default=0, ge=-100, le=100)
    enabled: bool = True
    hide_on_shabbat: bool = False
    screen_ids: list[uuid.UUID] = []

    @model_validator(mode="after")
    def dates(self):
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValueError("תאריך הסיום חייב להיות אחרי תאריך ההתחלה")
        return self


def screen_ids(db: Session, aid) -> list[str]:
    return [str(x) for x in db.scalars(select(AnnouncementScreen.screen_id).where(AnnouncementScreen.announcement_id == aid))]


def out(db: Session, a: Announcement) -> dict:
    d = row(a)
    d["screen_ids"] = screen_ids(db, a.id)
    d["image_url"] = f"/api/v1/media/{a.image_asset_id}" if a.image_asset_id else None
    now = datetime.now(timezone.utc)
    d["is_active_now"] = a.enabled and (not a.start_at or a.start_at <= now) and (not a.end_at or a.end_at > now)
    return d


def apply(db: Session, a: Announcement, body: AnnouncementIn):
    data = body.model_dump(exclude={"screen_ids"})
    data["body_html"] = sanitize_html(data["body_html"])
    for k, v in data.items():
        setattr(a, k, v)
    db.flush()
    db.execute(delete(AnnouncementScreen).where(AnnouncementScreen.announcement_id == a.id))
    for sid in dict.fromkeys(body.screen_ids):
        db.add(AnnouncementScreen(announcement_id=a.id, screen_id=sid))


@router.get("/announcements")
def list_announcements(q: str | None = None, screen_id: uuid.UUID | None = None, active_only: bool = False,
                       limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                       _: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Announcement).order_by(Announcement.priority.desc(), Announcement.created_at.desc())
    if q:
        query = query.where(or_(Announcement.title.ilike(f"%{q}%"), Announcement.body_html.ilike(f"%{q}%")))
    if screen_id:
        query = query.where(Announcement.id.in_(select(AnnouncementScreen.announcement_id)
                                                .where(AnnouncementScreen.screen_id == screen_id)))
    if active_only:
        now = datetime.now(timezone.utc)
        query = query.where(Announcement.enabled.is_(True),
                            or_(Announcement.start_at.is_(None), Announcement.start_at <= now),
                            or_(Announcement.end_at.is_(None), Announcement.end_at > now))
    items, total = paginate(db, query, limit, offset)
    return {"items": [out(db, a) for a in items], "total": total}


@router.post("/announcements", status_code=201)
def create(body: AnnouncementIn, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    a = Announcement(title=body.title)
    db.add(a)
    apply(db, a, body)
    commit_change(db, request, user, "create", "announcement", a.id, {"title": a.title})
    return out(db, a)


@router.patch("/announcements/{aid}")
def update(aid: uuid.UUID, body: AnnouncementIn, request: Request, user: User = Depends(require_editor),
           db: Session = Depends(get_db)):
    a = get_or_404(db, Announcement, aid, "ההודעה")
    apply(db, a, body)
    commit_change(db, request, user, "update", "announcement", a.id, {"title": a.title})
    return out(db, a)


@router.post("/announcements/{aid}/duplicate", status_code=201)
def duplicate(aid: uuid.UUID, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    src = get_or_404(db, Announcement, aid, "ההודעה")
    a = Announcement(title=(src.title + " (עותק)")[:200], body_html=src.body_html, image_asset_id=src.image_asset_id,
                     start_at=src.start_at, end_at=src.end_at, priority=src.priority, enabled=False,
                     hide_on_shabbat=src.hide_on_shabbat)
    db.add(a)
    db.flush()
    for sid in screen_ids(db, src.id):
        db.add(AnnouncementScreen(announcement_id=a.id, screen_id=sid))
    commit_change(db, request, user, "duplicate", "announcement", a.id, {"from": str(src.id)})
    return out(db, a)


@router.delete("/announcements/{aid}", status_code=204)
def remove(aid: uuid.UUID, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    a = get_or_404(db, Announcement, aid, "ההודעה")
    db.delete(a)
    commit_change(db, request, user, "delete", "announcement", aid, {"title": a.title})
