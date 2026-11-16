"""Builds the versioned, checksummed display snapshot (everything an offline TV needs)."""
import hashlib
import json
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..models import (
    Announcement, AnnouncementScreen, AppState, Birthday, DisplaySnapshot, Halacha, HalachaChapter,
    HalachaDisplayHistory, HalachaSelection, HalachaSource, HalachaTagLink, HalachicCalculationProfile,
    HilulaDate, Lesson, LessonSchedule, Memorial, PrayerSchedule, PrayerType, ReligiousContent, Screen,
    ScreenContentLink, Sponsorship, SynagogueSettings, Tzadik, ZmanimDailyCache,
)
from . import hebrew as H
from .calendar_engine import (
    ADDITION_DEFS, DEFAULT_ADDITIONS, DEFAULT_ENABLED_ZMANIM, DEFAULT_LEARNING, DEFAULT_REMINDERS,
    ENGINE_VERSION, ZMANIM_DEFS, CalcProfile, DayCalculator,
)
from .scheduling import anniversaries_by_date, plan_halachot, schedule_items, sponsorship_end

_build_lock = threading.Lock()
SNAPSHOT_SCHEMA = 1
SNAPSHOT_FORMAT = "1.1"  # bump whenever the payload shape/content rules change → forces a rebuild after upgrade


def media_url(asset_id) -> str | None:
    return f"/api/v1/media/{asset_id}" if asset_id else None


def get_settings_row(db: Session) -> SynagogueSettings:
    row = db.scalar(select(SynagogueSettings).limit(1))
    if row is None:
        row = SynagogueSettings(prayer_additions=DEFAULT_ADDITIONS, reminders=DEFAULT_REMINDERS,
                                daily_learning=DEFAULT_LEARNING, theme={})
        db.add(row)
        db.flush()
    return row


def get_profile_row(db: Session, s: SynagogueSettings) -> HalachicCalculationProfile:
    prof = db.get(HalachicCalculationProfile, s.calculation_profile_id) if s.calculation_profile_id else None
    if prof is None:
        prof = db.scalar(select(HalachicCalculationProfile).limit(1))
    if prof is None:
        prof = HalachicCalculationProfile(name="ברירת מחדל (ניתן לשינוי)", enabled_zmanim=DEFAULT_ENABLED_ZMANIM,
                                          engine_version=ENGINE_VERSION)
        db.add(prof)
        db.flush()
        s.calculation_profile_id = prof.id
    return prof


def calc_profile(db: Session) -> CalcProfile:
    s = get_settings_row(db)
    p = get_profile_row(db, s)
    return CalcProfile(
        latitude=s.latitude, longitude=s.longitude, elevation_m=s.elevation_m, timezone=s.timezone,
        in_israel=s.in_israel, nusach=s.nusach, walled_city_purim=s.walled_city_purim,
        show_national_holidays=s.show_national_holidays, alos_method=p.alos_method,
        misheyakir_degrees=p.misheyakir_degrees, tzeit_method=p.tzeit_method,
        candle_lighting_minutes=p.candle_lighting_minutes, shabbat_end_method=p.shabbat_end_method,
        shabbat_end_minutes=p.shabbat_end_minutes, rabbeinu_tam_minutes=p.rabbeinu_tam_minutes,
        rabbeinu_tam_zmaniyot=p.rabbeinu_tam_zmaniyot, use_elevation=p.use_elevation,
        enabled_zmanim=list(p.enabled_zmanim or []), prayer_additions=list(s.prayer_additions or []),
        reminders=list(s.reminders or []), daily_learning=list(s.daily_learning or []),
    )


def local_today(tzname: str) -> date:
    return datetime.now(ZoneInfo(tzname)).date()


# ---------------------------------------------------------------- calendar day (cached)
def calendar_day(calc: DayCalculator, prof: CalcProfile, d: date) -> dict:
    z = calc.zmanim(d)
    flags = calc.flags(d)
    h = H.hebrew_info(d)
    he = H.hebrew_info(d + timedelta(days=1))
    return {
        "h": {k: h[k] for k in ("day", "month", "year", "day_str", "month_name", "year_str", "str")},
        "he": {k: he[k] for k in ("day", "month", "year", "day_str", "month_name", "year_str", "str")},
        "parsha": H.parsha_for_week(d, prof.in_israel),
        "holiday": H.holiday_name(d, prof.in_israel, prof.show_national_holidays),
        "holiday_e": H.holiday_name(d + timedelta(days=1), prof.in_israel, prof.show_national_holidays),
        "flags": flags,
        "z": {k: v.strftime("%H:%M") for k, v in z.items()},
        "zi": {k: v.isoformat() for k, v in z.items()},
        "add": calc.additions(d),
        "rem": calc.reminders(d),
        "learn": calc.learning(d),
    }


