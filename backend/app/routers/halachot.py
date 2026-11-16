"""Licensed halacha corpus: sources, categories, chapters, halachot, tags, import, selections
and rotation preview. Every source must carry a license/attribution."""
import csv
import io
import json
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from ..common import commit_change, get_or_404, paginate, row
from ..db import get_db
from ..models import (
    Halacha, HalachaCategory, HalachaChapter, HalachaDisplayHistory, HalachaSelection, HalachaSource, HalachaTag,
    HalachaTagLink, User,
)
from ..security import current_user, require_editor
from ..services.scheduling import plan_halachot
from ..services.snapshot import eligible_halachot

router = APIRouter(prefix="/api/v1", tags=["halachot"])


class SourceIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str | None = Field(default=None, max_length=200)
    license: str = Field(min_length=2, max_length=200)
    attribution: str | None = Field(default=None, max_length=2000)
    source_url: str | None = Field(default=None, max_length=400)
    is_sample: bool = False
    enabled: bool = True


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sort_order: int = 0


class ChapterIn(BaseModel):
    source_id: uuid.UUID
    category_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    sort_order: int = 0


class HalachaIn(BaseModel):
    source_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=8000)
    source_ref: str | None = Field(default=None, max_length=200)
    sort_order: int = 0
    enabled: bool = True
    tags: list[str] = []


