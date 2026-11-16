"""TV devices (pairing tokens) and read-only display endpoints."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common import get_or_404, row
from ..db import get_db
from ..models import DisplayDevice, User
from ..security import audit, client_ip, device_from_request, display_reader, new_device_token, require_admin, sha256_hex
from ..services.snapshot import ensure_snapshot

router = APIRouter(prefix="/api/v1", tags=["display"])


class DeviceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class HeartbeatIn(BaseModel):
    snapshot_version: int | None = None
    online: bool = True
    current_screen: str | None = Field(default=None, max_length=120)
    app_version: str | None = Field(default=None, max_length=40)
    screen_size: str | None = Field(default=None, max_length=40)
    errors: list[str] = Field(default=[], max_length=20)


def device_out(d: DisplayDevice) -> dict:
    out = row(d, exclude={"token_hash"})
    if d.last_seen_at:
        age = (datetime.now(timezone.utc) - d.last_seen_at).total_seconds()
        out["status"] = "online" if age < 180 else ("stale" if age < 3600 else "offline")
        out["seconds_since_seen"] = int(age)
    else:
        out["status"] = "never"
    return out


@router.get("/devices")
def list_devices(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [device_out(d) for d in db.scalars(select(DisplayDevice).order_by(DisplayDevice.created_at))]


@router.post("/devices", status_code=201)
def create_device(body: DeviceIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    token = new_device_token()
    d = DisplayDevice(name=body.name, token_hash=sha256_hex(token), token_hint=token[-6:])
    db.add(d)
    db.flush()
    audit(db, request, user, "create", "device", d.id, {"name": d.name})
    db.commit()
    # the plain token is returned ONCE; only its hash is stored
    return {**device_out(d), "token": token}


@router.post("/devices/{did}/rotate")
def rotate_device(did: uuid.UUID, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    d = get_or_404(db, DisplayDevice, did, "ההתקן")
    token = new_device_token()
    d.token_hash, d.token_hint, d.revoked = sha256_hex(token), token[-6:], False
    audit(db, request, user, "rotate_token", "device", d.id)
    db.commit()
    return {**device_out(d), "token": token}


@router.patch("/devices/{did}")
def update_device(did: uuid.UUID, body: DeviceIn, request: Request, user: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    d = get_or_404(db, DisplayDevice, did, "ההתקן")
    d.name = body.name
    audit(db, request, user, "update", "device", d.id)
    db.commit()
    return device_out(d)


@router.post("/devices/{did}/revoke")
def revoke_device(did: uuid.UUID, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    d = get_or_404(db, DisplayDevice, did, "ההתקן")
    d.revoked = True
    audit(db, request, user, "revoke", "device", d.id)
    db.commit()
    return device_out(d)


@router.delete("/devices/{did}", status_code=204)
def delete_device(did: uuid.UUID, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    d = get_or_404(db, DisplayDevice, did, "ההתקן")
    db.delete(d)
    audit(db, request, user, "delete", "device", did)
    db.commit()


# ---------------------------------------------------------------- read-only display API
@router.get("/display/version")
def display_version(request: Request, reader=Depends(display_reader), db: Session = Depends(get_db)):
    snap = ensure_snapshot(db)
    return {"version": snap.version, "checksum": snap.checksum, "size": snap.size_bytes,
            "local_date": snap.local_date.isoformat(), "server_time": datetime.now(timezone.utc).isoformat()}


@router.get("/display/snapshot")
def display_snapshot(request: Request, reader=Depends(display_reader), db: Session = Depends(get_db)):
    snap = ensure_snapshot(db)
    if isinstance(reader, DisplayDevice):
        reader.last_snapshot_version = snap.version
        reader.last_seen_at = datetime.now(timezone.utc)
        reader.last_ip = client_ip(request)
        db.commit()
    return Response(snap.payload.encode("utf-8"), media_type="application/json; charset=utf-8", headers={
        "X-Snapshot-Version": str(snap.version), "X-Snapshot-Checksum": snap.checksum,
        "Cache-Control": "no-store", "Access-Control-Expose-Headers": "X-Snapshot-Version, X-Snapshot-Checksum"})


@router.post("/devices/heartbeat")
def heartbeat(body: HeartbeatIn, request: Request, db: Session = Depends(get_db)):
    dev = device_from_request(request, db)
    if not dev:
        raise HTTPException(401, detail="התקן לא מזוהה")
    dev.last_seen_at = datetime.now(timezone.utc)
    dev.last_ip = client_ip(request)
    dev.last_snapshot_version = body.snapshot_version
    dev.last_status = body.model_dump()
    db.commit()
    return {"ok": True, "server_time": datetime.now(timezone.utc).isoformat()}
