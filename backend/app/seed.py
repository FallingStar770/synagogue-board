"""Base data (always) and demo data (opt-in, every record clearly marked as a sample)."""
import io
import uuid
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    Announcement, Birthday, Halacha, HalachaCategory, HalachaSelection, HalachaSource, HilulaDate, Lesson,
    LessonSchedule, MediaAsset, Memorial, PrayerSchedule, PrayerType, Screen, ScreenTemplate, Sponsorship, Tzadik, User,
)
from .security import bump_content_revision, hash_password, validate_password_strength
from .services import hebrew as H
from .services.snapshot import get_profile_row, get_settings_row

PRAYER_TYPES = [("netz", "ותיקין (נץ)", 0), ("shacharit", "שחרית", 1), ("musaf", "מוסף", 2), ("mincha", "מנחה", 3),
                ("arvit", "ערבית", 4), ("selichot", "סליחות", 5), ("kabbalat_shabbat", "קבלת שבת", 6), ("other", "אחר", 9)]

TEMPLATES = [
    ("clock", "default", "שעון גדול עם תאריך וזמנים", {"show_seconds": True, "zmanim": ["sunrise", "sunset", "tzeit"]}),
    ("clock", "minimal", "שעון בלבד", {"show_seconds": True, "zmanim": []}),
    ("zmanim", "default", "רשימת זמני היום + לימוד יומי", {}),
    ("prayers", "default", "זמני תפילות", {}),
    ("lessons", "default", "שיעורים", {}),
    ("prayers_lessons", "default", "תפילות ושיעורים בשני טורים", {}),
    ("announcements", "default", "הודעות — כרטיסים", {"per_page": 2}),
    ("announcements", "single", "הודעה אחת במסך מלא", {"per_page": 1}),
    ("halacha", "default", "הלכה על רקע קלף", {"selection_id": None}),
    ("memorials", "list", "עילוי נשמת — רשימה", {"style": "list", "mode": "both"}),
    ("memorials", "cards", "עילוי נשמת — כרטיסים", {"style": "cards", "mode": "both"}),
    ("memorials", "tree", "עילוי נשמת — לוח זיכרון (עץ)", {"style": "tree", "mode": "both"}),
    ("sponsors", "default", "פרנסים והקדשות", {}),
    ("birthdays", "default", "ימי הולדת", {}),
    ("hilula", "default", "יום הילולה — תבנית אוטומטית (עם/בלי תמונה)", {"image_percent": 38}),
    ("shabbat", "default", "זמני שבת וחג", {}),
    ("combined", "default", "מסך משולב: שעון, תפילות והלכה", {}),
    ("content", "default", "תוכן תורני / סיפורים", {}),
]


def seed_base(db: Session) -> None:
    for key, name, order in PRAYER_TYPES:
        if not db.scalar(select(PrayerType).where(PrayerType.key == key)):
            db.add(PrayerType(key=key, name=name, sort_order=order))
    for t, key, name, cfg in TEMPLATES:
        if not db.scalar(select(ScreenTemplate).where(ScreenTemplate.screen_type == t, ScreenTemplate.key == key)):
            db.add(ScreenTemplate(screen_type=t, key=key, name=name, default_config=cfg))
    s = get_settings_row(db)
    get_profile_row(db, s)
    if not db.scalar(select(func.count()).select_from(Screen)):
        screens = [
            ("שעון", "clock", "default", 20, True, {"show_seconds": True, "zmanim": ["sunrise", "sunset", "tzeit"]}, {}),
            ("זמני היום", "zmanim", "default", 20, True, {}, {}),
            ("תפילות ושיעורים", "prayers_lessons", "default", 25, True, {}, {}),
            ("הודעות", "announcements", "default", 20, True, {"per_page": 2}, {}),
            ("הלכה יומית", "halacha", "default", 25, True, {"selection_id": None}, {}),
            ("יום הילולה", "hilula", "default", 30, True, {"image_percent": 38}, {}),
            ("עילוי נשמת", "memorials", "list", 15, True, {"style": "list", "mode": "both"}, {}),
            ("פרנסים", "sponsors", "default", 15, True, {}, {}),
            ("ימי הולדת", "birthdays", "default", 10, True, {}, {}),
            ("שבת וחג", "shabbat", "default", 20, True, {}, {"days_of_week": [4, 5, 6]}),
            ("מסך משולב", "combined", "default", 25, False, {}, {}),
            ("תוכן תורני", "content", "default", 20, False, {}, {}),
        ]
        for i, (name, typ, tpl, dur, en, cfg, cond) in enumerate(screens):
            db.add(Screen(name=name, type=typ, template_key=tpl, duration_seconds=dur, enabled=en, sort_order=i,
                          config=cfg, conditions={"days_of_week": [], "shabbat_mode": "any", **cond}))
    bump_content_revision(db)
    db.commit()