def cached_calendar_days(db: Session, prof: CalcProfile, days: list[date]) -> dict[date, dict]:
    phash = prof.hash()
    rows = db.scalars(select(ZmanimDailyCache).where(
        ZmanimDailyCache.profile_hash == phash, ZmanimDailyCache.date.in_(days),
        ZmanimDailyCache.engine_version == ENGINE_VERSION)).all()
    out = {r.date: r.data for r in rows}
    missing = [d for d in days if d not in out]
    if missing:
        calc = DayCalculator(prof)
        new_rows = []
        for d in missing:
            data = calendar_day(calc, prof, d)
            out[d] = data
            new_rows.append({"date": d, "profile_hash": phash, "engine_version": ENGINE_VERSION, "data": data})
        for i in range(0, len(new_rows), 200):
            db.execute(pg_insert(ZmanimDailyCache).values(new_rows[i:i + 200]).on_conflict_do_nothing())
        db.commit()
    return out


def zmanim_for_api(db: Session, d: date) -> dict:
    prof = calc_profile(db)
    data = cached_calendar_days(db, prof, [d])[d]
    return {
        "date": d.isoformat(), "hebrew_date": data["h"]["str"], "parsha": data["parsha"], "holiday": data["holiday"],
        "engine": ENGINE_VERSION, "profile_hash": prof.hash(),
        "zmanim": [{"key": k, "label": ZMANIM_DEFS[k][0], "time": data["z"][k], "enabled": k in prof.enabled_zmanim}
                   for k in ZMANIM_DEFS if k in data["z"]],
        "additions": data["add"], "reminders": data["rem"], "learning": data["learn"],
    }


# ---------------------------------------------------------------- full snapshot
def _links(db: Session) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    for l in db.scalars(select(ScreenContentLink)).all():
        out.setdefault(l.content_type, {}).setdefault(str(l.content_id), []).append(str(l.screen_id))
    for a in db.scalars(select(AnnouncementScreen)).all():
        out.setdefault("announcement", {}).setdefault(str(a.announcement_id), []).append(str(a.screen_id))
    return out


def eligible_halachot(db: Session, sel: HalachaSelection) -> list[Halacha]:
    q = (select(Halacha).join(HalachaSource, Halacha.source_id == HalachaSource.id)
         .outerjoin(HalachaChapter, Halacha.chapter_id == HalachaChapter.id)
         .where(Halacha.enabled.is_(True), HalachaSource.enabled.is_(True)))
    filters = []

    def ids(values):
        return [uuid.UUID(str(v)) for v in values or []]
    if sel.source_ids:
        filters.append(Halacha.source_id.in_(ids(sel.source_ids)))
    if sel.category_ids:
        filters.append(Halacha.category_id.in_(ids(sel.category_ids)))
    if sel.chapter_ids:
        filters.append(Halacha.chapter_id.in_(ids(sel.chapter_ids)))
    if sel.halacha_ids:
        filters.append(Halacha.id.in_(ids(sel.halacha_ids)))
    if sel.tag_ids:
        filters.append(Halacha.id.in_(select(HalachaTagLink.halacha_id).where(HalachaTagLink.tag_id.in_(ids(sel.tag_ids)))))
    if filters:
        from sqlalchemy import or_
        q = q.where(or_(*filters))
    q = q.order_by(HalachaSource.title, func.coalesce(HalachaChapter.sort_order, 0), Halacha.sort_order, Halacha.title)
    return list(db.scalars(q).all())


