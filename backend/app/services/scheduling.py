"""Prayer/lesson time rules, Hebrew anniversaries (hilula / yahrzeit / birthdays) and the
halacha rotation planner. Pure functions — unit tested in tests/test_engine.py."""
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Iterable

from . import hebrew as H
from .calendar_engine import round_time

REGULAR_KINDS = {"daily", "weekday", "sun_thu", "friday", "shabbat", "custom"}


def rule_matches(rule, d: date, flags: dict) -> bool:
    if rule.valid_from and d < rule.valid_from:
        return False
    if rule.valid_to and d > rule.valid_to:
        return False
    wd = flags["weekday"]
    yt = flags["is_yom_tov"]
    k = rule.day_kind
    if k == "daily":
        return True
    if k == "weekday":
        return wd <= 5 and not yt
    if k == "sun_thu":
        return wd <= 4 and not yt
    if k == "friday":
        return wd == 5 and not yt
    if k == "shabbat":
        return wd == 6
    if k == "custom":
        return wd in (rule.days_of_week or []) and (not yt or wd == 6)
    if k == "rosh_chodesh":
        return flags["is_rosh_chodesh"]
    if k == "yom_tov":
        return yt
    if k == "erev_yom_tov":
        return flags["is_erev_yom_tov"]
    if k == "chol_hamoed":
        return flags["is_chol_hamoed"]
    if k == "fast_day":
        return flags["is_fast"]
    if k == "chanukah":
        return flags["is_chanukah"]
    return False


def compute_time(rule, d: date, zmanim: dict, tz) -> datetime | None:
    """Return the local datetime for a rule on date d, or None when it cannot be computed
    (e.g. relative to candle lighting on a weekday). Never invents a time."""
    if rule.time_mode == "fixed":
        if rule.fixed_time is None:
            return None
        return datetime.combine(d, rule.fixed_time, tzinfo=tz)
    anchor = zmanim.get(rule.relative_zman)
    if anchor is None:
        return None
    return round_time(anchor + timedelta(minutes=rule.offset_minutes or 0), rule.rounding or "none")


def exception_for(rule, d: date):
    for e in getattr(rule, "exceptions", []) or []:
        if e.date == d:
            return e
    return None


def schedule_items(rules: Iterable, d: date, flags: dict, zmanim: dict, tz, group_key) -> list[dict]:
    """Evaluate a set of rules for a day. `group_key(rule)` returns the group (e.g. prayer type)
    in which special-day rules marked replaces_regular suppress the regular ones."""
    matching = [r for r in rules if rule_matches(r, d, flags)]
    replaced_groups = {group_key(r) for r in matching if r.day_kind not in REGULAR_KINDS and r.replaces_regular}
    out = []
    for r in matching:
        if r.day_kind in REGULAR_KINDS and group_key(r) in replaced_groups:
            continue
        exc = exception_for(r, d)
        if exc and exc.action == "cancel":
            continue
        if exc and exc.action == "override" and exc.override_time:
            t = datetime.combine(d, exc.override_time, tzinfo=tz)
        else:
            t = compute_time(r, d, zmanim, tz)
        if t is None:
            continue
        out.append({"rule": r, "time": t, "note": exc.note if exc else None})
    out.sort(key=lambda x: x["time"])
    return out


# ---------------------------------------------------------------- anniversaries
def anniversaries_by_date(records: Iterable, start: date, end: date, day30_policy: str,
                          get=lambda r: (r.hebrew_month, r.hebrew_day, r.leap_year_policy)) -> dict[date, list]:
    """Map civil date -> records whose Hebrew anniversary falls on that (daytime) civil date."""
    out: dict[date, list] = defaultdict(list)
    years = range(H.to_hebrew(start).year - 1, H.to_hebrew(end).year + 2)
    for r in records:
        month, day, policy = get(r)
        for y in years:
            for (m, dd) in H.anniversary_dates(month, day, policy, y, day30_policy):
                g = H.hebrew_to_greg(y, m, dd)
                if start <= g <= end:
                    out[g].append(r)
    return out


# ---------------------------------------------------------------- halacha rotation
def plan_halachot(items: list, mode: str, per_day: int, seed: int, start_date: date, d: date) -> list:
    """Deterministic plan: the server and an offline TV agree on the halachot of any date.
    sequential: continues through the ordered corpus; random: a fresh shuffle per full cycle,
    so no halacha repeats until every item has been shown."""
    n = len(items)
    if n == 0:
        return []
    k = (d - start_date).days
    out = []
    for i in range(min(per_day, n)):
        pos = k * per_day + i
        if mode == "random":
            cycle, idx = divmod(pos, n)
            perm = list(items)
            random.Random(seed * 1_000_003 + cycle).shuffle(perm)
            out.append(perm[idx])
        else:
            out.append(items[pos % n])
    return out


def sponsorship_end(start: date, period: str, end: date | None) -> date:
    if end:
        return end
    return start + timedelta(days={"day": 0, "week": 6, "month": 29, "year": 364}.get(period, 6))


def to_time(s: str | None) -> time | None:
    if not s:
        return None
    h, m = s.split(":")[:2]
    return time(int(h), int(m))
