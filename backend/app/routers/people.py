"""Memorials (עילוי נשמת), sponsorships (פרנסים), birthdays, religious content and
tzadikim / hilula dates (ימי הילולה)."""
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..common import commit_change, get_links, get_or_404, links_map, row, set_links
from ..db import get_db
from ..models import Birthday, HilulaDate, MediaAsset, Memorial, ReligiousContent, Sponsorship, Tzadik, User
from ..security import current_user, require_editor
from ..services import hebrew as H
from ..services.scheduling import anniversaries_by_date, sponsorship_end
from ..services.snapshot import get_settings_row

router = APIRouter(prefix="/api/v1", tags=["people"])
LEAP = "^(adar_i|adar_ii|both)$"


def _valid_hebrew(month: int, day: int):
    if not (1 <= month <= 13 and 1 <= day <= 30):
        raise ValueError("תאריך עברי לא תקין")
    if month in (2, 4, 6, 10, 13) and day == 30:
        raise ValueError(f"בחודש {H.MONTH_NAMES[month]} יש 29 ימים בלבד")


def _next_occurrence(db: Session, month: int, day: int, policy: str) -> str | None:
    s = get_settings_row(db)
    today = datetime.now(ZoneInfo(s.timezone)).date()
    from datetime import timedelta
    m = anniversaries_by_date([(month, day, policy)], today, today + timedelta(days=400), s.day30_policy,
                              get=lambda r: r)
    return min(m).isoformat() if m else None


# ---------------------------------------------------------------- memorials
class MemorialIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    parent_name: str | None = Field(default=None, max_length=160)
    gender: str = Field(default="m", pattern="^(m|f)$")
    hebrew_day: int
    hebrew_month: int
    hebrew_year: int | None = Field(default=None, ge=5000, le=6000)
    gregorian_date: date | None = None
    leap_year_policy: str = Field(default="adar_ii", pattern=LEAP)
    notes: str | None = Field(default=None, max_length=1000)
    permanent: bool = True
    show_days_before: int = Field(default=7, ge=0, le=30)
    enabled: bool = True
    screen_ids: list[uuid.UUID] | None = None

    @model_validator(mode="after")
    def v(self):
        _valid_hebrew(self.hebrew_month, self.hebrew_day)
        return self


def memorial_out(db, m: Memorial, links=None) -> dict:
    d = row(m)
    d["hebrew_date_str"] = f"{H.gematria(m.hebrew_day)} {H.MONTH_NAMES[m.hebrew_month]}" + (
        f" ה{H.gematria(m.hebrew_year % 1000)}" if m.hebrew_year else "")
    d["next_yahrzeit"] = _next_occurrence(db, m.hebrew_month, m.hebrew_day, m.leap_year_policy)
    d["screen_ids"] = links.get(str(m.id), []) if links is not None else get_links(db, "memorial", m.id)
    return d


@router.get("/memorials")
def list_memorials(q: str | None = None, _: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Memorial).order_by(Memorial.hebrew_month, Memorial.hebrew_day, Memorial.full_name)
    if q:
        query = query.where(or_(Memorial.full_name.ilike(f"%{q}%"), Memorial.parent_name.ilike(f"%{q}%")))
    links = links_map(db, "memorial")
    return [memorial_out(db, m, links) for m in db.scalars(query)]


@router.get("/hebrew-date")
def convert_date(day: date = Query(alias="date"), _: User = Depends(current_user)):
    """Helper for forms: Gregorian → Hebrew (daytime date)."""
    h = H.hebrew_info(day)
    return {"day": h["day"], "month": h["month"], "year": h["year"], "str": h["str"], "leap": h["leap"]}