def create_admin(db: Session, username: str, password: str, display_name: str = "מנהל") -> User:
    validate_password_strength(password)
    u = db.scalar(select(User).where(User.username == username))
    if u:
        u.password_hash = hash_password(password)
        u.role, u.is_active = "admin", True
    else:
        u = User(username=username, display_name=display_name, role="admin", password_hash=hash_password(password))
        db.add(u)
    db.commit()
    return u


def bootstrap_admin_from_env(db: Session) -> None:
    s = get_settings()
    if s.admin_username and s.admin_password and not db.scalar(select(func.count()).select_from(User)):
        create_admin(db, s.admin_username, s.admin_password)


def _placeholder_png() -> bytes:
    """Abstract placeholder portrait (no real person) for previewing the photo layout."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (600, 780), (216, 200, 166))
    d = ImageDraw.Draw(img)
    d.ellipse((190, 170, 410, 390), fill=(146, 125, 100))
    d.pieslice((90, 430, 510, 900), 180, 360, fill=(38, 61, 75))
    d.rectangle((0, 700, 600, 780), fill=(24, 41, 58))
    return _to_png(img)


def _to_png(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def seed_demo(db: Session) -> None:
    """Demo content — every name/text says it is a sample. Never presented as real halacha/history."""
    if db.scalar(select(HalachaSource).where(HalachaSource.is_sample.is_(True))):
        return
    s = get_settings_row(db)
    tz = ZoneInfo(s.timezone)
    today = datetime.now(tz).date()
    if not s.footer_text:
        s.footer_text = "ברוכים הבאים — לוח דוגמה (יש לעדכן בהגדרות)"
    types = {t.key: t for t in db.scalars(select(PrayerType))}
    P = PrayerSchedule
    db.add_all([
        P(prayer_type_id=types["shacharit"].id, name="שחרית מניין א׳", day_kind="weekday", time_mode="fixed",
          fixed_time=time(6, 15), sort_order=1),
        P(prayer_type_id=types["shacharit"].id, name="שחרית מניין ב׳", day_kind="sun_thu", time_mode="fixed",
          fixed_time=time(7, 30), sort_order=2),
        P(prayer_type_id=types["shacharit"].id, name="שחרית ראש חודש", day_kind="rosh_chodesh", replaces_regular=False,
          time_mode="fixed", fixed_time=time(6, 0), sort_order=3),
        P(prayer_type_id=types["shacharit"].id, name="שחרית שבת", day_kind="shabbat", time_mode="fixed",
          fixed_time=time(8, 0)),
        P(prayer_type_id=types["mincha"].id, name="מנחה", day_kind="sun_thu", time_mode="relative", relative_zman="sunset",
          offset_minutes=-15, rounding="down5"),
        P(prayer_type_id=types["mincha"].id, name="מנחה ערב שבת", day_kind="friday", time_mode="relative",
          relative_zman="candle_lighting", offset_minutes=10, rounding="none"),
        P(prayer_type_id=types["mincha"].id, name="מנחה שבת", day_kind="shabbat", time_mode="relative",
          relative_zman="sunset", offset_minutes=-40, rounding="down5"),
        P(prayer_type_id=types["arvit"].id, name="ערבית", day_kind="sun_thu", time_mode="relative", relative_zman="tzeit",
          offset_minutes=0, rounding="up5"),
        P(prayer_type_id=types["arvit"].id, name="ערבית מוצאי שבת", day_kind="shabbat", time_mode="relative",
          relative_zman="shabbat_end", offset_minutes=0),
    ])
    les = Lesson(title="שיעור דף יומי (דוגמה)", teacher="מגיד השיעור (דוגמה)", location="בית המדרש")
    les.schedules = [LessonSchedule(day_kind="sun_thu", time_mode="fixed", fixed_time=time(20, 30), duration_minutes=60)]
    les2 = Lesson(title="שיעור בין מנחה לערבית (דוגמה)", teacher="מגיד השיעור (דוגמה)")
    les2.schedules = [LessonSchedule(day_kind="sun_thu", time_mode="relative", relative_zman="sunset", offset_minutes=0,
                                     duration_minutes=20)]
    db.add_all([les, les2])

    src = HalachaSource(title="מאגר דוגמה — יש להחליף בתוכן מורשה", author="—",
                        license="דוגמה בלבד — אינו תוכן הלכתי מוסמך", is_sample=True,
                        attribution="טקסט הדגמה של המערכת. ייבאו הלכות ממקור בעל רישיון מתאים דרך מסך ההלכות.")
    cat = db.scalar(select(HalachaCategory).where(HalachaCategory.name == "דוגמה")) or HalachaCategory(name="דוגמה")
    db.add_all([src, cat])
    db.flush()
    for i in range(1, 6):
        db.add(Halacha(source_id=src.id, category_id=cat.id, title=f"הלכה לדוגמה {i}", sort_order=i,
                       text=("זהו טקסט הדגמה בלבד, שנועד להציג את עיצוב מסך ההלכה היומית. "
                             "אין זו הלכה ואין לנהוג על פיה. כדי להציג הלכות אמיתיות יש לייבא מאגר "
                             "ממקור מורשה (קובץ JSON או CSV) בממשק הניהול, תחת 'הלכות'."),
                       source_ref="מאגר דוגמה"))
    db.add(HalachaSelection(name="הלכה יומית", mode="sequential", per_day=2, start_date=today))

    db.add(Announcement(title="ברוכים הבאים ללוח הדיגיטלי (דוגמה)", priority=5,
                        body_html="<p>זוהי הודעת דוגמה. ניתן לערוך, לשכפל ולמחוק הודעות בממשק הניהול.</p>"
                                  "<p><span class=\"c-gold\">הודעות עם תאריך סיום</span> יוסתרו אוטומטית בזמן.</p>"))
    db.add(Announcement(title="הודעה נוספת (דוגמה)", body_html="<p>הודעה זו מוסתרת בשבת ובחג.</p>", hide_on_shabbat=True))

    h_today = H.to_hebrew(today)
    h_tom = H.to_hebrew(today + timedelta(days=1))
    db.add_all([
        Memorial(full_name="פלוני (דוגמה)", parent_name="אלמוני", gender="m", hebrew_day=h_today.day,
                 hebrew_month=h_today.month, hebrew_year=h_today.year - 10),
        Memorial(full_name="פלונית (דוגמה)", parent_name="אלמונית", gender="f", hebrew_day=h_tom.day,
                 hebrew_month=h_tom.month),
        Sponsorship(sponsor_name="משפחת דוגמה", dedication_type="iluy_nishmat", honoree_name="פלוני בן אלמוני (דוגמה)",
                    period="week", start_date=today - timedelta(days=1)),
        Sponsorship(dedication_type="hatzlacha", honoree_name="כל המתפללים (דוגמה)", period="month",
                    start_date=today - timedelta(days=3)),
        Birthday(name="ישראל ישראלי (דוגמה)", hebrew_day=h_today.day, hebrew_month=h_today.month, message="מזל טוב!"),
    ])

    # sample tzadikim: one WITH a placeholder image (layout A), one WITHOUT (layout B)
    png = _placeholder_png()
    key = f"{uuid.uuid4().hex}.png"
    import hashlib
    asset = MediaAsset(data=png, original_filename="placeholder-portrait.png", mime_type="image/png", size_bytes=len(png),
                       width=600, height=780, sha256=hashlib.sha256(png).hexdigest(), storage_key=key,
                       alt_text="איור דוגמה — לא תמונת צדיק", license="נוצר על ידי המערכת")
    db.add(asset)
    db.flush()
    sample_bio = ("כאן יוצג תיאור קצר ומאומת של תולדות חייו של הצדיק, פועלו ותרומתו ללימוד התורה ולעם ישראל. "
                  "זהו טקסט דוגמה בלבד — יש להזין תוכן ממקור מאומת בממשק הניהול, תחת 'ימי הילולה'.")
    sample_teaching = "כאן יוצג קטע לימוד מתורת הצדיק, מתוך מקור מאומת ובעל הרשאת שימוש מתאימה (טקסט דוגמה)."
    t1 = Tzadik(display_name="צדיק לדוגמה א׳", honorific="רבי", biography=sample_bio, teaching_title="מתורתו",
                teaching_text=sample_teaching, teaching_source="מקור לדוגמה", image_asset_id=asset.id,
                image_alt="איור דוגמה", image_attribution="איור שנוצר על ידי המערכת", burial_place="מקום לדוגמה", sort_order=1)
    # two dates (today + tomorrow) so the sample hilula screen shows both before and after sunset
    t1.dates = [HilulaDate(hebrew_month=h_today.month, hebrew_day=h_today.day),
                HilulaDate(hebrew_month=h_tom.month, hebrew_day=h_tom.day)]
    t2 = Tzadik(display_name="צדיק לדוגמה ב׳", honorific="הרב", biography=sample_bio, teaching_title="מתורתו",
                teaching_text=sample_teaching, teaching_source="מקור לדוגמה", sort_order=2)
    t2.dates = [HilulaDate(hebrew_month=h_today.month, hebrew_day=h_today.day)]
    t3 = Tzadik(display_name="צדיק לדוגמה ג׳", biography=sample_bio, teaching_text=sample_teaching, sort_order=3)
    in3 = H.to_hebrew(today + timedelta(days=3))
    t3.dates = [HilulaDate(hebrew_month=in3.month, hebrew_day=in3.day)]
    db.add_all([t1, t2, t3])
    bump_content_revision(db)
    db.commit()
