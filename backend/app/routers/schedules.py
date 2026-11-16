"""Prayers (minyanim) and lessons: fixed or relative times, special days, exceptions, export."""
import csv
import io
import uuid
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..common import commit_change, get_links, get_or_404, links_map, row, set_links
from ..db import get_db
from ..models import (
    DAY_KINDS, Lesson, LessonSchedule, LessonScheduleException, PrayerSchedule, PrayerScheduleException,
    PrayerType, User,
)
from ..security import current_user, require_editor
from ..services.calendar_engine import RELATIVE_ANCHORS
from ..services.scheduling import schedule_items
from ..services.snapshot import calc_profile, cached_calendar_days

router = APIRouter(prefix="/api/v1", tags=["prayers", "lessons"])

DAY_KIND_LABELS = {
    "daily": "כל יום", "weekday": "ימי חול (א׳-ו׳)", "sun_thu": "א׳-ה׳", "friday": "יום שישי", "shabbat": "שבת",
    "custom": "ימים נבחרים", "rosh_chodesh": "ראש חודש", "yom_tov": "יום טוב", "erev_yom_tov": "ערב יום טוב",
    "chol_hamoed": "חול המועד", "fast_day": "תענית ציבור", "chanukah": "חנוכה",
}
ROUNDING_LABELS = {"none": "ללא עיגול", "down5": "עיגול מטה ל-5 דק׳", "up5": "עיגול מעלה ל-5 דק׳", "near5": "לקרוב ל-5 דק׳"}


class RuleIn(BaseModel):
    day_kind: str = "daily"
    days_of_week: list[int] = []
    replaces_regular: bool = False
    time_mode: str = Field(default="fixed", pattern="^(fixed|relative)$")
    fixed_time: time | None = None
    relative_zman: str | None = None
    offset_minutes: int = Field(default=0, ge=-600, le=600)
    rounding: str = Field(default="none", pattern="^(none|down5|up5|near5)$")
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    valid_from: date | None = None
    valid_to: date | None = None

    @field_validator("day_kind")
    @classmethod
    def dk(cls, v):
        if v not in DAY_KINDS:
            raise ValueError("סוג יום לא מוכר")
        return v

    @model_validator(mode="after")
    def check(self):
        if self.time_mode == "fixed" and self.fixed_time is None:
            raise ValueError("יש להזין שעה קבועה")
        if self.time_mode == "relative" and self.relative_zman not in RELATIVE_ANCHORS:
            raise ValueError("יש לבחור זמן הלכתי לחישוב יחסי")
        if self.day_kind == "custom" and not self.days_of_week:
            raise ValueError("יש לבחור לפחות יום אחד")
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("טווח תוקף לא תקין")
        if self.time_mode == "fixed":
            self.relative_zman = None
        return self


class ExceptionIn(BaseModel):
    date: date
    action: str = Field(pattern="^(cancel|override)$")
    override_time: time | None = None
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def check(self):
        if self.action == "override" and not self.override_time:
            raise ValueError("יש להזין שעה חלופית")
        return self


class PrayerIn(RuleIn):
    prayer_type_id: uuid.UUID
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=120)
    enabled: bool = True
    sort_order: int = 0
    screen_ids: list[uuid.UUID] | None = None


class PrayerTypeIn(BaseModel):
    key: str = Field(min_length=1, max_length=30, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=60)
    sort_order: int = 0


def rule_label(r) -> str:
    if r.time_mode == "fixed":
        return r.fixed_time.strftime("%H:%M")
    from ..services.calendar_engine import ZMANIM_DEFS
    off = r.offset_minutes
    sign = "+" if off >= 0 else "-"
    return f"{ZMANIM_DEFS[r.relative_zman][0]} {sign} {abs(off)} דק׳" + (
        f" ({ROUNDING_LABELS[r.rounding]})" if r.rounding != "none" else "")


def prayer_out(db: Session, p: PrayerSchedule, links: dict | None = None) -> dict:
    d = row(p)
    d["type_name"] = p.prayer_type.name
    d["type_key"] = p.prayer_type.key
    d["day_kind_label"] = DAY_KIND_LABELS[p.day_kind]
    d["time_label"] = rule_label(p)
    d["exceptions"] = [row(e) for e in p.exceptions]
    d["screen_ids"] = (links or {}).get(str(p.id), []) if links is not None else get_links(db, "prayer", p.id)
    return d


