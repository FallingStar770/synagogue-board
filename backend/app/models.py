"""SQLAlchemy 2 models — full schema for a single synagogue.

All timestamps are stored as TIMESTAMPTZ (UTC). Hebrew dates are stored structurally
(month number + day [+ year]) and never only as display strings.

Hebrew month numbering used everywhere in this project (same as pyluach):
  1=ניסן 2=אייר 3=סיון 4=תמוז 5=אב 6=אלול 7=תשרי 8=חשון 9=כסלו 10=טבת 11=שבט
  12=אדר (בשנה פשוטה) / אדר א׳ (בשנה מעוברת)   13=אדר ב׳
"""
import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    JSON,
    BigInteger,
    LargeBinary,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ---------------------------------------------------------------- users & security
class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = uuid_pk()
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("role in ('admin','editor')", name="ck_users_role"),)


class UserSession(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    user: Mapped[User] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    username: Mapped[str | None] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    entity: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict | None] = mapped_column(JSONType)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


# ---------------------------------------------------------------- media
class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[uuid.UUID] = uuid_pk()
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(60), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # image bytes live in PostgreSQL: no persistent disk needed (Render / PaaS), included in pg_dump backups
    data: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    alt_text: Mapped[str | None] = mapped_column(Text)
    attribution: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- settings
class HalachicCalculationProfile(TimestampMixin, Base):
    __tablename__ = "halachic_calculation_profiles"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # every value below is an explicit, changeable choice — not an assumed halachic ruling
    alos_method: Mapped[str] = mapped_column(String(20), nullable=False, default="72min")  # 72min|90min|16.1deg|19.8deg
    misheyakir_degrees: Mapped[float] = mapped_column(Float, nullable=False, default=11.5)
    tzeit_method: Mapped[str] = mapped_column(String(30), nullable=False, default="8.5deg")  # 8.5deg|13.5min_zmaniyot|18min|20min|7.083deg
    candle_lighting_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    shabbat_end_method: Mapped[str] = mapped_column(String(30), nullable=False, default="tzeit")  # tzeit|minutes_after_sunset
    shabbat_end_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    rabbeinu_tam_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=72)
    rabbeinu_tam_zmaniyot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_elevation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled_zmanim: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    engine_version: Mapped[str] = mapped_column(String(60), nullable=False, default="")


class SynagogueSettings(TimestampMixin, Base):
    __tablename__ = "synagogue_settings"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="בית הכנסת")
    logo_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"))
    address: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float, nullable=False, default=31.778)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, default=35.235)
    elevation_m: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    timezone: Mapped[str] = mapped_column(String(60), nullable=False, default="Asia/Jerusalem")
    in_israel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    walled_city_purim: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    nusach: Mapped[str] = mapped_column(String(30), nullable=False, default="sefardi")
    calculation_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("halachic_calculation_profiles.id", ondelete="SET NULL")
    )
    day_change: Mapped[str] = mapped_column(String(20), nullable=False, default="sunset")  # sunset|midnight
    day30_policy: Mapped[str] = mapped_column(String(20), nullable=False, default="last_day")  # last_day|next_day
    show_national_holidays: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    prayer_additions: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    reminders: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    daily_learning: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    footer_text: Mapped[str | None] = mapped_column(Text)
    theme: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    __table_args__ = (
        CheckConstraint("day_change in ('sunset','midnight')", name="ck_settings_day_change"),
        CheckConstraint("latitude between -90 and 90 and longitude between -180 and 180", name="ck_settings_coords"),
    )


# ---------------------------------------------------------------- screens
SCREEN_TYPES = (
    "clock", "zmanim", "prayers", "lessons", "prayers_lessons", "announcements", "halacha",
    "memorials", "sponsors", "birthdays", "hilula", "shabbat", "combined", "content",
)


class ScreenTemplate(Base):
    __tablename__ = "screen_templates"
    id: Mapped[uuid.UUID] = uuid_pk()
    screen_type: Mapped[str] = mapped_column(String(30), nullable=False)
    key: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_config: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    __table_args__ = (UniqueConstraint("screen_type", "key", name="uq_screen_template"),)