class SelectionIn(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    mode: str = Field(default="sequential", pattern="^(sequential|random)$")
    source_ids: list[uuid.UUID] = []
    category_ids: list[uuid.UUID] = []
    chapter_ids: list[uuid.UUID] = []
    halacha_ids: list[uuid.UUID] = []
    tag_ids: list[uuid.UUID] = []
    per_day: int = Field(default=1, ge=1, le=20)
    start_date: date | None = None
    seed: int = Field(default=1, ge=0, le=2_000_000_000)
    active: bool = True


class SelectionsIn(BaseModel):
    selections: list[SelectionIn]


# ---------------------------------------------------------------- sources/categories/chapters
@router.get("/halacha-sources")
def list_sources(_: User = Depends(current_user), db: Session = Depends(get_db)):
    counts = dict(db.execute(select(Halacha.source_id, func.count()).group_by(Halacha.source_id)).all())
    return [{**row(s), "count": counts.get(s.id, 0)} for s in db.scalars(select(HalachaSource).order_by(HalachaSource.title)).all()]


@router.post("/halacha-sources", status_code=201)
def create_source(body: SourceIn, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    s = HalachaSource(**body.model_dump())
    db.add(s)
    db.flush()
    commit_change(db, request, user, "create", "halacha_source", s.id, {"title": s.title})
    return row(s)


@router.patch("/halacha-sources/{sid}")
def update_source(sid: uuid.UUID, body: SourceIn, request: Request, user: User = Depends(require_editor),
                  db: Session = Depends(get_db)):
    s = get_or_404(db, HalachaSource, sid, "המקור")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    commit_change(db, request, user, "update", "halacha_source", s.id)
    return row(s)


@router.delete("/halacha-sources/{sid}", status_code=204)
def delete_source(sid: uuid.UUID, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    s = get_or_404(db, HalachaSource, sid, "המקור")
    db.delete(s)
    commit_change(db, request, user, "delete", "halacha_source", sid, {"title": s.title})


@router.get("/halacha-categories")
def list_categories(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [row(c) for c in db.scalars(select(HalachaCategory).order_by(HalachaCategory.sort_order, HalachaCategory.name))]


@router.post("/halacha-categories", status_code=201)
def create_category(body: CategoryIn, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    if db.scalar(select(HalachaCategory).where(HalachaCategory.name == body.name)):
        raise HTTPException(409, detail="קטגוריה בשם זה כבר קיימת")
    c = HalachaCategory(**body.model_dump())
    db.add(c)
    db.flush()
    commit_change(db, request, user, "create", "halacha_category", c.id)
    return row(c)


@router.delete("/halacha-categories/{cid}", status_code=204)
def delete_category(cid: uuid.UUID, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    c = get_or_404(db, HalachaCategory, cid, "הקטגוריה")
    db.delete(c)
    commit_change(db, request, user, "delete", "halacha_category", cid)


@router.get("/halacha-chapters")
def list_chapters(source_id: uuid.UUID | None = None, _: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(HalachaChapter).order_by(HalachaChapter.sort_order, HalachaChapter.title)
    if source_id:
        q = q.where(HalachaChapter.source_id == source_id)
    return [row(c) for c in db.scalars(q)]


@router.post("/halacha-chapters", status_code=201)
def create_chapter(body: ChapterIn, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    c = HalachaChapter(**body.model_dump())
    db.add(c)
    db.flush()
    commit_change(db, request, user, "create", "halacha_chapter", c.id)
    return row(c)


@router.delete("/halacha-chapters/{cid}", status_code=204)
def delete_chapter(cid: uuid.UUID, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    c = get_or_404(db, HalachaChapter, cid, "הפרק")
    db.delete(c)
    commit_change(db, request, user, "delete", "halacha_chapter", cid)


@router.get("/halacha-tags")
def list_tags(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [row(t) for t in db.scalars(select(HalachaTag).order_by(HalachaTag.name))]


# ---------------------------------------------------------------- halachot
def _tags_for(db: Session, ids: list) -> dict:
    out: dict = {}
    for hid, name in db.execute(select(HalachaTagLink.halacha_id, HalachaTag.name)
                                .join(HalachaTag, HalachaTag.id == HalachaTagLink.tag_id)
                                .where(HalachaTagLink.halacha_id.in_(ids))).all():
        out.setdefault(hid, []).append(name)
    return out


def _set_tags(db: Session, h: Halacha, names: list[str]):
    db.execute(delete(HalachaTagLink).where(HalachaTagLink.halacha_id == h.id))
    for name in dict.fromkeys(n.strip() for n in names if n.strip()):
        tag = db.scalar(select(HalachaTag).where(HalachaTag.name == name[:80]))
        if not tag:
            tag = HalachaTag(name=name[:80])
            db.add(tag)
            db.flush()
        db.add(HalachaTagLink(halacha_id=h.id, tag_id=tag.id))


@router.get("/halachot")
def list_halachot(q: str | None = None, source_id: uuid.UUID | None = None, category_id: uuid.UUID | None = None,
                  chapter_id: uuid.UUID | None = None, tag: str | None = None,
                  limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                  _: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Halacha).order_by(Halacha.source_id, Halacha.sort_order, Halacha.title)
    if q:
        query = query.where(or_(Halacha.title.ilike(f"%{q}%"), Halacha.text.ilike(f"%{q}%"),
                                Halacha.source_ref.ilike(f"%{q}%")))
    if source_id:
        query = query.where(Halacha.source_id == source_id)
    if category_id:
        query = query.where(Halacha.category_id == category_id)
    if chapter_id:
        query = query.where(Halacha.chapter_id == chapter_id)
    if tag:
        query = query.where(Halacha.id.in_(select(HalachaTagLink.halacha_id).join(HalachaTag).where(HalachaTag.name == tag)))
    items, total = paginate(db, query, limit, offset)
    tags = _tags_for(db, [h.id for h in items])
    return {"items": [{**row(h), "tags": tags.get(h.id, [])} for h in items], "total": total}


@router.post("/halachot", status_code=201)
def create_halacha(body: HalachaIn, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    get_or_404(db, HalachaSource, body.source_id, "המקור")
    h = Halacha(**body.model_dump(exclude={"tags"}))
    db.add(h)
    db.flush()
    _set_tags(db, h, body.tags)
    commit_change(db, request, user, "create", "halacha", h.id, {"title": h.title})
    return {**row(h), "tags": body.tags}


@router.patch("/halachot/{hid}")
def update_halacha(hid: uuid.UUID, body: HalachaIn, request: Request, user: User = Depends(require_editor),
                   db: Session = Depends(get_db)):
    h = get_or_404(db, Halacha, hid, "ההלכה")
    for k, v in body.model_dump(exclude={"tags"}).items():
        setattr(h, k, v)
    _set_tags(db, h, body.tags)
    commit_change(db, request, user, "update", "halacha", h.id)
    return {**row(h), "tags": body.tags}


@router.delete("/halachot/{hid}", status_code=204)
def delete_halacha(hid: uuid.UUID, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    h = get_or_404(db, Halacha, hid, "ההלכה")
    db.delete(h)
    commit_change(db, request, user, "delete", "halacha", hid)


@router.post("/halachot/import")
async def import_halachot(request: Request, file: UploadFile = File(...), source_id: uuid.UUID = Form(...),
                          confirm_license: bool = Form(False), user: User = Depends(require_editor),
                          db: Session = Depends(get_db)):
    """Import JSON (list of {title,text,source_ref,chapter,category,tags}) or CSV with the same
    columns. The admin must confirm the content is licensed for this use."""
    if not confirm_license:
        raise HTTPException(422, detail="יש לאשר שהתוכן המיובא מורשה לשימוש")
    src = get_or_404(db, HalachaSource, source_id, "המקור")
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, detail="קובץ הייבוא גדול מדי (עד 5MB)")
    text = raw.decode("utf-8-sig", errors="strict")
    name = (file.filename or "").lower()
    try:
        if name.endswith(".json"):
            records = json.loads(text)
            if isinstance(records, dict):
                records = records.get("halachot") or records.get("items") or []
        else:
            records = list(csv.DictReader(io.StringIO(text)))
    except (ValueError, csv.Error) as e:
        raise HTTPException(422, detail=f"קובץ לא תקין: {e}")
    if not isinstance(records, list):
        raise HTTPException(422, detail="מבנה קובץ לא תקין")
    chapters = {c.title: c for c in db.scalars(select(HalachaChapter).where(HalachaChapter.source_id == src.id))}
    cats = {c.name: c for c in db.scalars(select(HalachaCategory))}
    created, errors = 0, []
    base_order = (db.scalar(select(func.max(Halacha.sort_order)).where(Halacha.source_id == src.id)) or 0) + 1
    for i, r in enumerate(records):
        try:
            title = str(r.get("title") or "").strip()[:200]
            body = str(r.get("text") or "").strip()
            if not title or not body:
                raise ValueError("חסרים כותרת או טקסט")
            if len(body) > 8000:
                raise ValueError("טקסט ארוך מדי")
            ch = None
            if r.get("chapter"):
                ct = str(r["chapter"])[:200]
                ch = chapters.get(ct)
                if not ch:
                    ch = HalachaChapter(source_id=src.id, title=ct, sort_order=len(chapters))
                    db.add(ch)
                    db.flush()
                    chapters[ct] = ch
            cat = None
            if r.get("category"):
                cn = str(r["category"])[:120]
                cat = cats.get(cn)
                if not cat:
                    cat = HalachaCategory(name=cn)
                    db.add(cat)
                    db.flush()
                    cats[cn] = cat
            h = Halacha(source_id=src.id, chapter_id=ch.id if ch else None, category_id=cat.id if cat else None,
                        title=title, text=body, source_ref=(str(r.get("source_ref") or "")[:200] or None),
                        sort_order=base_order + i)
            db.add(h)
            db.flush()
            tags = r.get("tags") or []
            if isinstance(tags, str):
                tags = [t for t in tags.replace(";", ",").split(",")]
            _set_tags(db, h, tags)
            created += 1
        except (ValueError, TypeError, AttributeError) as e:
            errors.append({"row": i + 1, "error": str(e)})
    commit_change(db, request, user, "import", "halacha", src.id, {"created": created, "errors": len(errors)})
    return {"created": created, "errors": errors[:50]}


# ---------------------------------------------------------------- selections & rotation
@router.get("/halachot/selections")
def list_selections(_: User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for s in db.scalars(select(HalachaSelection).order_by(HalachaSelection.created_at)):
        d = row(s)
        d["eligible_count"] = len(eligible_halachot(db, s))
        out.append(d)
    return out


@router.put("/halachot/selections")
def put_selections(body: SelectionsIn, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    existing = {s.id: s for s in db.scalars(select(HalachaSelection))}
    keep = set()
    for sin in body.selections:
        data = sin.model_dump(exclude={"id"})
        for k in ("source_ids", "category_ids", "chapter_ids", "halacha_ids", "tag_ids"):
            data[k] = [str(x) for x in data[k]]
        s = existing.get(sin.id) if sin.id else None
        if s is None:
            s = HalachaSelection(start_date=data.pop("start_date") or date.today(), **{k: v for k, v in data.items() if k != "start_date"})
            db.add(s)
        else:
            changed_filter = any(getattr(s, k) != data[k] for k in ("mode", "source_ids", "category_ids", "chapter_ids",
                                                                    "halacha_ids", "tag_ids", "per_day"))
            sd = data.pop("start_date")
            for k, v in data.items():
                setattr(s, k, v)
            if sd:
                s.start_date = sd
            elif changed_filter:
                s.start_date = date.today()  # selection changed → restart rotation from today
        db.flush()
        keep.add(s.id)
    for sid, s in existing.items():
        if sid not in keep:
            db.delete(s)
    commit_change(db, request, user, "update", "halacha_selections")
    return list_selections(user, db)


@router.get("/halachot/selections/{sid}/preview")
def preview_selection(sid: uuid.UUID, days: int = Query(7, ge=1, le=60), _: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    s = get_or_404(db, HalachaSelection, sid, "הבחירה")
    items = eligible_halachot(db, s)
    today = date.today()
    return [{"date": (today + timedelta(days=i)).isoformat(),
             "halachot": [{"id": str(h.id), "title": h.title}
                          for h in plan_halachot(items, s.mode, s.per_day, s.seed, s.start_date, today + timedelta(days=i))]}
            for i in range(days)]


@router.get("/halachot/history")
def history(limit: int = Query(100, ge=1, le=500), _: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(HalachaDisplayHistory, Halacha.title).join(Halacha, Halacha.id == HalachaDisplayHistory.halacha_id)
                      .order_by(HalachaDisplayHistory.shown_on.desc()).limit(limit)).all()
    return [{"date": h.shown_on.isoformat(), "halacha_id": str(h.halacha_id), "title": t,
             "selection_id": str(h.selection_id) if h.selection_id else None} for h, t in rows]