# ---------------------------------------------------------------- generic simple CRUD
def simple_crud(path: str, model, schema, entity: str, link_type: str | None, out_fn=None, order_by=None):
    def to_out(db, obj, links=None):
        if out_fn:
            return out_fn(db, obj, links)
        d = row(obj)
        if link_type:
            d["screen_ids"] = links.get(str(obj.id), []) if links is not None else get_links(db, link_type, obj.id)
        return d

    if path != "/memorials":
        @router.get(path)
        def list_items(_: User = Depends(current_user), db: Session = Depends(get_db)):
            q = select(model)
            if order_by is not None:
                q = q.order_by(*order_by)
            links = links_map(db, link_type) if link_type else None
            return [to_out(db, o, links) for o in db.scalars(q)]

    @router.post(path, status_code=201, name=f"create_{entity}")
    def create_item(body: schema, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
        obj = model(**body.model_dump(exclude={"screen_ids"}))
        db.add(obj)
        db.flush()
        if link_type:
            set_links(db, link_type, obj.id, body.screen_ids)
        commit_change(db, request, user, "create", entity, obj.id)
        return to_out(db, obj)

    @router.patch(path + "/{oid}", name=f"update_{entity}")
    def update_item(oid: uuid.UUID, body: schema, request: Request, user: User = Depends(require_editor),
                    db: Session = Depends(get_db)):
        obj = get_or_404(db, model, oid)
        for k, v in body.model_dump(exclude={"screen_ids"}).items():
            setattr(obj, k, v)
        if link_type:
            set_links(db, link_type, obj.id, body.screen_ids)
        commit_change(db, request, user, "update", entity, obj.id)
        return to_out(db, obj)

    @router.delete(path + "/{oid}", status_code=204, name=f"delete_{entity}")
    def delete_item(oid: uuid.UUID, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
        obj = get_or_404(db, model, oid)
        if link_type:
            set_links(db, link_type, obj.id, [])
        db.delete(obj)
        commit_change(db, request, user, "delete", entity, oid)


simple_crud("/memorials", Memorial, MemorialIn, "memorial", "memorial", out_fn=memorial_out)


class SponsorshipIn(BaseModel):
    sponsor_name: str | None = Field(default=None, max_length=160)
    dedication_type: str = Field(default="custom", pattern="^(iluy_nishmat|refua|hatzlacha|nidvat|zivug|custom)$")
    honoree_name: str | None = Field(default=None, max_length=200)
    text: str | None = Field(default=None, max_length=1000)
    period: str = Field(default="week", pattern="^(day|week|month|year)$")
    start_date: date
    end_date: date | None = None
    show_in_footer: bool = True
    enabled: bool = True
    screen_ids: list[uuid.UUID] | None = None

    @model_validator(mode="after")
    def v(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("תאריך הסיום לפני תאריך ההתחלה")
        if not (self.honoree_name or self.text or self.sponsor_name):
            raise ValueError("יש להזין לפחות שם תורם, שם להקדשה או נוסח")
        return self


def sponsorship_out(db, s: Sponsorship, links=None):
    d = row(s)
    d["effective_end"] = sponsorship_end(s.start_date, s.period, s.end_date).isoformat()
    today = date.today()
    d["is_active_now"] = s.enabled and s.start_date <= today <= sponsorship_end(s.start_date, s.period, s.end_date)
    d["screen_ids"] = links.get(str(s.id), []) if links is not None else get_links(db, "sponsorship", s.id)
    return d


simple_crud("/sponsorships", Sponsorship, SponsorshipIn, "sponsorship", "sponsorship", out_fn=sponsorship_out,
            order_by=(Sponsorship.start_date.desc(),))


class BirthdayIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    hebrew_day: int
    hebrew_month: int
    gregorian_date: date | None = None
    message: str | None = Field(default=None, max_length=300)
    leap_year_policy: str = Field(default="adar_ii", pattern=LEAP)
    enabled: bool = True

    @model_validator(mode="after")
    def v(self):
        _valid_hebrew(self.hebrew_month, self.hebrew_day)
        return self


def birthday_out(db, b: Birthday, links=None):
    d = row(b)
    d["hebrew_date_str"] = f"{H.gematria(b.hebrew_day)} {H.MONTH_NAMES[b.hebrew_month]}"
    d["next_date"] = _next_occurrence(db, b.hebrew_month, b.hebrew_day, b.leap_year_policy)
    return d


simple_crud("/birthdays", Birthday, BirthdayIn, "birthday", None, out_fn=birthday_out,
            order_by=(Birthday.hebrew_month, Birthday.hebrew_day))


class ContentIn(BaseModel):
    kind: str = Field(default="story", pattern="^(story|dvar_torah|parsha|other)$")
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)
    source: str | None = Field(default=None, max_length=300)
    license: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    enabled: bool = True
    sort_order: int = 0
    screen_ids: list[uuid.UUID] | None = None


simple_crud("/content", ReligiousContent, ContentIn, "content", "content",
            order_by=(ReligiousContent.sort_order, ReligiousContent.title))


# ---------------------------------------------------------------- hilulot (tzadikim)
class HilulaDateIn(BaseModel):
    id: uuid.UUID | None = None
    hebrew_month: int
    hebrew_day: int
    leap_year_policy: str = Field(default="adar_ii", pattern=LEAP)
    display_start_offset_days: int = Field(default=0, ge=0, le=30)
    display_end_offset_days: int = Field(default=0, ge=0, le=30)
    enabled: bool = True

    @model_validator(mode="after")
    def v(self):
        _valid_hebrew(self.hebrew_month, self.hebrew_day)
        return self


class TzadikIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    honorific: str | None = Field(default=None, max_length=60)
    biography: str = Field(min_length=1, max_length=6000)
    teaching_title: str | None = Field(default=None, max_length=200)
    teaching_text: str = Field(min_length=1, max_length=4000)
    teaching_source: str | None = Field(default=None, max_length=300)
    image_asset_id: uuid.UUID | None = None
    image_alt: str | None = Field(default=None, max_length=300)
    image_attribution: str | None = Field(default=None, max_length=500)
    burial_place: str | None = Field(default=None, max_length=200)
    death_hebrew_year: int | None = Field(default=None, ge=2000, le=6000)
    is_active: bool = True
    sort_order: int = 0
    dates: list[HilulaDateIn] = Field(min_length=1, max_length=5)


def tzadik_out(t: Tzadik, db: Session | None = None) -> dict:
    d = row(t)
    d["image_url"] = f"/api/v1/media/{t.image_asset_id}" if t.image_asset_id else None
    d["dates"] = []
    for x in t.dates:
        xd = row(x)
        xd["hebrew_date_str"] = f"{H.gematria(x.hebrew_day)} {H.MONTH_NAMES[x.hebrew_month]}"
        if db is not None:
            xd["next_date"] = _next_occurrence(db, x.hebrew_month, x.hebrew_day, x.leap_year_policy)
        d["dates"].append(xd)
    return d


def _tz_query():
    return select(Tzadik).options(selectinload(Tzadik.dates))


def _apply_tzadik(db: Session, t: Tzadik, body: TzadikIn):
    if body.image_asset_id and not db.get(MediaAsset, body.image_asset_id):
        raise HTTPException(422, detail="התמונה שנבחרה לא קיימת")
    for k, v in body.model_dump(exclude={"dates"}).items():
        setattr(t, k, v)
    existing = {x.id: x for x in t.dates}
    new = []
    for din in body.dates:
        data = din.model_dump(exclude={"id"})
        x = existing.get(din.id) if din.id else None
        if x is None:
            x = HilulaDate(**data)
        else:
            for k, v in data.items():
                setattr(x, k, v)
        new.append(x)
    t.dates = new


@router.get("/hilulot")
def list_hilulot(q: str | None = None, _: User = Depends(current_user), db: Session = Depends(get_db)):
    query = _tz_query().order_by(Tzadik.sort_order, Tzadik.display_name)
    if q:
        query = query.where(or_(Tzadik.display_name.ilike(f"%{q}%"), Tzadik.biography.ilike(f"%{q}%")))
    return [tzadik_out(t, db) for t in db.scalars(query)]


@router.get("/hilulot/active")
def active_hilulot(day: date | None = Query(None, alias="date"), after_day_change: bool = False,
                   _: User = Depends(current_user), db: Session = Depends(get_db)):
    """Tzadikim whose hilula is displayed on `date`. If after_day_change is true (after sunset
    when the synagogue changes day at sunset), the next Hebrew day is used."""
    from datetime import timedelta
    s = get_settings_row(db)
    tz = ZoneInfo(s.timezone)
    day = day or datetime.now(tz).date()
    target = day + timedelta(days=1) if (after_day_change and s.day_change == "sunset") else day
    dates = [x for x in db.scalars(select(HilulaDate).where(HilulaDate.enabled.is_(True))
                                   .options(selectinload(HilulaDate.tzadik))) if x.tzadik.is_active]
    m = anniversaries_by_date(dates, target - timedelta(days=31), target + timedelta(days=31), s.day30_policy)
    hits = []
    for g, recs in m.items():
        for r in recs:
            if g - timedelta(days=r.display_start_offset_days) <= target <= g + timedelta(days=r.display_end_offset_days):
                hits.append(r.tzadik)
    uniq = sorted({t.id: t for t in hits}.values(), key=lambda t: (t.sort_order, t.display_name))
    return {"date": day.isoformat(), "hebrew_date": H.hebrew_info(target)["str"],
            "items": [tzadik_out(t) for t in uniq]}


@router.post("/hilulot", status_code=201)
def create_tzadik(body: TzadikIn, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    t = Tzadik(display_name=body.display_name, biography=body.biography, teaching_text=body.teaching_text)
    db.add(t)
    _apply_tzadik(db, t, body)
    db.flush()
    commit_change(db, request, user, "create", "tzadik", t.id, {"name": t.display_name})
    return tzadik_out(db.scalar(_tz_query().where(Tzadik.id == t.id)), db)


@router.get("/hilulot/{tid}")
def get_tzadik(tid: uuid.UUID, _: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.scalar(_tz_query().where(Tzadik.id == tid))
    if not t:
        raise HTTPException(404, detail="הצדיק לא נמצא")
    return tzadik_out(t, db)


@router.patch("/hilulot/{tid}")
def update_tzadik(tid: uuid.UUID, body: TzadikIn, request: Request, user: User = Depends(require_editor),
                  db: Session = Depends(get_db)):
    t = db.scalar(_tz_query().where(Tzadik.id == tid))
    if not t:
        raise HTTPException(404, detail="הצדיק לא נמצא")
    _apply_tzadik(db, t, body)
    commit_change(db, request, user, "update", "tzadik", t.id, {"name": t.display_name})
    db.expire_all()
    return tzadik_out(db.scalar(_tz_query().where(Tzadik.id == tid)), db)


@router.delete("/hilulot/{tid}", status_code=204)
def delete_tzadik(tid: uuid.UUID, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    t = get_or_404(db, Tzadik, tid, "הצדיק")
    db.delete(t)
    commit_change(db, request, user, "delete", "tzadik", tid, {"name": t.display_name})