def build_payload(db: Session, today: date | None = None) -> dict:
    s = get_settings_row(db)
    prof = calc_profile(db)
    tz = ZoneInfo(prof.timezone)
    today = today or local_today(prof.timezone)
    n_days = get_settings().snapshot_days
    start = today - timedelta(days=1)
    days = [start + timedelta(days=i) for i in range(n_days + 1)]
    end = days[-1]
    cal = cached_calendar_days(db, prof, days)

    # screens
    # all screens are shipped (disabled ones only for admin preview); the playlist plays enabled ones
    screens = db.scalars(select(Screen).order_by(Screen.sort_order, Screen.name)).all()
    screens_out = [{
        "id": str(x.id), "name": x.name, "type": x.type, "template_key": x.template_key, "enabled": x.enabled,
        "duration_seconds": x.duration_seconds, "config": x.config or {}, "conditions": x.conditions or {},
        "fallback": x.fallback, "fallback_text": x.fallback_text,
    } for x in screens]
    links = _links(db)
    media: set[str] = set()

    # prayers & lessons
    ptypes = {t.id: t for t in db.scalars(select(PrayerType)).all()}
    prayers = db.scalars(select(PrayerSchedule).where(PrayerSchedule.enabled.is_(True))
                         .options(selectinload(PrayerSchedule.exceptions))).all()
    lessons = db.scalars(select(Lesson).where(Lesson.enabled.is_(True))
                         .options(selectinload(Lesson.schedules).selectinload(LessonSchedule.exceptions))).all()
    lesson_rules = []
    for les in lessons:
        for r in les.schedules:
            r._lesson = les  # noqa: SLF001 - transient attribute for grouping
            lesson_rules.append(r)

    # anniversaries
    tz_dates = db.scalars(select(HilulaDate).where(HilulaDate.enabled.is_(True))
                          .options(selectinload(HilulaDate.tzadik))).all()
    tz_dates = [x for x in tz_dates if x.tzadik.is_active]
    hil_map = anniversaries_by_date(tz_dates, start - timedelta(days=31), end + timedelta(days=31), s.day30_policy)
    hil_window: dict[date, list] = {}
    hil_exact: dict[date, list] = {}
    for g, recs in hil_map.items():
        for r in recs:
            hil_exact.setdefault(g, []).append(r)
            for off in range(-r.display_start_offset_days, r.display_end_offset_days + 1):
                hil_window.setdefault(g + timedelta(days=off), []).append(r)
    memorials = db.scalars(select(Memorial).where(Memorial.enabled.is_(True))).all()
    mem_map = anniversaries_by_date(memorials, start, end + timedelta(days=31), s.day30_policy)
    birthdays = db.scalars(select(Birthday).where(Birthday.enabled.is_(True))).all()
    bday_map = anniversaries_by_date(birthdays, start, end + timedelta(days=1), s.day30_policy)

    # halachot
    selections = db.scalars(select(HalachaSelection).where(HalachaSelection.active.is_(True))
                            .order_by(HalachaSelection.created_at)).all()
    sel_items = {sel.id: eligible_halachot(db, sel) for sel in selections}
    used_halachot: dict = {}

    def sort_tzadikim(recs):
        return sorted({r.tzadik.id: r for r in recs}.values(), key=lambda r: (r.tzadik.sort_order, r.tzadik.display_name))

    days_out = {}
    for d in days:
        c = cal[d]
        zi = {k: datetime.fromisoformat(v) for k, v in c["zi"].items()}
        flags = c["flags"]
        pr = schedule_items(prayers, d, flags, zi, tz, group_key=lambda r: r.prayer_type_id)
        ls = schedule_items(lesson_rules, d, flags, zi, tz, group_key=lambda r: r.lesson_id)
        day = dict(c)
        day.pop("zi")
        day["zi"] = {k: c["zi"][k] for k in ("sunset", "tzeit", "candle_lighting", "shabbat_end") if k in c["zi"]}
        day["prayers"] = [{
            "id": str(x["rule"].id), "type": ptypes[x["rule"].prayer_type_id].key,
            "type_name": ptypes[x["rule"].prayer_type_id].name, "name": x["rule"].name,
            "time": x["time"].strftime("%H:%M"), "description": x["rule"].description,
            "location": x["rule"].location, "note": x["note"],
        } for x in pr]
        day["lessons"] = [{
            "id": str(x["rule"].lesson_id), "title": x["rule"]._lesson.title, "teacher": x["rule"]._lesson.teacher,
            "location": x["rule"]._lesson.location, "time": x["time"].strftime("%H:%M"),
            "duration": x["rule"].duration_minutes, "note": x["note"],
        } for x in ls]
        nd = d + timedelta(days=1)
        day["hil"] = [str(r.tzadik.id) for r in sort_tzadikim(hil_window.get(d, []))]
        day["hil_e"] = [str(r.tzadik.id) for r in sort_tzadikim(hil_window.get(nd, []))]
        upcoming = []
        for i in range(0, 15):
            gd = d + timedelta(days=i)
            for r in sort_tzadikim(hil_exact.get(gd, [])):
                upcoming.append({"id": str(r.tzadik.id), "date": gd.isoformat(), "days": i,
                                 "hebrew": cal[gd]["h"]["day_str"] + " " + cal[gd]["h"]["month_name"]
                                 if gd in cal else None})
        day["hil_up"] = upcoming[:12]
        day["mem"] = [str(m.id) for m in mem_map.get(d, [])]
        day["mem_e"] = [str(m.id) for m in mem_map.get(nd, [])]
        week = []
        for i in range(0, 8):
            gd = d + timedelta(days=i)
            for m in mem_map.get(gd, []):
                if i <= m.show_days_before:
                    week.append({"id": str(m.id), "date": gd.isoformat(), "days": i})
        day["mem_week"] = week
        day["bday"] = [str(b.id) for b in bday_map.get(d, [])]
        day["bday_e"] = [str(b.id) for b in bday_map.get(nd, [])]
        day["halacha"] = {}
        for sel in selections:
            plan = plan_halachot(sel_items[sel.id], sel.mode, sel.per_day, sel.seed, sel.start_date, d)
            day["halacha"][str(sel.id)] = [str(x.id) for x in plan]
            for x in plan:
                used_halachot[x.id] = x
        days_out[d.isoformat()] = day

    # record today's halachot in the display history (idempotent)
    hist_rows = [{"selection_id": sel.id, "halacha_id": x.id, "shown_on": today}
                 for sel in selections
                 for x in plan_halachot(sel_items[sel.id], sel.mode, sel.per_day, sel.seed, sel.start_date, today)]
    if hist_rows:
        db.execute(pg_insert(HalachaDisplayHistory).values(hist_rows).on_conflict_do_nothing())

    sources = {x.id: x for x in db.scalars(select(HalachaSource)).all()}
    halachot_out = {}
    for hid, x in used_halachot.items():
        src = sources[x.source_id]
        halachot_out[str(hid)] = {
            "title": x.title, "text": x.text, "source_ref": x.source_ref, "source_title": src.title,
            "author": src.author, "attribution": src.attribution, "license": src.license, "is_sample": src.is_sample,
        }

    tzadikim = {}
    for r in tz_dates:
        t = r.tzadik
        img = media_url(t.image_asset_id)
        if img:
            media.add(img)
        tzadikim[str(t.id)] = {
            "display_name": t.display_name, "honorific": t.honorific, "biography": t.biography,
            "teaching_title": t.teaching_title, "teaching_text": t.teaching_text, "teaching_source": t.teaching_source,
            "image_url": img, "image_alt": t.image_alt, "image_attribution": t.image_attribution,
            "burial_place": t.burial_place,
            "death_year_str": ("ה" + H.gematria(t.death_hebrew_year % 1000)) if t.death_hebrew_year else None,
            "hilula_date_str": f"{H.gematria(r.hebrew_day)} {H.MONTH_NAMES[r.hebrew_month]}",
        }

    announcements = db.scalars(select(Announcement).where(Announcement.enabled.is_(True))
                               .order_by(Announcement.priority.desc(), Announcement.created_at.desc())).all()
    ann_out = []
    now_utc = datetime.now(timezone.utc)
    for a in announcements:
        if a.end_at and a.end_at < now_utc:
            continue
        img = media_url(a.image_asset_id)
        if img:
            media.add(img)
        ann_out.append({
            "id": str(a.id), "title": a.title, "body_html": a.body_html, "image_url": img,
            "start_at": a.start_at.isoformat() if a.start_at else None,
            "end_at": a.end_at.isoformat() if a.end_at else None, "priority": a.priority,
            "hide_on_shabbat": a.hide_on_shabbat, "screens": links.get("announcement", {}).get(str(a.id), []),
        })

    def mem_dict(m: Memorial):
        ben = "בת" if m.gender == "f" else "בן"
        return {
            "full_name": m.full_name, "parent_name": m.parent_name, "ben": ben, "gender": m.gender,
            "hebrew_date": f"{H.gematria(m.hebrew_day)} {H.MONTH_NAMES[m.hebrew_month]}" + (
                f" ה{H.gematria(m.hebrew_year % 1000)}" if m.hebrew_year else ""),
            "permanent": m.permanent, "screens": links.get("memorial", {}).get(str(m.id), []),
        }

    sponsors = []
    for sp in db.scalars(select(Sponsorship).where(Sponsorship.enabled.is_(True))).all():
        e = sponsorship_end(sp.start_date, sp.period, sp.end_date)
        if e < start:
            continue
        sponsors.append({
            "id": str(sp.id), "sponsor_name": sp.sponsor_name, "dedication_type": sp.dedication_type,
            "honoree_name": sp.honoree_name, "text": sp.text, "period": sp.period, "start": sp.start_date.isoformat(),
            "end": e.isoformat(), "footer": sp.show_in_footer, "screens": links.get("sponsorship", {}).get(str(sp.id), []),
        })

    content = [{
        "id": str(c.id), "kind": c.kind, "title": c.title, "body": c.body, "source": c.source,
        "start": c.start_date.isoformat() if c.start_date else None, "end": c.end_date.isoformat() if c.end_date else None,
        "screens": links.get("content", {}).get(str(c.id), []),
    } for c in db.scalars(select(ReligiousContent).where(ReligiousContent.enabled.is_(True))
                          .order_by(ReligiousContent.sort_order)).all()]

    logo = media_url(s.logo_asset_id)
    if logo:
        media.add(logo)
    return {
        "schema": SNAPSHOT_SCHEMA,
        "local_date": today.isoformat(),
        "engine": ENGINE_VERSION,
        "settings": {
            "name": s.name, "address": s.address, "city": s.city, "logo_url": logo, "timezone": s.timezone,
            "day_change": s.day_change, "footer_text": s.footer_text, "theme": s.theme or {}, "nusach": s.nusach,
            "in_israel": s.in_israel,
        },
        "zmanim_labels": {k: v[0] for k, v in ZMANIM_DEFS.items()},
        "enabled_zmanim": [k for k in ZMANIM_DEFS if k in prof.enabled_zmanim],
        "addition_labels": ADDITION_DEFS,
        "screens": screens_out,
        "links": {k: v for k, v in links.items() if k in ("prayer", "lesson")},
        "announcements": ann_out,
        "halachot": halachot_out,
        "halacha_selections": [{"id": str(x.id), "name": x.name} for x in selections],
        "memorials": {str(m.id): mem_dict(m) for m in memorials},
        "sponsorships": sponsors,
        "birthdays": {str(b.id): {"name": b.name, "message": b.message} for b in birthdays},
        "tzadikim": tzadikim,
        "content": content,
        "media": sorted(media),
        "days": days_out,
    }


