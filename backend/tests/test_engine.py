"""Unit tests for the halachic calendar engine, scheduling rules and rotation (no DB)."""
from datetime import date, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.services import hebrew as H
from app.services.calendar_engine import CalcProfile, DayCalculator, round_time
from app.services.scheduling import anniversaries_by_date, compute_time, plan_halachot, rule_matches, schedule_items

TZ = ZoneInfo("Asia/Jerusalem")
JLM = CalcProfile(prayer_additions=["geshem", "tachanun", "hallel", "yaale_veyavo", "al_hanisim", "omer_long"],
                  reminders=["dst", "eruv_tavshilin", "bedikat_chametz"], daily_learning=["daf_bavli"],
                  enabled_zmanim=[])


def test_gematria():
    assert H.gematria(5) == "ה׳"
    assert H.gematria(15) == "ט״ו"
    assert H.gematria(16) == "ט״ז"
    assert H.gematria(58) == "נ״ח"
    assert H.gematria(787) == "תשפ״ז"


def test_hebrew_date_matches_reference_screenshot():
    # reference image: "ליל שני-ה' כסלו התשפ"ז" with parashat Vayetze, 15.11.2026
    h = H.hebrew_info(date(2026, 11, 15))
    assert h["str"] == "ה׳ כסלו התשפ״ז"
    assert H.parsha_for_week(date(2026, 11, 15), True) == "ויצא"


def test_adar_policies():
    # 5787 is a leap year? check both kinds explicitly
    leap_year = next(y for y in range(5784, 5800) if H.is_leap(y))
    plain_year = next(y for y in range(5784, 5800) if not H.is_leap(y))
    assert H.anniversary_dates(12, 7, "adar_ii", leap_year) == [(13, 7)]
    assert H.anniversary_dates(12, 7, "adar_i", leap_year) == [(12, 7)]
    assert H.anniversary_dates(12, 7, "both", leap_year) == [(12, 7), (13, 7)]
    assert H.anniversary_dates(12, 7, "both", plain_year) == [(12, 7)]
    assert H.anniversary_dates(13, 7, "adar_ii", plain_year) == [(12, 7)]


def test_day30_policy():
    # find a year with a 29-day Cheshvan
    y = next(y for y in range(5780, 5800) if H.days_in_month(y, 8) == 29)
    assert H.anniversary_dates(8, 30, "adar_ii", y, "last_day") == [(8, 29)]
    assert H.anniversary_dates(8, 30, "adar_ii", y, "next_day") == [(9, 1)]


def test_zmanim_order_and_dst():
    c = DayCalculator(JLM)
    for d in (date(2026, 11, 15), date(2027, 6, 21), date(2027, 3, 26)):
        z = c.zmanim(d)
        order = ["alot", "misheyakir", "sunrise", "shma_mga", "shma_gra", "tfila_gra", "chatzot", "mincha_gedola",
                 "mincha_ketana", "plag", "sunset", "tzeit", "tzeit_rt"]
        times = [z[k] for k in order]
        assert times == sorted(times), d
        assert z["sunrise"].utcoffset() in (timedelta(hours=2), timedelta(hours=3))
    # Israel DST 2027 starts Friday March 26: local sunrise jumps by ~1 hour
    before, after = c.zmanim(date(2027, 3, 25))["sunrise"], c.zmanim(date(2027, 3, 26))["sunrise"]
    diff = (after.hour * 60 + after.minute) - (before.hour * 60 + before.minute)
    assert 55 <= diff <= 60


def test_jerusalem_sample_values_within_tolerance():
    """Sanity check against independently published Jerusalem times (sea level, Nov 15 2026):
    sunrise ≈ 06:08, sunset ≈ 16:39 (±2 minutes)."""
    z = DayCalculator(JLM).zmanim(date(2026, 11, 15))
    assert abs((z["sunrise"].hour * 60 + z["sunrise"].minute) - (6 * 60 + 8)) <= 2
    assert abs((z["sunset"].hour * 60 + z["sunset"].minute) - (16 * 60 + 39)) <= 2


def test_candle_lighting_and_havdala_only_when_relevant():
    c = DayCalculator(JLM)
    fri, sat, sun = date(2026, 11, 20), date(2026, 11, 21), date(2026, 11, 22)
    assert "candle_lighting" in c.zmanim(fri) and "shabbat_end" not in c.zmanim(fri)
    assert "shabbat_end" in c.zmanim(sat) and "candle_lighting" not in c.zmanim(sat)
    assert "candle_lighting" not in c.zmanim(sun) and "shabbat_end" not in c.zmanim(sun)
    z = c.zmanim(fri)
    assert (z["sunset"] - z["candle_lighting"]).total_seconds() // 60 in (19, 20, 21)


