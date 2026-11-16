from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..common import commit_change, row
from ..db import get_db
from ..models import User
from ..security import current_user, require_admin
from ..services.calendar_engine import (
    ADDITION_DEFS, ENGINE_VERSION, LEARNING_DEFS, RELATIVE_ANCHORS, REMINDER_DEFS, ZMANIM_DEFS,
)
from ..services.snapshot import calc_profile, cached_calendar_days, get_profile_row, get_settings_row, zmanim_for_api

router = APIRouter(prefix="/api/v1", tags=["settings"])

NUSACHIM = {"ashkenazi": "אשכנזי", "sfard": "ספרד", "sefardi": "ספרדי / עדות המזרח", "teimani_baladi": "תימני בלאדי",
            "teimani_shami": "תימני שאמי", "chabad": "חב״ד"}


class ProfileIn(BaseModel):
    alos_method: str = Field(pattern="^(72min|90min|16.1deg|19.8deg)$")
    misheyakir_degrees: float = Field(ge=9, le=13)
    tzeit_method: str = Field(pattern="^(8.5deg|7.083deg|13.5min_zmaniyot|18min|20min)$")
    candle_lighting_minutes: int = Field(ge=0, le=60)
    shabbat_end_method: str = Field(pattern="^(tzeit|minutes_after_sunset)$")
    shabbat_end_minutes: int = Field(ge=0, le=120)
    rabbeinu_tam_minutes: int = Field(ge=50, le=120)
    rabbeinu_tam_zmaniyot: bool
    use_elevation: bool
    enabled_zmanim: list[str]

    @field_validator("enabled_zmanim")
    @classmethod
    def known(cls, v):
        bad = [x for x in v if x not in ZMANIM_DEFS]
        if bad:
            raise ValueError(f"זמנים לא מוכרים: {bad}")
        return v


class SettingsIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    logo_asset_id: str | None = None
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    elevation_m: float = Field(ge=-500, le=5000)
    timezone: str
    in_israel: bool
    walled_city_purim: bool = False
    nusach: str
    day_change: str = Field(pattern="^(sunset|midnight)$")
    day30_policy: str = Field(pattern="^(last_day|next_day)$")
    show_national_holidays: bool
    prayer_additions: list[str]
    reminders: list[str]
    daily_learning: list[str]
    footer_text: str | None = Field(default=None, max_length=500)
    theme: dict = {}
    profile: ProfileIn

    @field_validator("timezone")
    @classmethod
    def tz(cls, v):
        if v not in available_timezones():
            raise ValueError("אזור זמן לא תקין")
        return v

    @field_validator("nusach")
    @classmethod
    def nus(cls, v):
        if v not in NUSACHIM:
            raise ValueError("נוסח לא מוכר")
        return v


def settings_out(db: Session) -> dict:
    s = get_settings_row(db)
    p = get_profile_row(db, s)
    db.commit()
    out = row(s)
    out["profile"] = row(p)
    return out


@router.get("/settings")
def get_settings_api(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return settings_out(db)


@router.put("/settings")
def put_settings(body: SettingsIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    s = get_settings_row(db)
    p = get_profile_row(db, s)
    data = body.model_dump()
    prof = data.pop("profile")
    for lst, defs in (("prayer_additions", ADDITION_DEFS), ("reminders", REMINDER_DEFS), ("daily_learning", LEARNING_DEFS)):
        data[lst] = [x for x in data[lst] if x in defs]
    for k, v in data.items():
        setattr(s, k, v)
    for k, v in prof.items():
        setattr(p, k, v)
    p.engine_version = ENGINE_VERSION
    commit_change(db, request, user, "update", "settings", s.id)
    return settings_out(db)


@router.get("/settings/options")
def options(_: User = Depends(current_user)):
    return {
        "zmanim": [{"key": k, "label": v[0]} for k, v in ZMANIM_DEFS.items()],
        "relative_anchors": [{"key": k, "label": ZMANIM_DEFS[k][0]} for k in RELATIVE_ANCHORS],
        "additions": [{"key": k, "label": v} for k, v in ADDITION_DEFS.items()],
        "reminders": [{"key": k, "label": v} for k, v in REMINDER_DEFS.items()],
        "learning": [{"key": k, "label": v} for k, v in LEARNING_DEFS.items()],
        "nusachim": [{"key": k, "label": v} for k, v in NUSACHIM.items()],
        "engine": ENGINE_VERSION,
    }


@router.get("/zmanim")
def zmanim(day: date | None = Query(None, alias="date"), _: User = Depends(current_user),
           db: Session = Depends(get_db)):
    if day is None:
        day = datetime.now(ZoneInfo(get_settings_row(db).timezone)).date()
    return zmanim_for_api(db, day)


@router.get("/zmanim/range")
def zmanim_range(start: date, days: int = 7, _: User = Depends(current_user), db: Session = Depends(get_db)):
    if not 1 <= days <= 62:
        raise HTTPException(422, detail="ניתן לבקש בין 1 ל-62 ימים")
    prof = calc_profile(db)
    ds = [start + timedelta(days=i) for i in range(days)]
    cal = cached_calendar_days(db, prof, ds)
    return [{"date": d.isoformat(), "hebrew": cal[d]["h"]["str"], "parsha": cal[d]["parsha"],
             "holiday": cal[d]["holiday"], "z": cal[d]["z"]} for d in ds]