def content_revision(db: Session) -> str:
    row = db.get(AppState, "content_revision")
    return row.value if row else "0"


def ensure_snapshot(db: Session, force: bool = False) -> DisplaySnapshot:
    """Return the current snapshot, rebuilding it when content or the local date changed."""
    s = get_settings_row(db)
    today = local_today(s.timezone)
    key = hashlib.sha256(f"{content_revision(db)}|{today}|{ENGINE_VERSION}|{SNAPSHOT_SCHEMA}|{SNAPSHOT_FORMAT}".encode()).hexdigest()
    latest = db.scalar(select(DisplaySnapshot).order_by(DisplaySnapshot.version.desc()).limit(1))
    if latest and latest.content_hash == key and not force:
        return latest
    with _build_lock:
        db.expire_all()
        latest = db.scalar(select(DisplaySnapshot).order_by(DisplaySnapshot.version.desc()).limit(1))
        if latest and latest.content_hash == key and not force:
            return latest
        payload = build_payload(db, today)
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
        version = (latest.version + 1) if latest else 1
        snap = DisplaySnapshot(version=version, checksum=checksum, content_hash=key, local_date=today,
                               payload=text, size_bytes=len(text.encode("utf-8")))
        db.add(snap)
        db.flush()
        # keep the last 5 snapshots (previous good versions remain available)
        old = db.scalars(select(DisplaySnapshot.id).order_by(DisplaySnapshot.version.desc()).offset(5)).all()
        if old:
            db.execute(delete(DisplaySnapshot).where(DisplaySnapshot.id.in_(old)))
        db.commit()
        return snap
