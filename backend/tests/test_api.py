"""API integration tests against a real PostgreSQL database (migrated with Alembic)."""
import hashlib
import io
import json
from datetime import date, timedelta

from PIL import Image

from app.services import hebrew as H


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["database"] == "ok"


def test_auth_required_and_uniform_errors(client):
    r = client.get("/api/v1/settings")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == 401


def test_login_logout_and_csrf(client, admin):
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["user"]["username"] == "admin"
    assert "password_hash" not in me.json()["user"]
    # state change without CSRF header is rejected
    r = client.post("/api/v1/screens", json={"name": "x", "type": "clock"})
    assert r.status_code == 403
    r = client.post("/api/v1/auth/logout", headers=admin.h())
    assert r.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_session_cookie_flags(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin12345!"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


def test_login_rate_limit(client):
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 429


def test_screens_crud_order_and_validation(admin):
    r = admin.post("/api/v1/screens", json={"name": "מסך בדיקה", "type": "clock", "duration_seconds": 12})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert admin.post("/api/v1/screens", json={"name": "x", "type": "bad"}).status_code == 422
    assert admin.post("/api/v1/screens", json={"name": "x", "type": "clock", "duration_seconds": 1}).status_code == 422
    r = admin.patch(f"/api/v1/screens/{sid}", json={"enabled": False, "conditions": {"days_of_week": [5, 6],
                                                                                     "shabbat_mode": "any"}})
    assert r.status_code == 200 and r.json()["enabled"] is False and r.json()["conditions"]["days_of_week"] == [5, 6]
    ids = [s["id"] for s in admin.get("/api/v1/screens").json()]
    new_order = [sid] + [i for i in ids if i != sid]
    r = admin.put("/api/v1/screens/order", json={"ids": new_order})
    assert r.status_code == 200
    assert admin.get("/api/v1/screens").json()[0]["id"] == sid
    assert admin.put("/api/v1/screens/order", json={"ids": new_order[:-1]}).status_code == 422
    assert admin.delete(f"/api/v1/screens/{sid}").status_code == 204


def test_announcements_sanitized_duplicate_and_dates(admin):
    screens = admin.get("/api/v1/screens").json()
    ann_screen = next(s for s in screens if s["type"] == "announcements")
    r = admin.post("/api/v1/announcements", json={
        "title": "בדיקה", "body_html": '<p onclick="x()">שלום<script>alert(1)</script><span class="c-gold">זהב</span></p>',
        "screen_ids": [ann_screen["id"]], "priority": 3})
    assert r.status_code == 201, r.text
    a = r.json()
    assert "script" not in a["body_html"] and "onclick" not in a["body_html"] and 'class="c-gold"' in a["body_html"]
    assert a["screen_ids"] == [ann_screen["id"]]
    dup = admin.post(f"/api/v1/announcements/{a['id']}/duplicate")
    assert dup.status_code == 201 and dup.json()["enabled"] is False
    bad = admin.post("/api/v1/announcements", json={"title": "x", "start_at": "2026-01-02T00:00:00Z",
                                                    "end_at": "2026-01-01T00:00:00Z"})
    assert bad.status_code == 422
    found = admin.get("/api/v1/announcements", params={"q": "בדיקה"}).json()
    assert found["total"] >= 2


def test_prayers_relative_and_exceptions(admin):
    types = {t["key"]: t for t in admin.get("/api/v1/prayer-types").json()}
    r = admin.post("/api/v1/prayers", json={
        "prayer_type_id": types["mincha"]["id"], "name": "מנחה גדולה בדיקה", "day_kind": "custom",
        "days_of_week": [1], "time_mode": "relative", "relative_zman": "mincha_gedola", "offset_minutes": 5,
        "rounding": "up5"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    monday = date(2026, 11, 16)
    day = admin.get("/api/v1/prayers/day", params={"date": monday.isoformat()}).json()
    mine = [i for i in day["items"] if i["id"] == pid]
    assert mine and mine[0]["time"].endswith(("0", "5"))
    assert admin.post(f"/api/v1/prayers/{pid}/exceptions", json={"date": monday.isoformat(), "action": "cancel"}).status_code == 201
    day = admin.get("/api/v1/prayers/day", params={"date": monday.isoformat()}).json()
    assert not [i for i in day["items"] if i["id"] == pid]
    assert admin.post("/api/v1/prayers", json={"prayer_type_id": types["mincha"]["id"], "name": "x",
                                               "time_mode": "relative"}).status_code == 422
    csv = admin.get("/api/v1/prayers/export.csv")
    assert csv.status_code == 200 and csv.text.startswith("﻿")


def test_lessons(admin):
    r = admin.post("/api/v1/lessons", json={"title": "שיעור בדיקה", "teacher": "מגיד", "schedules": [
        {"day_kind": "sun_thu", "time_mode": "fixed", "fixed_time": "21:00"},
        {"day_kind": "shabbat", "time_mode": "relative", "relative_zman": "sunset", "offset_minutes": -60}]})
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    assert len(r.json()["schedules"]) == 2
    body = r.json()
    body["schedules"] = body["schedules"][:1]
    r = admin.patch(f"/api/v1/lessons/{lid}", json={k: body[k] for k in ("title", "teacher", "schedules")})
    assert r.status_code == 200 and len(r.json()["schedules"]) == 1


def test_zmanim_api(admin):
    r = admin.get("/api/v1/zmanim", params={"date": "2026-11-20"}).json()
    assert r["hebrew_date"] == "י׳ כסלו התשפ״ז" and r["parsha"] == "ויצא"
    keys = {z["key"] for z in r["zmanim"]}
    assert {"sunrise", "sunset", "candle_lighting"} <= keys
    assert "python-zmanim" in r["engine"]


def test_halachot_import_selection_and_preview(admin):
    src = admin.post("/api/v1/halacha-sources", json={"title": "מקור בדיקה", "license": "CC-BY (בדיקה)"}).json()
    assert admin.post("/api/v1/halacha-sources", json={"title": "ללא רישיון"}).status_code == 422
    data = json.dumps([{"title": f"ה{i}", "text": f"טקסט {i}", "chapter": "פרק א", "category": "שבת", "tags": "שבת,בדיקה"}
                       for i in range(6)] + [{"title": "", "text": ""}], ensure_ascii=False).encode()
    r = admin.post("/api/v1/halachot/import", data={"source_id": src["id"], "confirm_license": "true"},
                   files={"file": ("h.json", data, "application/json")})
    assert r.status_code == 200 and r.json()["created"] == 6 and len(r.json()["errors"]) == 1
    nolicense = admin.post("/api/v1/halachot/import", data={"source_id": src["id"]},
                           files={"file": ("h.json", data, "application/json")})
    assert nolicense.status_code == 422
    csv_data = "title,text,source_ref\nכותרת,טקסט,סימן א\n".encode("utf-8-sig")
    r = admin.post("/api/v1/halachot/import", data={"source_id": src["id"], "confirm_license": "true"},
                   files={"file": ("h.csv", csv_data, "text/csv")})
    assert r.json()["created"] == 1
    assert admin.get("/api/v1/halachot", params={"q": "טקסט 3"}).json()["total"] == 1
    sels = admin.get("/api/v1/halachot/selections").json()
    sels.append({"name": "שבת", "mode": "random", "source_ids": [src["id"]], "per_day": 3})
    r = admin.put("/api/v1/halachot/selections", json={"selections": sels})
    assert r.status_code == 200, r.text
    new = next(s for s in r.json() if s["name"] == "שבת")
    assert new["eligible_count"] == 7
    prev = admin.get(f"/api/v1/halachot/selections/{new['id']}/preview", params={"days": 3}).json()
    flat = [h["id"] for d in prev[:2] for h in d["halachot"]]
    assert len(flat) == len(set(flat)) == 6


def _png(w=300, h=400) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 100, 50)).save(buf, "PNG")
    return buf.getvalue()


def test_media_upload_validation(admin, client):
    bad = admin.post("/api/v1/media", files={"file": ("x.png", b"<?php echo 1; ?>", "image/png")})
    assert bad.status_code == 415
    r = admin.post("/api/v1/media", files={"file": ("p.png", _png(), "image/png")}, data={"alt_text": "בדיקה"})
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["width"] == 300 and m["mime_type"] == "image/png"
    got = client.get(m["url"])
    assert got.status_code == 200 and got.headers["content-type"] == "image/png"


def test_hilulot_both_layout_data_and_active(admin):
    up = admin.post("/api/v1/media", files={"file": ("p.png", _png(), "image/png")}).json()
    today = date.today()
    h = H.to_hebrew(today)
    with_img = admin.post("/api/v1/hilulot", json={
        "display_name": "צדיק בדיקה א", "biography": "תיאור", "teaching_text": "תורה", "image_asset_id": up["id"],
        "dates": [{"hebrew_month": h.month, "hebrew_day": h.day}]})
    assert with_img.status_code == 201, with_img.text
    assert with_img.json()["image_url"]
    no_img = admin.post("/api/v1/hilulot", json={
        "display_name": "צדיק בדיקה ב", "biography": "תיאור", "teaching_text": "תורה",
        "dates": [{"hebrew_month": h.month, "hebrew_day": h.day, "display_end_offset_days": 1}]})
    assert no_img.status_code == 201 and no_img.json()["image_url"] is None
    act = admin.get("/api/v1/hilulot/active", params={"date": today.isoformat()}).json()
    names = [t["display_name"] for t in act["items"]]
    assert "צדיק בדיקה א" in names and "צדיק בדיקה ב" in names
    # end offset keeps B displayed tomorrow; A is not
    tom = admin.get("/api/v1/hilulot/active", params={"date": (today + timedelta(days=1)).isoformat()}).json()
    tnames = [t["display_name"] for t in tom["items"]]
    assert "צדיק בדיקה ב" in tnames and "צדיק בדיקה א" not in tnames
    bad = admin.post("/api/v1/hilulot", json={"display_name": "x", "biography": "x", "teaching_text": "x",
                                              "dates": [{"hebrew_month": 2, "hebrew_day": 30}]})
    assert bad.status_code == 422  # Iyar has 29 days
    tid = no_img.json()["id"]
    assert admin.get(f"/api/v1/hilulot/{tid}").status_code == 200
    assert admin.delete(f"/api/v1/hilulot/{tid}").status_code == 204


def test_memorials_sponsorships_birthdays_content(admin):
    r = admin.post("/api/v1/memorials", json={"full_name": "בדיקה", "parent_name": "הורה", "hebrew_day": 7,
                                              "hebrew_month": 12, "leap_year_policy": "both"})
    assert r.status_code == 201 and r.json()["next_yahrzeit"]
    assert admin.post("/api/v1/sponsorships", json={"start_date": "2026-01-01"}).status_code == 422
    r = admin.post("/api/v1/sponsorships", json={"honoree_name": "בדיקה", "period": "month", "start_date": "2026-01-01"})
    assert r.status_code == 201 and r.json()["effective_end"] == "2026-01-30"
    assert admin.post("/api/v1/birthdays", json={"name": "ב", "hebrew_day": 1, "hebrew_month": 7}).status_code == 201
    assert admin.post("/api/v1/content", json={"title": "סיפור", "body": "טקסט"}).status_code == 201


def test_device_pairing_readonly_and_snapshot_integrity(admin, client):
    from fastapi.testclient import TestClient
    from app.main import app
    dev = admin.post("/api/v1/devices", json={"name": "טלוויזיה ראשית"}).json()
    token = dev["token"]
    assert token.startswith("dev_") and "token_hash" not in dev
    tv = TestClient(app)
    auth = {"Authorization": f"Bearer {token}"}
    assert tv.get("/api/v1/display/version").status_code == 401  # unpaired
    v = tv.get("/api/v1/display/version", headers=auth).json()
    snap = tv.get("/api/v1/display/snapshot", headers=auth)
    assert snap.status_code == 200
    assert hashlib.sha256(snap.content).hexdigest() == snap.headers["x-snapshot-checksum"] == v["checksum"]
    payload = snap.json()
    for key in ("settings", "screens", "days", "tzadikim", "halachot", "announcements", "memorials", "sponsorships"):
        assert key in payload
    assert len(payload["days"]) >= 30
    today = payload["local_date"]
    assert payload["days"][today]["z"]["sunrise"]
    assert "password" not in snap.text and "token" not in json.dumps(payload["settings"])
    # TV token cannot touch admin APIs
    assert tv.get("/api/v1/settings", headers=auth).status_code == 401
    assert tv.post("/api/v1/screens", headers=auth, json={"name": "x", "type": "clock"}).status_code == 401
    hb = tv.post("/api/v1/devices/heartbeat", headers=auth, json={"snapshot_version": v["version"], "online": True})
    assert hb.status_code == 200
    # content change produces a new snapshot version
    admin.post("/api/v1/announcements", json={"title": "חדש לגמרי"})
    v2 = tv.get("/api/v1/display/version", headers=auth).json()
    assert v2["version"] > v["version"]
    # revoke
    admin.post(f"/api/v1/devices/{dev['id']}/revoke")
    assert tv.get("/api/v1/display/version", headers=auth).status_code == 401
    rot = admin.post(f"/api/v1/devices/{dev['id']}/rotate").json()
    assert tv.get("/api/v1/display/version", headers={"Authorization": f"Bearer {rot['token']}"}).status_code == 200
    assert tv.get("/api/v1/display/version", headers=auth).status_code == 401


def test_settings_update_invalidates_and_validates(admin):
    s = admin.get("/api/v1/settings").json()
    body = {k: s[k] for k in ("name", "address", "city", "latitude", "longitude", "elevation_m", "timezone", "in_israel",
                              "walled_city_purim", "nusach", "day_change", "day30_policy", "show_national_holidays",
                              "prayer_additions", "reminders", "daily_learning", "footer_text", "theme")}
    body["profile"] = {k: s["profile"][k] for k in ("alos_method", "misheyakir_degrees", "tzeit_method",
                                                    "candle_lighting_minutes", "shabbat_end_method", "shabbat_end_minutes",
                                                    "rabbeinu_tam_minutes", "rabbeinu_tam_zmaniyot", "use_elevation",
                                                    "enabled_zmanim")}
    body["name"] = "בית כנסת בדיקה"
    body["profile"]["candle_lighting_minutes"] = 40
    r = admin.put("/api/v1/settings", json=body)
    assert r.status_code == 200 and r.json()["profile"]["candle_lighting_minutes"] == 40
    z = admin.get("/api/v1/zmanim", params={"date": "2026-11-20"}).json()
    times = {x["key"]: x["time"] for x in z["zmanim"]}
    sunset = int(times["sunset"][:2]) * 60 + int(times["sunset"][3:])
    candle = int(times["candle_lighting"][:2]) * 60 + int(times["candle_lighting"][3:])
    assert 39 <= sunset - candle <= 41
    body["timezone"] = "Mars/Olympus"
    assert admin.put("/api/v1/settings", json=body).status_code == 422


def test_users_roles(admin, client):
    r = admin.post("/api/v1/users", json={"username": "editor1", "password": "Editor12345!", "role": "editor"})
    assert r.status_code == 201
    assert admin.post("/api/v1/users", json={"username": "weak", "password": "1234567890"}).status_code == 422
    from fastapi.testclient import TestClient
    from app.main import app
    ed = TestClient(app)
    lr = ed.post("/api/v1/auth/login", json={"username": "editor1", "password": "Editor12345!"})
    csrf = lr.json()["csrf_token"]
    assert ed.post("/api/v1/announcements", headers={"X-CSRF-Token": csrf}, json={"title": "מעורך"}).status_code == 201
    assert ed.get("/api/v1/users").status_code == 403
    assert ed.post("/api/v1/devices", headers={"X-CSRF-Token": csrf}, json={"name": "x"}).status_code == 403
    logs = admin.get("/api/v1/audit-logs").json()
    assert logs["total"] > 0 and any(x["action"] == "login" for x in logs["items"])


def test_backup_and_restore_roundtrip(admin, client):
    b = admin.get("/api/v1/maintenance/backup")
    assert b.status_code == 200
    data = b.json()
    n_ann = len(data["tables"]["announcements"])
    admin.post("/api/v1/announcements", json={"title": "יימחק בשחזור"})
    r = admin.post("/api/v1/maintenance/restore", files={"file": ("b.json", b.content, "application/json")})
    assert r.status_code == 200, r.text
    # sessions were cleared by restore → log in again
    from tests.conftest import Admin
    a2 = Admin(client)
    assert a2.get("/api/v1/announcements").json()["total"] == n_ann
    assert a2.get("/api/v1/maintenance/status").json()["counts"]["announcements"] == n_ann
    bad = a2.post("/api/v1/maintenance/restore", files={"file": ("b.json", b'{"format":"x"}', "application/json")})
    assert bad.status_code == 422

