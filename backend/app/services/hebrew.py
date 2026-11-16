"""Hebrew calendar helpers built on pyluach (MIT) and python-zmanim (LGPL-2.1).

Month numbering (pyluach): 1=ניסן … 6=אלול, 7=תשרי … 12=אדר/אדר א׳, 13=אדר ב׳.
"""
from datetime import date

from pyluach import dates as pdates
from pyluach import hebrewcal

MONTH_NAMES = {
    1: "ניסן", 2: "אייר", 3: "סיון", 4: "תמוז", 5: "אב", 6: "אלול", 7: "תשרי",
    8: "חשון", 9: "כסלו", 10: "טבת", 11: "שבט", 12: "אדר", 13: "אדר ב׳",
}

_ONES = ["", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט"]
_TENS = ["", "י", "כ", "ל", "מ", "נ", "ס", "ע", "פ", "צ"]
_HUNDREDS = ["", "ק", "ר", "ש", "ת"]


def gematria(n: int, geresh: bool = True) -> str:
    """Hebrew numeral for 1..999 (e.g. 15 -> ט״ו, 58 -> נ״ח)."""
    if n <= 0:
        return str(n)
    s = ""
    h = n // 100
    while h > 4:
        s += "ת"
        h -= 4
    s += _HUNDREDS[h]
    rem = n % 100
    if rem == 15:
        s += "טו"
    elif rem == 16:
        s += "טז"
    else:
        s += _TENS[rem // 10] + _ONES[rem % 10]
    if not geresh:
        return s
    return s + "׳" if len(s) == 1 else s[:-1] + "״" + s[-1]


def month_name(month: int, year: int) -> str:
    leap = hebrewcal.Year(year).leap
    if month == 12 and leap:
        return "אדר א׳"
    if month == 13:
        return "אדר ב׳"
    return MONTH_NAMES[month]


def to_hebrew(d: date) -> pdates.HebrewDate:
    return pdates.GregorianDate(d.year, d.month, d.day).to_heb()


def hebrew_info(d: date) -> dict:
    h = to_hebrew(d)
    return {
        "day": h.day,
        "month": h.month,
        "year": h.year,
        "day_str": gematria(h.day),
        "month_name": month_name(h.month, h.year),
        "year_str": gematria(h.year % 1000),
        "str": f"{gematria(h.day)} {month_name(h.month, h.year)} ה{gematria(h.year % 1000)}",
        "leap": hebrewcal.Year(h.year).leap,
    }


def is_leap(year: int) -> bool:
    return hebrewcal.Year(year).leap


def days_in_month(year: int, month: int) -> int:
    return 30 if (pdates.HebrewDate(year, month, 1) + 29).month == month else 29


def anniversary_dates(month: int, day: int, policy: str, year: int, day30_policy: str = "last_day") -> list[tuple[int, int]]:
    """Return the (month, day) pairs on which an anniversary falls in the given Hebrew year.

    month 12 = אדר (פשוטה) / אדר א׳; month 13 = אדר ב׳.
    policy (for month 12 when target year is leap): adar_i | adar_ii | both. This is an explicit
    choice stored per record — the system never guesses a custom.
    A record in month 13 (אדר ב׳) falls in אדר in a non-leap year.
    day 30 in a 29-day month: day30_policy last_day (→29) | next_day (→1 of next month).
    """
    leap = is_leap(year)
    months: list[int]
    if month == 13:
        months = [13] if leap else [12]
    elif month == 12 and leap:
        months = {"adar_i": [12], "adar_ii": [13], "both": [12, 13]}[policy]
    else:
        months = [month]
    out = []
    for m in months:
        dim = days_in_month(year, m)
        if day <= dim:
            out.append((m, day))
        elif day30_policy == "next_day":
            nxt = pdates.HebrewDate(year, m, dim) + 1
            out.append((nxt.month, nxt.day))
        else:
            out.append((m, dim))
    return out


def hebrew_to_greg(year: int, month: int, day: int) -> date:
    return pdates.HebrewDate(year, month, day).to_pydate()


def parsha_for_week(d: date, in_israel: bool) -> str | None:
    """Parsha read on the Shabbat on/after date d (None when a festival reading replaces it)."""
    from pyluach import parshios
    days_to_sat = (5 - d.weekday()) % 7  # python Monday=0 … Saturday=5
    sat = pdates.GregorianDate.from_pydate(d) + days_to_sat
    return parshios.getparsha_string(sat, israel=in_israel, hebrew=True)


def holiday_name(d: date, in_israel: bool, national: bool) -> str | None:
    h = to_hebrew(d)
    name = h.holiday(israel=in_israel, hebrew=True, prefix_day=True)
    if name and not national:
        if any(x in name for x in ("יום העצמאות", "יום הזיכרון", "יום ירושלים", "יום השואה")):
            return None
    return name


def fast_day_name(d: date) -> str | None:
    h = to_hebrew(d)
    return h.fast_day(hebrew=True)


# ---------------------------------------------------------------- daily learning names
TRACTATES = {
    "berachos": "ברכות", "peah": "פאה", "demai": "דמאי", "kilayim": "כלאים", "sheviis": "שביעית", "shviis": "שביעית",
    "terumos": "תרומות", "maasros": "מעשרות", "maaser_sheni": "מעשר שני", "chalah": "חלה", "orlah": "ערלה",
    "bikurim": "ביכורים", "shabbos": "שבת", "eruvin": "עירובין", "pesachim": "פסחים", "shekalim": "שקלים",
    "yoma": "יומא", "sukkah": "סוכה", "beitzah": "ביצה", "rosh_hashanah": "ראש השנה", "taanis": "תענית",
    "megillah": "מגילה", "megilah": "מגילה", "moed_katan": "מועד קטן", "chagigah": "חגיגה", "yevamos": "יבמות",
    "kesubos": "כתובות", "nedarim": "נדרים", "nazir": "נזיר", "sotah": "סוטה", "gitin": "גיטין",
    "kiddushin": "קידושין", "bava_kamma": "בבא קמא", "bava_kama": "בבא קמא", "bava_metzia": "בבא מציעא",
    "bava_basra": "בבא בתרא", "sanhedrin": "סנהדרין", "makkos": "מכות", "makos": "מכות", "shevuos": "שבועות",
    "eduyos": "עדויות", "avodah_zarah": "עבודה זרה", "avos": "אבות", "horiyos": "הוריות", "horayos": "הוריות",
    "zevachim": "זבחים", "menachos": "מנחות", "chullin": "חולין", "bechoros": "בכורות", "arachin": "ערכין",
    "temurah": "תמורה", "kerisos": "כריתות", "meilah": "מעילה", "tamid": "תמיד", "midos": "מדות",
    "kinnim": "קינים", "keilim": "כלים", "ohalos": "אהלות", "negaim": "נגעים", "parah": "פרה",
    "taharos": "טהרות", "mikvaos": "מקואות", "niddah": "נדה", "machshirin": "מכשירין", "zavim": "זבים",
    "tevul_yom": "טבול יום", "yadayim": "ידים", "uktzin": "עוקצים",
}


def render_limud(unit) -> str | None:
    if unit is None:
        return None
    comps = unit.components
    parts = []
    for c in comps:
        if isinstance(c, (list, tuple)):
            name = TRACTATES.get(c[0], c[0]) if isinstance(c[0], str) else gematria(c[0])
            nums = [gematria(x) for x in c[1:] if isinstance(x, int)]
            parts.append((name, nums))
        elif isinstance(c, str):
            parts.append((TRACTATES.get(c, c), []))
        elif isinstance(c, int):
            parts.append(("", [gematria(c)]))
    if not parts:
        return None
    if len(parts) == 1:
        name, nums = parts[0]
        if len(nums) == 2:
            return f"{name} {nums[0]}, {nums[1]}"
        return (name + " " + " ".join(nums)).strip()
    (n1, a), (n2, b) = parts[0], parts[1]
    if n1 == n2:
        if len(a) == 2 and len(b) == 2 and a[0] == b[0]:
            return f"{n1} {a[0]}, {a[1]}-{b[1]}"
        return f"{n1} {':'.join(a)} - {':'.join(b)}"
    return f"{n1} {':'.join(a)} - {n2} {':'.join(b)}"


# ---------------------------------------------------------------- omer
_UNITS_M = ["", "אחד", "שנים", "שלשה", "ארבעה", "חמשה", "ששה", "שבעה", "שמונה", "תשעה"]
_TEENS = {10: "עשרה", 11: "אחד עשר", 12: "שנים עשר", 13: "שלשה עשר", 14: "ארבעה עשר", 15: "חמשה עשר",
          16: "ששה עשר", 17: "שבעה עשר", 18: "שמונה עשר", 19: "תשעה עשר"}
_TENS_W = {2: "עשרים", 3: "שלשים", 4: "ארבעים"}


def _num_words(n: int) -> str:
    if n < 10:
        return _UNITS_M[n]
    if n < 20:
        return _TEENS[n]
    t, u = divmod(n, 10)
    return _TENS_W[t] if u == 0 else f"{_UNITS_M[u]} ו{_TENS_W[t]}"


def omer_long(n: int) -> str:
    if n == 1:
        days = "יום אחד"
    elif n == 2:
        days = "שני ימים"
    elif n < 11:
        days = f"{_num_words(n)} ימים"
    else:
        days = f"{_num_words(n)} יום"
    text = f"היום {days}"
    if n >= 7:
        w, d = divmod(n, 7)
        weeks = "שבוע אחד" if w == 1 else ("שני שבועות" if w == 2 else f"{_num_words(w)} שבועות")
        rest = "" if d == 0 else (" ויום אחד" if d == 1 else (" ושני ימים" if d == 2 else f" ו{_num_words(d)} ימים"))
        text += f" שהם {weeks}{rest}"
    return text + " לעומר"
