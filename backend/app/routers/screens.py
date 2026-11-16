import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common import commit_change, get_or_404, row
from ..db import get_db
from ..models import SCREEN_TYPES, Screen, ScreenTemplate, User
from ..security import current_user, require_editor

router = APIRouter(prefix="/api/v1", tags=["screens"])

SCREEN_TYPE_LABELS = {
    "clock": "מסך שעון", "zmanim": "זמני היום", "prayers": "זמני תפילות", "lessons": "שיעורים",
    "prayers_lessons": "תפילות ושיעורים", "announcements": "הודעות", "halacha": "הלכות", "memorials": "עילוי נשמת",
    "sponsors": "פרנסים והקדשות", "birthdays": "ימי הולדת", "hilula": "יום הילולה", "shabbat": "מסך שבת וחג",
    "combined": "מסך משולב", "content": "תוכן תורני",
}


class Conditions(BaseModel):
    days_of_week: list[int] = []  # 0=Sunday..6=Saturday; empty = every day
    shabbat_mode: str = Field(default="any", pattern="^(any|only|hide)$")
    time_from: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    time_to: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    date_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("days_of_week")
    @classmethod
    def dow(cls, v):
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("ימים בטווח 0-6")
        return sorted(set(v))


class ScreenIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: str
    template_key: str = Field(default="default", max_length=40)
    enabled: bool = True
    duration_seconds: int = Field(default=20, ge=3, le=3600)
    config: dict = {}
    conditions: Conditions = Conditions()
    fallback: str = Field(default="skip", pattern="^(skip|message)$")
    fallback_text: str | None = Field(default=None, max_length=500)

    @field_validator("type")
    @classmethod
    def t(cls, v):
        if v not in SCREEN_TYPES:
            raise ValueError("סוג מסך לא מוכר")
        return v


class ScreenPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    template_key: str | None = Field(default=None, max_length=40)
    enabled: bool | None = None
    duration_seconds: int | None = Field(default=None, ge=3, le=3600)
    config: dict | None = None
    conditions: Conditions | None = None
    fallback: str | None = Field(default=None, pattern="^(skip|message)$")
    fallback_text: str | None = Field(default=None, max_length=500)


class OrderIn(BaseModel):
    ids: list[uuid.UUID]


@router.get("/screens")
def list_screens(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [row(s) for s in db.scalars(select(Screen).order_by(Screen.sort_order, Screen.name)).all()]


@router.get("/screens/types")
def screen_types(_: User = Depends(current_user), db: Session = Depends(get_db)):
    templates = db.scalars(select(ScreenTemplate).order_by(ScreenTemplate.screen_type, ScreenTemplate.key)).all()
    return {"types": [{"key": k, "label": SCREEN_TYPE_LABELS[k]} for k in SCREEN_TYPES],
            "templates": [row(t) for t in templates]}


@router.post("/screens", status_code=201)
def create_screen(body: ScreenIn, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    last = db.scalar(select(Screen.sort_order).order_by(Screen.sort_order.desc()).limit(1)) or 0
    s = Screen(**body.model_dump(exclude={"conditions"}), conditions=body.conditions.model_dump(), sort_order=last + 1)
    db.add(s)
    db.flush()
    commit_change(db, request, user, "create", "screen", s.id, {"name": s.name})
    return row(s)


@router.patch("/screens/{screen_id}")
def update_screen(screen_id: uuid.UUID, body: ScreenPatch, request: Request, user: User = Depends(require_editor),
                  db: Session = Depends(get_db)):
    s = get_or_404(db, Screen, screen_id, "המסך")
    data = body.model_dump(exclude_unset=True)
    if "conditions" in data and data["conditions"] is not None:
        data["conditions"] = body.conditions.model_dump()
    for k, v in data.items():
        setattr(s, k, v)
    commit_change(db, request, user, "update", "screen", s.id, {"fields": list(data)})
    return row(s)


@router.delete("/screens/{screen_id}", status_code=204)
def delete_screen(screen_id: uuid.UUID, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    s = get_or_404(db, Screen, screen_id, "המסך")
    db.delete(s)
    commit_change(db, request, user, "delete", "screen", screen_id, {"name": s.name})


@router.put("/screens/order")
def reorder(body: OrderIn, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    screens = {s.id: s for s in db.scalars(select(Screen)).all()}
    if set(body.ids) != set(screens):
        raise HTTPException(422, detail="רשימת הסדר חייבת לכלול את כל המסכים בדיוק פעם אחת")
    for i, sid in enumerate(body.ids):
        screens[sid].sort_order = i
    commit_change(db, request, user, "reorder", "screen")
    return [row(screens[i]) for i in body.ids]