class Screen(TimestampMixin, Base):
    __tablename__ = "screens"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    template_key: Mapped[str] = mapped_column(String(40), nullable=False, default="default")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    config: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    # display conditions: days_of_week[0=Sun..6=Sat], shabbat_mode(any|only|hide), time_from, time_to, date_from, date_to
    conditions: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    fallback: Mapped[str] = mapped_column(String(20), nullable=False, default="skip")  # skip|message
    fallback_text: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("duration_seconds between 3 and 3600", name="ck_screens_duration"),
        CheckConstraint("fallback in ('skip','message')", name="ck_screens_fallback"),
        Index("ix_screens_order", "sort_order"),
    )


class ScreenContentLink(Base):
    """Optional assignment of content to specific screens. Content with no links appears on
    every screen of the matching type."""
    __tablename__ = "screen_content_links"
    id: Mapped[uuid.UUID] = uuid_pk()
    screen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("screens.id", ondelete="CASCADE"), nullable=False)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("screen_id", "content_type", "content_id", name="uq_screen_content"),
        Index("ix_screen_content_lookup", "content_type", "content_id"),
    )


# ---------------------------------------------------------------- announcements
class Announcement(TimestampMixin, Base):
    __tablename__ = "announcements"
    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"))
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    hide_on_shabbat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    __table_args__ = (CheckConstraint("end_at is null or start_at is null or end_at > start_at", name="ck_ann_dates"),)


class AnnouncementScreen(Base):
    __tablename__ = "announcement_screens"
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"), primary_key=True
    )
    screen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("screens.id", ondelete="CASCADE"), primary_key=True)


# ---------------------------------------------------------------- prayers & lessons
DAY_KINDS = (
    "daily", "weekday", "sun_thu", "friday", "shabbat", "custom", "rosh_chodesh", "yom_tov",
    "erev_yom_tov", "chol_hamoed", "fast_day", "chanukah",
)


class ScheduleRuleMixin:
    day_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    days_of_week: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)  # for custom (0=Sun)
    replaces_regular: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    time_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="fixed")  # fixed|relative
    fixed_time: Mapped[time | None] = mapped_column(Time)
    relative_zman: Mapped[str | None] = mapped_column(String(40))
    offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rounding: Mapped[str] = mapped_column(String(10), nullable=False, default="none")  # none|down5|up5|near5
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)


class PrayerType(Base):
    __tablename__ = "prayer_types"
    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PrayerSchedule(TimestampMixin, ScheduleRuleMixin, Base):
    __tablename__ = "prayer_schedules"
    id: Mapped[uuid.UUID] = uuid_pk()
    prayer_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prayer_types.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prayer_type: Mapped[PrayerType] = relationship()
    exceptions: Mapped[list["PrayerScheduleException"]] = relationship(
        cascade="all, delete-orphan", order_by="PrayerScheduleException.date"
    )
    __table_args__ = (
        CheckConstraint("time_mode in ('fixed','relative')", name="ck_prayer_time_mode"),
        CheckConstraint(
            "(time_mode='fixed' and fixed_time is not null) or (time_mode='relative' and relative_zman is not null)",
            name="ck_prayer_time_value",
        ),
    )


class PrayerScheduleException(Base):
    __tablename__ = "prayer_schedule_exceptions"
    id: Mapped[uuid.UUID] = uuid_pk()
    schedule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prayer_schedules.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False, default="cancel")  # cancel|override
    override_time: Mapped[time | None] = mapped_column(Time)
    note: Mapped[str | None] = mapped_column(String(200))
    __table_args__ = (UniqueConstraint("schedule_id", "date", name="uq_prayer_exc"),)


class Lesson(TimestampMixin, Base):
    __tablename__ = "lessons"
    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    teacher: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schedules: Mapped[list["LessonSchedule"]] = relationship(cascade="all, delete-orphan")


