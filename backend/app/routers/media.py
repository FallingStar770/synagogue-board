"""Secure image upload: size limit, real format detection with Pillow (not trusting the client
MIME/extension), re-encoding to strip metadata/payloads, content hashing."""
import hashlib
import io
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common import commit_change, get_or_404, row
from ..config import get_settings
from ..db import get_db
from ..models import MediaAsset, User
from ..security import require_editor

router = APIRouter(prefix="/api/v1", tags=["media"])
ALLOWED = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"), "WEBP": ("image/webp", "webp")}
MAX_PIXELS = 40_000_000
MAX_SIDE = 2560  # TV never needs more; keeps snapshot media small for offline cache


def media_dir():
    d = get_settings().media_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/media", status_code=201)
async def upload(request: Request, file: UploadFile = File(...), alt_text: str | None = Form(None),
                 attribution: str | None = Form(None), license: str | None = Form(None),
                 user: User = Depends(require_editor), db: Session = Depends(get_db)):
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, detail=f"הקובץ גדול מדי (מקסימום {get_settings().max_upload_mb}MB)")
    if not data:
        raise HTTPException(422, detail="קובץ ריק")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError):
        raise HTTPException(415, detail="הקובץ אינו תמונה תקינה (JPEG / PNG / WEBP בלבד)")
    if fmt not in ALLOWED:
        raise HTTPException(415, detail="סוג קובץ לא נתמך (JPEG / PNG / WEBP בלבד)")
    # re-encode: strips EXIF/ICC payloads and any trailing data
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(out, "JPEG", quality=88, optimize=True)
    elif fmt == "PNG":
        img.save(out, "PNG", optimize=True)
    else:
        img.save(out, "WEBP", quality=88)
    clean = out.getvalue()
    mime, ext = ALLOWED[fmt]
    key = f"{uuid.uuid4().hex}.{ext}"
    asset = MediaAsset(data=clean, original_filename=(file.filename or "image")[:255], mime_type=mime, size_bytes=len(clean),
                       width=img.size[0], height=img.size[1], sha256=hashlib.sha256(clean).hexdigest(),
                       storage_key=key, alt_text=alt_text, attribution=attribution, license=license, uploaded_by=user.id)
    db.add(asset)
    db.flush()
    commit_change(db, request, user, "upload", "media", asset.id, {"name": asset.original_filename})
    return media_out(asset)


def media_out(a: MediaAsset) -> dict:
    d = row(a, exclude={"storage_key"})
    d["url"] = f"/api/v1/media/{a.id}"
    return d


@router.get("/media")
def list_media(_: User = Depends(require_editor), db: Session = Depends(get_db)):
    return [media_out(a) for a in db.scalars(select(MediaAsset).order_by(MediaAsset.created_at.desc())).all()]


@router.get("/media/{asset_id}")
def get_media(asset_id: uuid.UUID, db: Session = Depends(get_db)):
    """Public read by unguessable UUID (capability URL) so the TV can cache images offline
    and <img> tags work without credentials. Never lists or enumerates assets."""
    a = get_or_404(db, MediaAsset, asset_id, "הקובץ")
    headers = {"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff",
               "ETag": a.sha256}
    if a.data is not None:
        return Response(a.data, media_type=a.mime_type, headers=headers)
    path = media_dir() / a.storage_key  # legacy: files saved on disk by older versions
    if not path.exists():
        raise HTTPException(404, detail="הקובץ חסר באחסון")
    return FileResponse(path, media_type=a.mime_type, headers=headers)


@router.delete("/media/{asset_id}", status_code=204)
def delete_media(asset_id: uuid.UUID, request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    a = get_or_404(db, MediaAsset, asset_id, "הקובץ")
    db.delete(a)
    commit_change(db, request, user, "delete", "media", asset_id)
    (media_dir() / a.storage_key).unlink(missing_ok=True)