def test_additions():
    c = DayCalculator(JLM)
    assert "הלל שלם" in c.additions(date(2026, 12, 6))  # Chanukah
    assert "על הניסים" in c.additions(date(2026, 12, 6))
    assert "משיב הרוח ומוריד הגשם" in c.additions(date(2026, 11, 15))
    assert "מוריד הטל" in c.additions(date(2027, 6, 1))
    assert any("ספירת העומר" in a for a in c.additions(date(2027, 4, 22)))


def test_rounding():
    from datetime import datetime
    t = datetime(2026, 1, 1, 16, 37, 30, tzinfo=TZ)
    assert round_time(t, "down5").strftime("%H:%M") == "16:35"
    assert round_time(t, "up5").strftime("%H:%M") == "16:40"
    assert round_time(t, "near5").strftime("%H:%M") == "16:40"
    assert round_time(t, "none").strftime("%H:%M") == "16:37"


def _rule(**kw):
    base = dict(valid_from=None, valid_to=None, day_kind="daily", days_of_week=[], time_mode="fixed",
                fixed_time=time(7, 0), relative_zman=None, offset_minutes=0, rounding="none", replaces_regular=False,
                exceptions=[], group="g")
    base.update(kw)
    return SimpleNamespace(**base)


def test_rules_special_days_replace_regular():
    c = DayCalculator(JLM)
    rc = date(2026, 11, 10)  # Rosh Chodesh Kislev 5787 (1 Kislev)
    assert c.flags(rc)["is_rosh_chodesh"]
    regular = _rule(day_kind="weekday", fixed_time=time(6, 30))
    special = _rule(day_kind="rosh_chodesh", fixed_time=time(6, 0), replaces_regular=True)
    z = c.zmanim(rc)
    items = schedule_items([regular, special], rc, c.flags(rc), z, TZ, group_key=lambda r: r.group)
    assert [i["time"].strftime("%H:%M") for i in items] == ["06:00"]
    normal_day = date(2026, 11, 16)
    items = schedule_items([regular, special], normal_day, c.flags(normal_day), c.zmanim(normal_day), TZ,
                           group_key=lambda r: r.group)
    assert [i["time"].strftime("%H:%M") for i in items] == ["06:30"]


def test_relative_time_and_missing_anchor_never_invented():
    c = DayCalculator(JLM)
    d = date(2026, 11, 16)  # Monday: no candle lighting
    z = c.zmanim(d)
    r = _rule(time_mode="relative", relative_zman="sunset", offset_minutes=-15, rounding="down5")
    t = compute_time(r, d, z, TZ)
    assert t.minute % 5 == 0 and t < z["sunset"]
    assert compute_time(_rule(time_mode="relative", relative_zman="candle_lighting"), d, z, TZ) is None


def test_exceptions():
    d = date(2026, 11, 16)
    c = DayCalculator(JLM)
    cancel = _rule(exceptions=[SimpleNamespace(date=d, action="cancel", override_time=None, note=None)])
    over = _rule(exceptions=[SimpleNamespace(date=d, action="override", override_time=time(9, 0), note="חריג")])
    items = schedule_items([cancel, over], d, c.flags(d), c.zmanim(d), TZ, group_key=lambda r: id(r))
    assert len(items) == 1 and items[0]["time"].strftime("%H:%M") == "09:00" and items[0]["note"] == "חריג"


def test_custom_days_and_shabbat():
    c = DayCalculator(JLM)
    r = _rule(day_kind="custom", days_of_week=[1, 4])  # Mon, Thu
    assert rule_matches(r, date(2026, 11, 16), c.flags(date(2026, 11, 16)))
    assert not rule_matches(r, date(2026, 11, 17), c.flags(date(2026, 11, 17)))
    assert rule_matches(_rule(day_kind="shabbat"), date(2026, 11, 21), c.flags(date(2026, 11, 21)))


def test_halacha_rotation_no_repeats_until_exhausted():
    items = list(range(10))
    start = date(2026, 1, 1)
    seen = []
    for i in range(5):  # 5 days x 2 per day = full cycle
        seen += plan_halachot(items, "random", 2, 7, start, start + timedelta(days=i))
    assert sorted(seen) == items
    seq = [plan_halachot(items, "sequential", 3, 1, start, start + timedelta(days=i)) for i in range(4)]
    assert seq[0] == [0, 1, 2] and seq[1] == [3, 4, 5] and seq[3] == [9, 0, 1]
    # deterministic (server and offline TV agree)
    assert plan_halachot(items, "random", 2, 7, start, date(2026, 3, 3)) == plan_halachot(items, "random", 2, 7, start, date(2026, 3, 3))


def test_anniversaries_by_date_maps_to_civil_dates():
    rec = SimpleNamespace(hebrew_month=9, hebrew_day=25, leap_year_policy="adar_ii")  # 25 Kislev
    m = anniversaries_by_date([rec], date(2026, 11, 1), date(2027, 1, 31), "last_day")
    assert date(2026, 12, 5) in m  # first day of Chanukah 5787