class LessonSchedule(ScheduleRuleMixin, Base):
    __tablename__ = "lesson_schedules"
    id: Mapped[uuid.UUID] = uuid_pk()
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    exceptions: Mapped[list["LessonScheduleException"]] = relationship(cascade="all, delete-orphan")


class LessonScheduleException(Base):
    __tablename__ = "lesson_schedule_exceptions"
    id: Mapped[uuid.UUID] = uuid_pk()
    schedule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson_schedules.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False, default="cancel")
    override_time: Mapped[time | None] = mapped_column(Time)
    note: Mapped[str | None] = mapped_column(String(200))
    __table_args__ = (UniqueConstraint("schedule_id", "date", name="uq_lesson_exc"),)


# ---------------------------------------------------------------- halachot
class HalachaSource(TimestampMixin, Base):
    __tablename__ = "halacha_sources"
    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    author: Mapped[str | None] = mapped_column(String(200))
    license: Mapped[str] = mapped_column(String(200), nullable=False)  # required — no unlicensed corpus
    attribution: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(400))
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class HalachaCategory(Base):
    __tablename__ = "halacha_categories"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class HalachaChapter(Base):
    __tablename__ = "halacha_chapters"
    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("halacha_sources.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("halacha_categories.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Halacha(TimestampMixin, Base):
    __tablename__ = "halachot"
    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("halacha_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("halacha_chapters.id", ondelete="SET NULL"), index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("halacha_categories.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[HalachaSource] = relationship()


class HalachaTag(Base):
    __tablename__ = "halacha_tags"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)


class HalachaTagLink(Base):
    __tablename__ = "halacha_tag_links"
    halacha_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("halachot.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("halacha_tags.id", ondelete="CASCADE"), primary_key=True)


class HalachaSelection(TimestampMixin, Base):
    __tablename__ = "halacha_selections"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str] = mapped_column(String(12), nullable=False, default="sequential")  # sequential|random
    source_ids: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    category_ids: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    chapter_ids: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    halacha_ids: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    tag_ids: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint("per_day between 1 and 20", name="ck_halacha_per_day"),)


class HalachaDisplayHistory(Base):
    __tablename__ = "halacha_display_history"
    id: Mapped[uuid.UUID] = uuid_pk()
    selection_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("halacha_selections.id", ondelete="SET NULL"))
    halacha_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("halachot.id", ondelete="CASCADE"), nullable=False)
    shown_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    __table_args__ = (UniqueConstraint("selection_id", "halacha_id", "shown_on", name="uq_halacha_hist"),)


# ---------------------------------------------------------------- people content
class Memorial(TimestampMixin, Base):
    __tablename__ = "memorials"
    id: Mapped[uuid.UUID] = uuid_pk()
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    parent_name: Mapped[str | None] = mapped_column(String(160))
    gender: Mapped[str] = mapped_column(String(1), nullable=False, default="m")  # m|f
    hebrew_day: Mapped[int] = mapped_column(Integer, nullable=False)
    hebrew_month: Mapped[int] = mapped_column(Integer, nullable=False)
    hebrew_year: Mapped[int | None] = mapped_column(Integer)
    gregorian_date: Mapped[date | None] = mapped_column(Date)
    leap_year_policy: Mapped[str] = mapped_column(String(12), nullable=False, default="adar_ii")
    notes: Mapped[str | None] = mapped_column(Text)
    permanent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_days_before: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        CheckConstraint("hebrew_month between 1 and 13 and hebrew_day between 1 and 30", name="ck_memorial_date"),
        CheckConstraint("leap_year_policy in ('adar_i','adar_ii','both')", name="ck_memorial_leap"),
    )


class Sponsorship(TimestampMixin, Base):
    __tablename__ = "sponsorships"
    id: Mapped[uuid.UUID] = uuid_pk()
    sponsor_name: Mapped[str | None] = mapped_column(String(160))
    dedication_type: Mapped[str] = mapped_column(String(20), nullable=False, default="custom")
    honoree_name: Mapped[str | None] = mapped_column(String(200))
    text: Mapped[str | None] = mapped_column(Text)
    period: Mapped[str] = mapped_column(String(10), nullable=False, default="week")  # day|week|month|year
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    show_in_footer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint("end_date is null or end_date >= start_date", name="ck_sponsor_dates"),)