@router.get("/schedule-options")
def schedule_options(_: User = Depends(current_user)):
    from ..services.calendar_engine import ZMANIM_DEFS
    return {"day_kinds": [{"key": k, "label": v} for k, v in DAY_KIND_LABELS.items()],
            "rounding": [{"key": k, "label": v} for k, v in ROUNDING_LABELS.items()],
            "anchors": [{"key": k, "label": ZMANIM_DEFS[k][0]} for k in RELATIVE_ANCHORS]}


@router.get("/prayer-types")
def prayer_types(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [row(t) for t in db.scalars(select(PrayerType).order_by(PrayerType.sort_order)).all()]


@router.post("/prayer-types", status_code=201)
def create_prayer_type(body: PrayerTypeIn, request: Request, user: User = Depends(require_editor),
                       db: Session = Depends(get_db)):
    if db.scalar(select(PrayerType).where(PrayerType.key == body.key)):
        raise HTTPException(409, detail="מזהה סוג התפילה כבר קיים")
    t = PrayerType(**body.model_dump())
    db.add(t)
    db.flush()
    commit_change(db, request, user, "create", "prayer_type", t.id)
    return row(t)


def _prayer_query():
    return select(PrayerSchedule).options(selectinload(PrayerSchedule.exceptions), selectinload(PrayerSchedule.prayer_type))


@router.get("/prayers")
def list_prayers(q: str | None = None, prayer_type_id: uuid.UUID | None = None, day_kind: str | None = None,
                 screen_id: uuid.UUID | None = None, _: User = Depends(current_user), db: Session = Depends(get_db)):
    query = _prayer_query().join(PrayerType).order_by(PrayerType.sort_order, PrayerSchedule.sort_order, PrayerSchedule.name)
    if q:
        query = query.where(or_(PrayerSchedule.name.ilike(f"%{q}%"), PrayerSchedule.description.ilike(f"%{q}%")))
    if prayer_type_id:
        query = query.where(PrayerSchedule.prayer_type_id == prayer_type_id)
    if day_kind:
        query = query.where(PrayerSchedule.day_kind == day_kind)
    links = links_map(db, "prayer")
    items = [prayer_out(db, p, links) for p in db.scalars(query).all()]
    if screen_id:
        items = [i for i in items if str(screen_id) in i["screen_ids"]]
    return items


@router.post("/prayers", status_code=201)
def create_prayer(body: PrayerIn, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    get_or_404(db, PrayerType, body.prayer_type_id, "סוג התפילה")
    p = PrayerSchedule(**body.model_dump(exclude={"screen_ids"}))
    db.add(p)
    db.flush()
    set_links(db, "prayer", p.id, body.screen_ids)
    commit_change(db, request, user, "create", "prayer", p.id, {"name": p.name})
    db.refresh(p)
    return prayer_out(db, p)


@router.patch("/prayers/{pid}")
def update_prayer(pid: uuid.UUID, body: PrayerIn, request: Request, user: User = Depends(require_editor),
                  db: Session = Depends(get_db)):
    p = get_or_404(db, PrayerSchedule, pid, "התפילה")
    for k, v in body.model_dump(exclude={"screen_ids"}).items():
        setattr(p, k, v)
    set_links(db, "prayer", p.id, body.screen_ids)
    commit_change(db, request, user, "update", "prayer", p.id, {"name": p.name})
    db.refresh(p)
    return prayer_out(db, p)


@router.post("/prayers/{pid}/duplicate", status_code=201)
def duplicate_prayer(pid: uuid.UUID, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    src = get_or_404(db, PrayerSchedule, pid, "התפילה")
    data = row(src, exclude={"id", "created_at", "updated_at"})
    data["name"] = (src.name + " (עותק)")[:120]
    p = PrayerSchedule(**{k: getattr(src, k) for k in data if k != "name"}, name=data["name"])
    db.add(p)
    db.flush()
    set_links(db, "prayer", p.id, get_links(db, "prayer", src.id))
    commit_change(db, request, user, "duplicate", "prayer", p.id)
    db.refresh(p)
    return prayer_out(db, p)


@router.delete("/prayers/{pid}", status_code=204)
def delete_prayer(pid: uuid.UUID, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    p = get_or_404(db, PrayerSchedule, pid, "התפילה")
    set_links(db, "prayer", p.id, [])
    db.delete(p)
    commit_change(db, request, user, "delete", "prayer", pid, {"name": p.name})


@router.post("/prayers/{pid}/exceptions", status_code=201)
def add_prayer_exception(pid: uuid.UUID, body: ExceptionIn, request: Request, user: User = Depends(require_editor),
                         db: Session = Depends(get_db)):
    get_or_404(db, PrayerSchedule, pid, "התפילה")
    existing = db.scalar(select(PrayerScheduleException).where(PrayerScheduleException.schedule_id == pid,
                                                                PrayerScheduleException.date == body.date))
    e = existing or PrayerScheduleException(schedule_id=pid)
    for k, v in body.model_dump().items():
        setattr(e, k, v)
    db.add(e)
    db.flush()
    commit_change(db, request, user, "exception", "prayer", pid, {"date": body.date.isoformat(), "action": body.action})
    return row(e)


@router.delete("/prayers/exceptions/{eid}", status_code=204)
def delete_prayer_exception(eid: uuid.UUID, request: Request, user: User = Depends(require_editor),
                            db: Session = Depends(get_db)):
    e = get_or_404(db, PrayerScheduleException, eid, "החריג")
    db.delete(e)
    commit_change(db, request, user, "delete_exception", "prayer", e.schedule_id)


def _day_ctx(db: Session, d: date):
    prof = calc_profile(db)
    cal = cached_calendar_days(db, prof, [d])[d]
    tz = ZoneInfo(prof.timezone)
    zi = {k: datetime.fromisoformat(v) for k, v in cal["zi"].items()}
    return cal, zi, tz


@router.get("/prayers/day")
def prayers_for_day(day: date = Query(alias="date"), _: User = Depends(current_user), db: Session = Depends(get_db)):
    cal, zi, tz = _day_ctx(db, day)
    rules = db.scalars(_prayer_query().where(PrayerSchedule.enabled.is_(True))).all()
    items = schedule_items(rules, day, cal["flags"], zi, tz, group_key=lambda r: r.prayer_type_id)
    return {"date": day.isoformat(), "hebrew": cal["h"]["str"], "holiday": cal["holiday"],
            "items": [{"id": str(x["rule"].id), "type_name": x["rule"].prayer_type.name, "name": x["rule"].name,
                       "time": x["time"].strftime("%H:%M"), "note": x["note"]} for x in items]}


def _csv(rows: list[list]) -> Response:
    buf = io.StringIO()
    buf.write("﻿")  # BOM so Excel opens Hebrew UTF-8 correctly
    w = csv.writer(buf)
    w.writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=export.csv"})


@router.get("/prayers/export.csv")
def export_prayers(_: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = [["סוג", "שם", "ימים", "שעה", "משך (דק׳)", "מיקום", "תיאור", "פעיל"]]
    for p in db.scalars(_prayer_query().join(PrayerType).order_by(PrayerType.sort_order, PrayerSchedule.sort_order)).all():
        rows.append([p.prayer_type.name, p.name, DAY_KIND_LABELS[p.day_kind], rule_label(p), p.duration_minutes or "",
                     p.location or "", p.description or "", "כן" if p.enabled else "לא"])
    return _csv(rows)


# ---------------------------------------------------------------- lessons
class LessonScheduleIn(RuleIn):
    id: uuid.UUID | None = None


class LessonIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    teacher: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    enabled: bool = True
    sort_order: int = 0
    schedules: list[LessonScheduleIn] = Field(min_length=1)
    screen_ids: list[uuid.UUID] | None = None


def _lesson_query():
    return select(Lesson).options(selectinload(Lesson.schedules).selectinload(LessonSchedule.exceptions))


def lesson_out(db: Session, les: Lesson, links: dict | None = None) -> dict:
    d = row(les)
    d["schedules"] = []
    for s in les.schedules:
        sd = row(s)
        sd["day_kind_label"] = DAY_KIND_LABELS[s.day_kind]
        sd["time_label"] = rule_label(s)
        sd["exceptions"] = [row(e) for e in s.exceptions]
        d["schedules"].append(sd)
    d["screen_ids"] = (links or {}).get(str(les.id), []) if links is not None else get_links(db, "lesson", les.id)
    return d


@router.get("/lessons")
def list_lessons(q: str | None = None, _: User = Depends(current_user), db: Session = Depends(get_db)):
    query = _lesson_query().order_by(Lesson.sort_order, Lesson.title)
    if q:
        query = query.where(or_(Lesson.title.ilike(f"%{q}%"), Lesson.teacher.ilike(f"%{q}%")))
    links = links_map(db, "lesson")
    return [lesson_out(db, x, links) for x in db.scalars(query).all()]


def _apply_lesson(db: Session, les: Lesson, body: LessonIn):
    for k, v in body.model_dump(exclude={"schedules", "screen_ids"}).items():
        setattr(les, k, v)
    keep = {}
    for s in les.schedules:
        keep[s.id] = s
    new_list = []
    for sin in body.schedules:
        data = sin.model_dump(exclude={"id"})
        s = keep.get(sin.id) if sin.id else None
        if s is None:
            s = LessonSchedule(**data)
        else:
            for k, v in data.items():
                setattr(s, k, v)
        new_list.append(s)
    les.schedules = new_list


@router.post("/lessons", status_code=201)
def create_lesson(body: LessonIn, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    les = Lesson(title=body.title)
    db.add(les)
    _apply_lesson(db, les, body)
    db.flush()
    set_links(db, "lesson", les.id, body.screen_ids)
    commit_change(db, request, user, "create", "lesson", les.id, {"title": les.title})
    return lesson_out(db, db.scalar(_lesson_query().where(Lesson.id == les.id)))


@router.patch("/lessons/{lid}")
def update_lesson(lid: uuid.UUID, body: LessonIn, request: Request, user: User = Depends(require_editor),
                  db: Session = Depends(get_db)):
    les = db.scalar(_lesson_query().where(Lesson.id == lid))
    if not les:
        raise HTTPException(404, detail="השיעור לא נמצא")
    _apply_lesson(db, les, body)
    set_links(db, "lesson", les.id, body.screen_ids)
    commit_change(db, request, user, "update", "lesson", les.id, {"title": les.title})
    db.expire_all()
    return lesson_out(db, db.scalar(_lesson_query().where(Lesson.id == lid)))


@router.delete("/lessons/{lid}", status_code=204)
def delete_lesson(lid: uuid.UUID, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    les = get_or_404(db, Lesson, lid, "השיעור")
    set_links(db, "lesson", les.id, [])
    db.delete(les)
    commit_change(db, request, user, "delete", "lesson", lid, {"title": les.title})


@router.post("/lessons/schedules/{sid}/exceptions", status_code=201)
def add_lesson_exception(sid: uuid.UUID, body: ExceptionIn, request: Request, user: User = Depends(require_editor),
                         db: Session = Depends(get_db)):
    get_or_404(db, LessonSchedule, sid, "מועד השיעור")
    existing = db.scalar(select(LessonScheduleException).where(LessonScheduleException.schedule_id == sid,
                                                               LessonScheduleException.date == body.date))
    e = existing or LessonScheduleException(schedule_id=sid)
    for k, v in body.model_dump().items():
        setattr(e, k, v)
    db.add(e)
    db.flush()
    commit_change(db, request, user, "exception", "lesson", sid, {"date": body.date.isoformat()})
    return row(e)


@router.delete("/lessons/exceptions/{eid}", status_code=204)
def delete_lesson_exception(eid: uuid.UUID, request: Request, user: User = Depends(require_editor),
                            db: Session = Depends(get_db)):
    e = get_or_404(db, LessonScheduleException, eid, "החריג")
    db.delete(e)
    commit_change(db, request, user, "delete_exception", "lesson", e.schedule_id)


@router.get("/lessons/day")
def lessons_for_day(day: date = Query(alias="date"), _: User = Depends(current_user), db: Session = Depends(get_db)):
    cal, zi, tz = _day_ctx(db, day)
    lessons = db.scalars(_lesson_query().where(Lesson.enabled.is_(True))).all()
    rules = []
    for les in lessons:
        for s in les.schedules:
            s._lesson = les  # noqa: SLF001
            rules.append(s)
    items = schedule_items(rules, day, cal["flags"], zi, tz, group_key=lambda r: r.lesson_id)
    return {"date": day.isoformat(), "items": [{"title": x["rule"]._lesson.title, "teacher": x["rule"]._lesson.teacher,
                                                "time": x["time"].strftime("%H:%M")} for x in items]}


@router.get("/lessons/export.csv")
def export_lessons(_: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = [["שיעור", "מגיד שיעור", "מיקום", "ימים", "שעה", "משך"]]
    for les in db.scalars(_lesson_query().order_by(Lesson.sort_order)).all():
        for s in les.schedules:
            rows.append([les.title, les.teacher or "", les.location or "", DAY_KIND_LABELS[s.day_kind], rule_label(s),
                         s.duration_minutes or ""])
    return _csv(rows)
