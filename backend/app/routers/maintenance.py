"""Maintenance: system status, JSON backup export / restore, snapshot rebuild."""
import base64
import json
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from ..common import commit_change, jsonable
from ..config import get_settings
from ..db import Base, get_db
from ..models import (
    Announcement, AuditLog, DisplayDevice, DisplaySnapshot, Halacha, MediaAsset, Memorial, PrayerSchedule, Screen,
    Tzadik, User, UserSession, ZmanimDailyCache,
)
from ..security import audit, require_admin
from ..services.calendar_engine import ENGINE_VERSION
from ..services.snapshot import ensure_snapshot

router = APIRouter(prefix="/api/v1", tags=["maintenance"])
BACKUP_FORMAT = "synagogue-board-backup/1"
# tables never included in a content backup (security/session/cache data)
EXCLUDED = {"sessions", "audit_logs", "display_snapshots", "zmanim_daily_cache", "alembic_version"}


@router.get("/maintenance/status")
def status(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    snap = db.scalar(select(DisplaySnapshot).order_by(DisplaySnapshot.version.desc()).limit(1))
    devices = db.scalars(select(DisplayDevice)).all()
    now = datetime.now(timezone.utc)

    def count(m):
        return db.scalar(select(func.count()).select_from(m))
    return {
        "server_time": now.isoformat(),
        "engine": ENGINE_VERSION,
        "database": db.execute(text("select version()")).scalar(),
        "snapshot": {"version": snap.version, "size": snap.size_bytes, "created_at": snap.created_at.isoformat(),
                     "local_date": snap.local_date.isoformat()} if snap else None,
        "devices": [{"name": d.name, "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
                     "online": bool(d.last_seen_at and (now - d.last_seen_at).total_seconds() < 180),
                     "snapshot_version": d.last_snapshot_version, "revoked": d.revoked} for d in devices],
        "counts": {"screens": count(Screen), "announcements": count(Announcement), "prayers": count(PrayerSchedule),
                   "halachot": count(Halacha), "memorials": count(Memorial), "tzadikim": count(Tzadik),
                   "media": count(MediaAsset), "users": count(User)},
        "environment": get_settings().environment,
    }


@router.post("/maintenance/rebuild-snapshot")
def rebuild(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    db.execute(delete(ZmanimDailyCache))
    db.commit()
    snap = ensure_snapshot(db, force=True)
    audit(db, request, user, "rebuild", "snapshot", details={"version": snap.version})
    db.commit()
    return {"version": snap.version, "size": snap.size_bytes}


def _tables():
    return [t for t in Base.metadata.sorted_tables if t.name not in EXCLUDED]


@router.get("/maintenance/backup")
def backup(request: Request, include_media: bool = True, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Full content backup as JSON (users included with password hashes — store it securely).
    For encrypted, scheduled database backups use scripts/backup.sh (pg_dump + GPG/age)."""
    data = {"format": BACKUP_FORMAT, "created_at": datetime.now(timezone.utc).isoformat(), "engine": ENGINE_VERSION,
            "tables": {}}
    for t in _tables():
        rows = db.execute(t.select()).mappings().all()
        data["tables"][t.name] = [{k: jsonable(v) for k, v in r.items()} for r in rows]
    if include_media:  # legacy disk files (older versions) are embedded too
        media_dir = get_settings().media_dir
        files = {}
        for a in db.scalars(select(MediaAsset).where(MediaAsset.data.is_(None))):
            p = media_dir / a.storage_key
            if p.exists():
                files[a.storage_key] = base64.b64encode(p.read_bytes()).decode()
        data["media_files"] = files
    else:
        for r in data["tables"].get("media_assets", []):
            r.pop("data", None)
    audit(db, request, user, "backup", "system")
    db.commit()
    body = json.dumps(data, ensure_ascii=False)
    name = f"synagogue-backup-{datetime.now():%Y%m%d-%H%M}.json"
    return Response(body, media_type="application/json",
                    headers={"Content-Disposition": f"attachment; filename={name}"})


def _coerce(col, v):
    if v is None:
        return None
    if isinstance(v, dict) and "$b64" in v:
        return base64.b64decode(v["$b64"])
    pt = None
    try:
        pt = col.type.python_type
    except NotImplementedError:
        return v
    if pt is datetime:
        return datetime.fromisoformat(v)
    if pt is date:
        return date.fromisoformat(v)
    if pt is time:
        return time.fromisoformat(v)
    return v


@router.post("/maintenance/restore")
async def restore(request: Request, file: UploadFile = File(...), user: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    """Replace all content with a backup file (single transaction — all or nothing)."""
    raw = await file.read(200 * 1024 * 1024)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(422, detail="קובץ גיבוי לא תקין")
    if data.get("format") != BACKUP_FORMAT:
        raise HTTPException(422, detail="פורמט גיבוי לא נתמך")
    tables = _tables()
    if "users" not in data["tables"] or not any(u.get("role") == "admin" for u in data["tables"]["users"]):
        raise HTTPException(422, detail="הגיבוי אינו כולל מנהל — השחזור בוטל כדי למנוע נעילה")
    try:
        db.execute(delete(UserSession))
        for t in reversed(tables):
            db.execute(t.delete())
        for t in tables:
            rows = data["tables"].get(t.name, [])
            cols = {c.name: c for c in t.columns}
            clean = [{k: _coerce(cols[k], v) for k, v in r.items() if k in cols} for r in rows]
            if clean:
                db.execute(t.insert(), clean)
        db.execute(delete(DisplaySnapshot))
        db.execute(delete(ZmanimDailyCache))
        for key, b64 in (data.get("media_files") or {}).items():  # legacy backups: move files into the DB
            asset = db.scalar(select(MediaAsset).where(MediaAsset.storage_key == key))
            if asset is not None and asset.data is None:
                asset.data = base64.b64decode(b64)
        db.add(AuditLog(user_id=None, username=user.username, action="restore", entity="system",
                        details={"from": data.get("created_at")}))
        commit_change(db, request, None, "restore", "system")
    except Exception as e:  # noqa: BLE001 - roll back the whole restore on any failure
        db.rollback()
        raise HTTPException(422, detail=f"השחזור נכשל ובוטל: {e}")
    return {"ok": True, "message": "השחזור הושלם. יש להתחבר מחדש."}