class Birthday(TimestampMixin, Base):
    __tablename__ = "birthdays"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    hebrew_day: Mapped[int] = mapped_column(Integer, nullable=False)
    hebrew_month: Mapped[int] = mapped_column(Integer, nullable=False)
    gregorian_date: Mapped[date | None] = mapped_column(Date)
    message: Mapped[str | None] = mapped_column(String(300))
    leap_year_policy: Mapped[str] = mapped_column(String(12), nullable=False, default="adar_ii")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint("hebrew_month between 1 and 13 and hebrew_day between 1 and 30", name="ck_bday_date"),)


class ReligiousContent(TimestampMixin, Base):
    __tablename__ = "religious_content"
    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="story")  # story|dvar_torah|parsha|other
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(300))
    license: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Tzadik(TimestampMixin, Base):
    __tablename__ = "tzadikim"
    id: Mapped[uuid.UUID] = uuid_pk()
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    honorific: Mapped[str | None] = mapped_column(Text)
    biography: Mapped[str] = mapped_column(Text, nullable=False)
    teaching_title: Mapped[str | None] = mapped_column(Text)
    teaching_text: Mapped[str] = mapped_column(Text, nullable=False)
    teaching_source: Mapped[str | None] = mapped_column(Text)
    image_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"))
    image_alt: Mapped[str | None] = mapped_column(Text)
    image_attribution: Mapped[str | None] = mapped_column(Text)
    burial_place: Mapped[str | None] = mapped_column(Text)
    death_hebrew_year: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dates: Mapped[list["HilulaDate"]] = relationship(cascade="all, delete-orphan", back_populates="tzadik")


class HilulaDate(Base):
    __tablename__ = "hilula_dates"
    id: Mapped[uuid.UUID] = uuid_pk()
    tzadik_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tzadikim.id", ondelete="CASCADE"), nullable=False, index=True)
    hebrew_month: Mapped[int] = mapped_column(Integer, nullable=False)
    hebrew_day: Mapped[int] = mapped_column(Integer, nullable=False)
    leap_year_policy: Mapped[str] = mapped_column(Text, nullable=False, default="adar_ii")
    display_start_offset_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    display_end_offset_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tzadik: Mapped[Tzadik] = relationship(back_populates="dates")
    __table_args__ = (
        CheckConstraint("hebrew_month between 1 and 13 and hebrew_day between 1 and 30", name="ck_hilula_date"),
        CheckConstraint("leap_year_policy in ('adar_i','adar_ii','both')", name="ck_hilula_leap"),
        CheckConstraint("display_start_offset_days between 0 and 30 and display_end_offset_days between 0 and 30",
                        name="ck_hilula_offsets"),
        Index("ix_hilula_month_day", "hebrew_month", "hebrew_day"),
    )


# ---------------------------------------------------------------- display
class ZmanimDailyCache(Base):
    __tablename__ = "zmanim_daily_cache"
    id: Mapped[uuid.UUID] = uuid_pk()
    date: Mapped[date] = mapped_column(Date, nullable=False)
    profile_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(60), nullable=False)
    data: Mapped[dict] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("date", "profile_hash", name="uq_zmanim_cache"),)


class DisplayDevice(TimestampMixin, Base):
    __tablename__ = "display_devices"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    token_hint: Mapped[str] = mapped_column(String(8), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ip: Mapped[str | None] = mapped_column(String(64))
    last_snapshot_version: Mapped[int | None] = mapped_column(Integer)
    last_status: Mapped[dict | None] = mapped_column(JSONType)


class DisplaySnapshot(Base):
    __tablename__ = "display_snapshots"
    id: Mapped[uuid.UUID] = uuid_pk()
    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppState(Base):
    """Small key/value table (e.g. content revision counter that invalidates the snapshot)."""
    __tablename__ = "app_state"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
