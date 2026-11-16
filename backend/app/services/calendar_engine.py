"""Zmanim + daily halachic calendar engine.

Engines: python-zmanim 0.3.x (port of KosherJava, NOAA algorithm, LGPL-2.1) for astronomical
times, molad and daily-learning cycles; pyluach 2.x (MIT) for Hebrew dates, parshiot and
holiday names. See docs/ZMANIM_ENGINE.md for methods, rounding and limitations.

Rounding convention (stringent, documented): times that mark the EARLIEST moment something is
allowed (dawn, misheyakir, sunrise, mincha, nightfall, end of Shabbat) are rounded UP to the
minute; DEADLINES (latest shma/tefila, sunset, candle lighting, chametz) are rounded DOWN.
"""
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from importlib.metadata import version
from zoneinfo import ZoneInfo

from zmanim.hebrew_calendar.jewish_calendar import JewishCalendar
from zmanim.limudim.calculators.daf_yomi_bavli import DafYomiBavli
from zmanim.limudim.calculators.daf_yomi_yerushalmi import DafYomiYerushalmi
from zmanim.limudim.calculators.mishna_yomis import MishnaYomis
from zmanim.limudim.calculators.pirkei_avos import PirkeiAvos
from zmanim.util.geo_location import GeoLocation
from zmanim.zmanim_calendar import ZmanimCalendar

from . import hebrew as H

ENGINE_VERSION = f"python-zmanim {version('zmanim')} + pyluach {version('pyluach')}"


@dataclass
class CalcProfile:
    latitude: float = 31.778
    longitude: float = 35.235
    elevation_m: float = 0
    timezone: str = "Asia/Jerusalem"
    in_israel: bool = True
    nusach: str = "sefardi"
    walled_city_purim: bool = False
    show_national_holidays: bool = True
    alos_method: str = "72min"
    misheyakir_degrees: float = 11.5
    tzeit_method: str = "8.5deg"
    candle_lighting_minutes: int = 20
    shabbat_end_method: str = "tzeit"
    shabbat_end_minutes: int = 40
    rabbeinu_tam_minutes: int = 72
    rabbeinu_tam_zmaniyot: bool = True
    use_elevation: bool = False
    enabled_zmanim: list = field(default_factory=list)
    prayer_additions: list = field(default_factory=list)
    reminders: list = field(default_factory=list)
    daily_learning: list = field(default_factory=list)

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


# key: (label, rounding 'up'|'down')
ZMANIM_DEFS: dict[str, tuple[str, str]] = {
    "alot": ("עלות השחר", "up"),
    "misheyakir": ("טלית ותפילין", "up"),
    "sunrise": ("זריחה", "up"),
    "shma_mga": ("סוף זמן ק״ש מג״א", "down"),
    "shma_gra": ("סוף זמן ק״ש גר״א", "down"),
    "tfila_mga": ("סוף זמן תפילה מג״א", "down"),
    "tfila_gra": ("סוף זמן תפילה גר״א", "down"),
    "chatzot": ("חצות היום", "up"),
    "mincha_gedola": ("מנחה גדולה", "up"),
    "mincha_ketana": ("מנחה קטנה", "up"),
    "plag": ("פלג המנחה", "up"),
    "sunset": ("שקיעה", "down"),
    "tzeit": ("צאת הכוכבים", "up"),
    "tzeit_rt": ("צאת הכוכבים ר״ת", "up"),
    "chatzot_night": ("חצות הלילה", "up"),
    "candle_lighting": ("הדלקת נרות", "down"),
    "shabbat_end": ("צאת שבת וחג", "up"),
    "shabbat_end_rt": ("צאת שבת וחג ר״ת", "up"),
    "fast_start": ("תחילת הצום", "down"),
    "fast_end": ("צאת הצום", "up"),
    "chametz_eat_mga": ("סוף זמן אכילת חמץ מג״א", "down"),
    "chametz_eat_gra": ("סוף זמן אכילת חמץ גר״א", "down"),
    "chametz_burn_mga": ("סוף זמן ביעור חמץ מג״א", "down"),
    "chametz_burn_gra": ("סוף זמן ביעור חמץ גר״א", "down"),
}

DEFAULT_ENABLED_ZMANIM = [
    "alot", "misheyakir", "sunrise", "shma_mga", "shma_gra", "tfila_mga", "tfila_gra", "chatzot",
    "mincha_gedola", "mincha_ketana", "plag", "sunset", "tzeit", "candle_lighting", "shabbat_end",
    "shabbat_end_rt", "fast_start", "fast_end", "chametz_eat_mga", "chametz_burn_mga",
]

# Zmanim allowed as anchors for relative prayer/lesson times
RELATIVE_ANCHORS = ["alot", "misheyakir", "sunrise", "chatzot", "mincha_gedola", "mincha_ketana", "plag",
                    "sunset", "tzeit", "tzeit_rt", "candle_lighting", "shabbat_end"]

ADDITION_DEFS = {
    "geshem": "משיב הרוח / מוריד הטל ושאלת גשמים",
    "tachanun": "לא אומרים תחנון",
    "lamnatzeach": "לא אומרים למנצח",
    "kabbalat_shabbat": "שינויים בקבלת שבת",
    "bameh_madlikin": "לא אומרים במה מדליקין",
    "av_harachamim": "אב הרחמים",
    "tzidkatcha": "לא אומרים צדקתך",
    "havdala": "הבדלה בתפילה (אתה חוננתנו / ותודיענו)",
    "vihi_noam": "לא אומרים ויהי נועם",
    "yaale_veyavo": "יעלה ויבוא",
    "hallel": "הלל",
    "ata_yatzarta": "אתה יצרת (ר״ח שחל בשבת)",
    "hamelech": "המלך הקדוש והמלך המשפט",
    "avinu_malkenu": "אבינו מלכנו",
    "ledavid": "לדוד ה׳ אורי וישעי",
    "al_hanisim": "על הניסים",
    "fast_announce": "הכרזת צום בשבת",
    "fast_additions": "הוספות בתפילה בצומות",
    "purim_meshulash": "סדר פורים המשולש",
    "nesiim": "פרשת הנשיאים",
    "hallel_pesach_night": "הלל בליל פסח",
    "omer_long": "ספירת העומר (נוסח ארוך)",
    "omer_short": "ספירת העומר (נוסח קצר)",
    "avot_shavuot": "פרקי אבות: פסח - שבועות",
    "avot_rh": "פרקי אבות: פסח - ראש השנה",
}
REMINDER_DEFS = {
    "rain": "הזכרת ושאלת גשמים / טל",
    "yom_kippur_katan": "יום כיפור קטן",
    "mevarchim": "שבת מברכים והכרזת ראש חודש",
    "molad": "זמן המולד",
    "levana_3": "קידוש לבנה ג׳ מהמולד",
    "levana_7": "ברכת הלבנה ז׳ מהמולד",
    "selichot": "זמן אמירת סליחות",
    "eruv_tavshilin": "עירוב תבשילין",
    "ushpizin": "אושפיזין",
    "bahab": "תענית שני וחמישי (בה״ב)",
    "fast": "תזכורת על צום",
    "shovavim": "שובבי״ם",
    "ilanot": "ברכת האילנות",
    "bedikat_chametz": "בדיקת חמץ",
    "bechorot": "תענית בכורות",
    "dst": "מעבר לשעון קיץ / חורף",
}
LEARNING_DEFS = {"daf_bavli": "דף היומי בבלי", "daf_yerushalmi": "דף היומי ירושלמי", "mishna_yomit": "משנה יומית"}

DEFAULT_ADDITIONS = ["geshem", "tachanun", "yaale_veyavo", "hallel", "hamelech", "al_hanisim", "fast_additions",
                     "omer_long", "havdala"]
DEFAULT_REMINDERS = ["rain", "mevarchim", "molad", "levana_7", "eruv_tavshilin", "fast", "bedikat_chametz", "dst"]
DEFAULT_LEARNING = ["daf_bavli"]

WEEKDAY_NAMES = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]
USHPIZIN = ["אברהם", "יצחק", "יעקב", "משה", "אהרן", "יוסף", "דוד"]


def sun_weekday(d: date) -> int:
    """0=Sunday … 6=Saturday."""
    return (d.weekday() + 1) % 7


def _round(dt: datetime | None, direction: str) -> datetime | None:
    if dt is None:
        return None
    if direction == "up" and (dt.second or dt.microsecond):
        dt = dt + timedelta(minutes=1)
    return dt.replace(second=0, microsecond=0)


class DayCalculator:
    """Computes everything the display needs for one civil date."""

    def __init__(self, profile: CalcProfile):
        self.p = profile
        self.tz = ZoneInfo(profile.timezone)
        self.geo = GeoLocation("synagogue", profile.latitude, profile.longitude, profile.timezone,
                               elevation=profile.elevation_m)

    # ------------------------------------------------------------ helpers
    def jc(self, d: date) -> JewishCalendar:
        j = JewishCalendar(d)
        j.in_israel = self.p.in_israel
        j.use_modern_holidays = True
        return j

    def zc(self, d: date) -> ZmanimCalendar:
        z = ZmanimCalendar(geo_location=self.geo, date=d, candle_lighting_offset=self.p.candle_lighting_minutes)
        z.use_elevation = self.p.use_elevation
        return z

    def is_yom_tov(self, d: date) -> bool:
        return self.jc(d).is_yom_tov_assur_bemelacha()

    def is_assur(self, d: date) -> bool:
        j = self.jc(d)
        return sun_weekday(d) == 6 or j.is_yom_tov_assur_bemelacha()

    # ------------------------------------------------------------ zmanim
    def raw_zmanim(self, d: date) -> dict[str, datetime | None]:
        z = self.zc(d)
        j = self.jc(d)
        alos = {
            "72min": lambda: z.alos({"offset": 72}),
            "90min": lambda: z.alos({"offset": 90}),
            "16.1deg": lambda: z.alos({"degrees": 16.1}),
            "19.8deg": lambda: z.alos({"degrees": 19.8}),
        }[self.p.alos_method]()
        tzeit = {
            "8.5deg": lambda: z.tzais({"degrees": 8.5}),
            "7.083deg": lambda: z.tzais({"degrees": 7.083}),
            "13.5min_zmaniyot": lambda: z.tzais({"zmanis_offset": 13.5}),
            "18min": lambda: z.tzais({"offset": 18}),
            "20min": lambda: z.tzais({"offset": 20}),
        }[self.p.tzeit_method]()
        rt_opts = {"zmanis_offset": self.p.rabbeinu_tam_minutes} if self.p.rabbeinu_tam_zmaniyot else {
            "offset": self.p.rabbeinu_tam_minutes}
        tzeit_rt = z.tzais(rt_opts)
        sunrise, sunset = z.elevation_adjusted_sunrise(), z.elevation_adjusted_sunset()
        alos72 = z.alos({"offset": 72})
        out: dict[str, datetime | None] = {
            "alot": alos,
            "misheyakir": z.sunrise_offset_by_degrees(z.GEOMETRIC_ZENITH + self.p.misheyakir_degrees),
            "sunrise": sunrise,
            "shma_mga": z.sof_zman_shma_mga(),
            "shma_gra": z.sof_zman_shma_gra(),
            "tfila_mga": z.sof_zman_tfila_mga(),
            "tfila_gra": z.sof_zman_tfila_gra(),
            "chatzot": z.chatzos(),
            "mincha_gedola": z.mincha_gedola(),
            "mincha_ketana": z.mincha_ketana(),
            "plag": z.plag_hamincha(),
            "sunset": sunset,
            "tzeit": tzeit,
            "tzeit_rt": tzeit_rt,
            "chatzot_night": z.chatzos() + timedelta(hours=12) if z.chatzos() else None,
        }
        # candle lighting: erev Shabbat / erev Yom Tov (when the next day is assur and today is not)
        today_assur = self.is_assur(d)
        tomorrow_assur = self.is_assur(d + timedelta(days=1))
        if tomorrow_assur and not today_assur:
            out["candle_lighting"] = z.candle_lighting()
        elif tomorrow_assur and today_assur:
            # second day / Shabbat after Yom Tov: lighting only after nightfall (from an existing flame)
            out["candle_lighting"] = tzeit
        if today_assur and not tomorrow_assur:
            if self.p.shabbat_end_method == "minutes_after_sunset":
                out["shabbat_end"] = sunset + timedelta(minutes=self.p.shabbat_end_minutes) if sunset else None
            else:
                out["shabbat_end"] = tzeit
            out["shabbat_end_rt"] = tzeit_rt
        # fasts
        if j.is_taanis():
            sig = j.significant_day()
            if sig not in ("tisha_beav", "yom_kippur"):
                out["fast_start"] = alos
            out["fast_end"] = tzeit if sig != "yom_kippur" else out.get("shabbat_end", tzeit)
        tomorrow = self.jc(d + timedelta(days=1))
        if tomorrow.significant_day() in ("tisha_beav", "yom_kippur") and tomorrow.is_taanis():
            out["fast_start"] = sunset
        # chametz (14 Nisan)
        if j.jewish_month == 1 and j.jewish_day == 14:
            sh_gra = z.shaah_zmanis_gra()
            sh_mga = z.shaah_zmanis_mga()
            if sh_gra and sh_mga:
                out["chametz_eat_gra"] = sunrise + timedelta(milliseconds=sh_gra * 4)
                out["chametz_burn_gra"] = sunrise + timedelta(milliseconds=sh_gra * 5)
                out["chametz_eat_mga"] = alos72 + timedelta(milliseconds=sh_mga * 4)
                out["chametz_burn_mga"] = alos72 + timedelta(milliseconds=sh_mga * 5)
        return out

    def zmanim(self, d: date) -> dict:
        raw = self.raw_zmanim(d)
        result = {}
        for key, dt in raw.items():
            label, direction = ZMANIM_DEFS[key]
            r = _round(dt, direction)
            if r is not None:
                result[key] = r.astimezone(self.tz)
        return result

    # ------------------------------------------------------------ day flags
    def flags(self, d: date) -> dict:
        j = self.jc(d)
        sig = j.significant_day()
        wd = sun_weekday(d)
        return {
            "weekday": wd,
            "is_shabbat": wd == 6,
            "is_erev_shabbat": wd == 5,
            "is_yom_tov": j.is_yom_tov_assur_bemelacha(),
            "is_erev_yom_tov": j.is_erev_yom_tov() and not j.is_yom_tov_assur_bemelacha(),
            "is_chol_hamoed": j.is_chol_hamoed(),
            "is_rosh_chodesh": j.is_rosh_chodesh(),
            "is_fast": j.is_taanis(),
            "is_chanukah": j.is_chanukah(),
            "assur_today": self.is_assur(d),
            "assur_tomorrow": self.is_assur(d + timedelta(days=1)),
            "significant": sig,
        }

    # ------------------------------------------------------------ tachanun & additions
    def no_tachanun_weekday(self, d: date) -> bool:
        """Common custom; every addition can be disabled by the admin."""
        j = self.jc(d)
        m, dd = j.jewish_month, j.jewish_day
        if j.is_rosh_chodesh() or j.is_chanukah() or j.is_chol_hamoed() or j.is_yom_tov_assur_bemelacha():
            return True
        if m == 1:  # Nisan
            return True
        if (m, dd) in ((2, 14), (2, 18), (5, 9), (5, 15), (11, 15)):
            return True
        if m == 3 and dd <= 12:
            return True
        if m == 7 and dd >= 9:
            return True
        if m == 6 and dd == 29:  # Erev Rosh Hashana
            return True
        if m in (12, 13) and dd in (14, 15):  # Purim / Purim Katan (Adar I)
            return True
        return False

    def additions(self, d: date) -> list[str]:
        p = set(self.p.prayer_additions)
        j = self.jc(d)
        f = self.flags(d)
        m, dd, y = j.jewish_month, j.jewish_day, j.jewish_year
        sig = f["significant"]
        out: list[str] = []
        # evening Hebrew date (for things that start at night)
        jn = self.jc(d + timedelta(days=1))

        if "geshem" in p:
            rainy = (m == 7 and dd >= 22) or m in (8, 9, 10, 11, 12, 13) or (m == 1 and dd <= 14)
            if rainy:
                out.append("משיב הרוח ומוריד הגשם")
            elif not (self.p.nusach == "ashkenazi" and not self.p.in_israel):
                out.append("מוריד הטל")
            if self.p.in_israel:
                tal_umatar = (m == 8 and dd >= 7) or m in (9, 10, 11, 12, 13) or (m == 1 and dd <= 14)
            else:
                # Diaspora: from Ma'ariv of Dec 4 (Dec 5 before a Gregorian leap year) until Pesach
                start_day = 5 if ((d.year + 1) % 4 == 0 and ((d.year + 1) % 100 != 0 or (d.year + 1) % 400 == 0)) else 4
                tal_umatar = (d.month == 12 and d.day > start_day) or (m in (10, 11, 12, 13)) or (m == 1 and dd <= 14) \
                    or (d.month == 12 and d.day >= start_day and m == 9)
            out.append("ותן טל ומטר לברכה" if tal_umatar else "ותן ברכה")
        weekday_no_tach = self.no_tachanun_weekday(d)
        if "tachanun" in p and not f["is_shabbat"] and weekday_no_tach and not f["is_yom_tov"]:
            out.append("לא אומרים תחנון")
        if "lamnatzeach" in p and not f["is_shabbat"] and not f["is_yom_tov"] and (
                weekday_no_tach or (m == 1 and dd == 14) or (m == 7 and dd == 9) or sig == "tisha_beav"):
            out.append("לא אומרים למנצח")
        if f["is_shabbat"]:
            if "tzidkatcha" in p and weekday_no_tach and not f["is_yom_tov"]:
                out.append("במנחה לא אומרים צדקתך")
            if "av_harachamim" in p:
                mevarchim = self._is_mevarchim(d)
                if (mevarchim and jn.jewish_month not in (2, 3)) or weekday_no_tach:
                    out.append("לא אומרים אב הרחמים")
            if "havdala" in p and not self.is_assur(d + timedelta(days=1)):
                out.append("במוצאי שבת: אתה חוננתנו")
            if "havdala" in p and self.is_yom_tov(d + timedelta(days=1)):
                out.append("במוצאי שבת: ותודיענו")
            if "vihi_noam" in p:
                week = [d + timedelta(days=i) for i in range(1, 7)]
                if any(self.is_yom_tov(x) for x in week):
                    out.append("במוצאי שבת לא אומרים ויהי נועם")
            if "ata_yatzarta" in p and f["is_rosh_chodesh"]:
                out.append("במוסף: אתה יצרת")
        if f["is_erev_shabbat"] or f["is_shabbat"]:
            sat = d if f["is_shabbat"] else d + timedelta(days=1)
            sat_j = self.jc(sat)
            if "bameh_madlikin" in p and (sat_j.is_yom_tov_assur_bemelacha() or sat_j.is_chol_hamoed()
                                          or self.is_yom_tov(sat + timedelta(days=1))):
                out.append("בליל שבת לא אומרים במה מדליקין")
            if "kabbalat_shabbat" in p and (sat_j.is_yom_tov_assur_bemelacha() or sat_j.is_chol_hamoed()
                                            or self.is_yom_tov(sat - timedelta(days=1))):
                out.append("שינויים בקבלת שבת (שבת חל ביו״ט / חול המועד)")
        if f["assur_today"] and "havdala" in p and not f["is_shabbat"] and not self.is_assur(d + timedelta(days=1)):
            out.append("במוצאי החג: אתה חוננתנו")
        if "yaale_veyavo" in p and (f["is_rosh_chodesh"] or f["is_chol_hamoed"] or f["is_yom_tov"]):
            out.append("יעלה ויבוא")
        if "hallel" in p:
            hallel = self._hallel(j)
            if hallel:
                out.append(hallel)
        if "hamelech" in p and m == 7 and dd <= 10:
            out.append("המלך הקדוש, המלך המשפט")
        if "avinu_malkenu" in p and ((m == 7 and dd <= 10 and not f["is_shabbat"]) or (
                f["is_fast"] and sig != "tisha_beav")):
            out.append("אבינו מלכנו")
        if "ledavid" in p and (m == 6 or (m == 7 and dd <= 21)):
            out.append("לדוד ה׳ אורי וישעי")
        if "al_hanisim" in p and (f["is_chanukah"] or self._is_purim(j)):
            out.append("על הניסים")
        if "fast_additions" in p and f["is_fast"]:
            out.append("עננו" + (" ונחם" if sig == "tisha_beav" else ""))
        if "fast_announce" in p and f["is_shabbat"]:
            for i in range(1, 7):
                nj = self.jc(d + timedelta(days=i))
                if nj.is_taanis() and nj.significant_day() not in ("yom_kippur",):
                    out.append(f"הכרזת צום ({H.fast_day_name(d + timedelta(days=i)) or 'תענית'})")
                    break
        if "purim_meshulash" in p and self.p.walled_city_purim:
            adar = 13 if H.is_leap(y) else 12
            if m == adar and 14 <= dd <= 16:
                p15 = H.hebrew_to_greg(y, adar, 15)
                if sun_weekday(p15) == 6:
                    out.append("פורים המשולש")
        if "nesiim" in p and m == 1 and 1 <= dd <= 13:
            out.append(f"פרשת הנשיאים — יום {H.gematria(dd)}" if dd <= 12 else "זאת חנוכת המזבח")
        if "hallel_pesach_night" in p and m == 1 and dd == 14:
            out.append("הלל בליל פסח")
        omer_tonight = jn.day_of_omer()
        if omer_tonight and ("omer_long" in p or "omer_short" in p):
            if "omer_long" in p:
                out.append("ספירת העומר הלילה: " + H.omer_long(omer_tonight))
            else:
                out.append(f"ספירת העומר הלילה: {H.gematria(omer_tonight)} לעומר")
        if f["is_shabbat"] and ("avot_shavuot" in p or "avot_rh" in p):
            avot = self._pirkei_avot(d, only_until_shavuot="avot_rh" not in p)
            if avot:
                out.append(avot)
        return out

    def _hallel(self, j: JewishCalendar) -> str | None:
        m, dd = j.jewish_month, j.jewish_day
        israel = self.p.in_israel
        if j.is_chanukah():
            return "הלל שלם"
        if m == 7 and 15 <= dd <= (23 if not israel else 22):
            return "הלל שלם"
        if m == 3 and dd == 6 or (m == 3 and dd == 7 and not israel):
            return "הלל שלם"
        if m == 1 and (dd == 15 or (dd == 16 and not israel)):
            return "הלל שלם"
        if m == 1 and 16 <= dd <= (22 if not israel else 21):
            return "חצי הלל"
        if j.is_rosh_chodesh() and m != 7:
            return "חצי הלל"
        return None

    def _is_purim(self, j: JewishCalendar) -> bool:
        adar = 13 if H.is_leap(j.jewish_year) else 12
        day = 15 if self.p.walled_city_purim else 14
        return j.jewish_month == adar and j.jewish_day == day

    def _is_mevarchim(self, d: date) -> bool:
        """Shabbat before Rosh Chodesh (except Tishrei)."""
        if sun_weekday(d) != 6:
            return False
        for i in range(1, 8):
            nj = self.jc(d + timedelta(days=i))
            if nj.jewish_day in (1, 30):
                return nj.jewish_month != 7 and not (nj.jewish_day == 30 and nj.jewish_month == 6)
        return False

    def _pirkei_avot(self, d: date, only_until_shavuot: bool) -> str | None:
        j = self.jc(d)
        if only_until_shavuot and not (j.jewish_month == 1 or j.jewish_month == 2 or (j.jewish_month == 3 and j.jewish_day < 6)):
            return None
        try:
            lim = PirkeiAvos(in_israel=self.p.in_israel).limud(j)
        except Exception:
            return None
        if not lim:
            return None
        comps = lim.unit.components
        chapters = []
        for c in comps:
            if isinstance(c, (list, tuple)):
                chapters.extend([x for x in c if isinstance(x, int)])
            elif isinstance(c, int):
                chapters.append(c)
        if not chapters:
            return None
        return "פרקי אבות: פרק " + "-".join(H.gematria(c) for c in chapters)

    # ------------------------------------------------------------ reminders
    def reminders(self, d: date) -> list[str]:
        p = set(self.p.reminders)
        j = self.jc(d)
        f = self.flags(d)
        m, dd, y = j.jewish_month, j.jewish_day, j.jewish_year
        out: list[str] = []
        if "rain" in p:
            if m == 7 and 21 <= dd <= 22:
                out.append("בשמיני עצרת מתחילים לומר משיב הרוח ומוריד הגשם")
            if self.p.in_israel and m == 8 and 6 <= dd <= 7:
                out.append("מליל ז׳ חשון מתחילים לומר ותן טל ומטר לברכה")
            if m == 1 and 14 <= dd <= 15:
                out.append("ביום א׳ של פסח (מוסף) מפסיקים לומר משיב הרוח")
        if "yom_kippur_katan" in p:
            ykk = self._yom_kippur_katan(d)
            if ykk:
                out.append(ykk)
        if "mevarchim" in p and sun_weekday(d) in (5, 6):
            sat = d if sun_weekday(d) == 6 else d + timedelta(days=1)
            if self._is_mevarchim(sat):
                rc = self._next_rosh_chodesh(sat)
                if rc:
                    out.append(rc)
        if "molad" in p and sun_weekday(d) in (4, 5, 6):
            sat = d + timedelta(days=(6 - sun_weekday(d)))
            if self._is_mevarchim(sat):
                out.append(self._molad_text(sat))
        if "levana_3" in p or "levana_7" in p:
            jj = self.jc(d)
            start = jj.techilas_zman_kiddush_levana_7_days() if "levana_7" in p else jj.techilas_zman_kiddush_levana_3_days()
            end = jj.sof_zman_kiddush_levana_15_days()
            if start and end:
                st, en = start.astimezone(self.tz), end.astimezone(self.tz)
                day_start = datetime(d.year, d.month, d.day, tzinfo=self.tz)
                day_end = day_start + timedelta(days=1)
                if day_start <= st < day_end:
                    out.append(f"תחילת זמן ברכת הלבנה הלילה מהשעה {st:%H:%M}")
                elif st < day_start and en > day_start:
                    out.append(f"זמן ברכת הלבנה עד {WEEKDAY_NAMES[sun_weekday(en.date())]} {en:%H:%M}")
        if "selichot" in p and self._selichot(d):
            out.append("אומרים סליחות")
        if "eruv_tavshilin" in p and self._eruv_tavshilin(d):
            out.append("היום מניחים עירוב תבשילין")
        if "ushpizin" in p and m == 7 and 15 <= dd <= 21:
            out.append(f"אושפיזא: {USHPIZIN[dd - 15]}")
        if "bahab" in p and self._bahab(d):
            out.append("תענית שני וחמישי ושני (בה״ב)")
        if "fast" in p:
            for i in (1,):
                nd = d + timedelta(days=i)
                nj = self.jc(nd)
                if nj.is_taanis():
                    name = H.fast_day_name(nd) or "תענית"
                    out.append(f"מחר: {name}")
        if "shovavim" in p:
            parsha = H.parsha_for_week(d, self.p.in_israel) or ""
            names = ["שמות", "וארא", "בא", "בשלח", "יתרו", "משפטים"]
            if H.is_leap(y):
                names += ["תרומה", "תצוה"]
            if any(parsha.startswith(n) for n in names) and m in (10, 11, 12, 13):
                out.append("ימי השובבי״ם")
        if "ilanot" in p and m == 1:
            out.append("חודש ניסן — זמן ברכת האילנות")
        if "bedikat_chametz" in p:
            erev = H.hebrew_to_greg(y, 1, 14) if m == 1 else None
            if erev:
                bedika = erev - timedelta(days=1) if sun_weekday(erev) != 6 else erev - timedelta(days=2)
                if d == bedika:
                    out.append("הלילה בדיקת חמץ")
        if "bechorot" in p and m == 1:
            erev = H.hebrew_to_greg(y, 1, 14)
            fast = erev if sun_weekday(erev) != 6 else erev - timedelta(days=2)
            if d == fast:
                out.append("תענית בכורות")
        if "dst" in p:
            today_off = datetime(d.year, d.month, d.day, 12, tzinfo=self.tz).utcoffset()
            for i in range(1, 8):
                nd = d + timedelta(days=i)
                off = datetime(nd.year, nd.month, nd.day, 12, tzinfo=self.tz).utcoffset()
                if off != today_off:
                    kind = "קיץ" if off > today_off else "חורף"
                    out.append(f"מעבר לשעון {kind} בליל {WEEKDAY_NAMES[sun_weekday(nd - timedelta(days=1))]} {nd - timedelta(days=1):%d/%m}")
                    break
        return out

    def _next_rosh_chodesh(self, sat: date) -> str | None:
        days = []
        for i in range(1, 9):
            nd = sat + timedelta(days=i)
            nj = self.jc(nd)
            if nj.is_rosh_chodesh():
                days.append(nd)
            elif days:
                break
        if not days:
            return None
        hj = self.jc(days[-1])
        month = H.month_name(hj.jewish_month, hj.jewish_year)
        names = " ו".join(WEEKDAY_NAMES[sun_weekday(x)] for x in days)
        return f"ראש חודש {month} יחול ביום {names}"

    def _molad_text(self, sat: date) -> str:
        nd = sat + timedelta(days=7)
        j = self.jc(nd)
        if j.jewish_day > 15:
            j = self.jc(nd + timedelta(days=15))
        mol = j.molad()
        dow = WEEKDAY_NAMES[(mol.day_of_week - 1) % 7]
        return (f"המולד: יום {dow}, {mol.molad_hours} שעות, {mol.molad_minutes} דקות "
                f"ו-{mol.molad_chalakim} חלקים")

    def _yom_kippur_katan(self, d: date) -> str | None:
        wd = sun_weekday(d)
        if wd in (5, 6):
            return None
        # the next Rosh Chodesh day 1 within 3 days
        for i in range(1, 4):
            nd = d + timedelta(days=i)
            nj = self.jc(nd)
            if nj.is_rosh_chodesh() and (nj.jewish_day == 1 or nj.jewish_day == 30):
                if nj.jewish_month in (7, 8, 10, 2) or (nj.jewish_day == 30 and nj.jewish_month in (6, 7, 9, 1)):
                    return None
                erev = nd - timedelta(days=1)
                if sun_weekday(erev) in (5, 6):
                    erev = erev - timedelta(days=(sun_weekday(erev) - 4))
                return "יום כיפור קטן" if erev == d else None
        return None

    def _selichot(self, d: date) -> bool:
        j = self.jc(d)
        m, dd, y = j.jewish_month, j.jewish_day, j.jewish_year
        if self.is_assur(d):
            return False
        if self.p.nusach in ("sefardi", "teimani_baladi", "teimani_shami"):
            return (m == 6 and dd >= 2) or (m == 7 and 3 <= dd <= 9)
        rh = H.hebrew_to_greg(y + 1 if m == 6 else y, 7, 1)
        start = rh - timedelta(days=4)
        while sun_weekday(start) != 0:
            start -= timedelta(days=1)
        return (start <= d < rh) or (m == 7 and 3 <= dd <= 9)

    def _eruv_tavshilin(self, d: date) -> bool:
        if self.is_assur(d) or not self.is_yom_tov(d + timedelta(days=1)):
            return False
        x = d + timedelta(days=1)
        while self.is_yom_tov(x):
            if sun_weekday(x) == 5:  # Yom Tov on Friday, Shabbat follows
                return True
            x += timedelta(days=1)
        return False

    def _bahab(self, d: date) -> bool:
        j = self.jc(d)
        if j.jewish_month not in (8, 2):
            return False
        first = H.hebrew_to_greg(j.jewish_year, j.jewish_month, 1)
        sat = first + timedelta(days=(6 - sun_weekday(first)) % 7)
        mon1 = sat + timedelta(days=2)
        return d in (mon1, mon1 + timedelta(days=3), mon1 + timedelta(days=7))

    # ------------------------------------------------------------ learning
    def learning(self, d: date) -> list[dict]:
        out = []
        j = self.jc(d)
        calcs = {"daf_bavli": DafYomiBavli, "daf_yerushalmi": DafYomiYerushalmi, "mishna_yomit": MishnaYomis}
        for key in self.p.daily_learning:
            if key not in calcs:
                continue
            try:
                lim = calcs[key]().limud(j)
                text = H.render_limud(lim.unit) if lim else None
            except Exception:
                text = None
            if text and "no_daf_today" not in text:
                out.append({"key": key, "label": LEARNING_DEFS[key], "value": text})
        return out


def time_str(dt: datetime | None) -> str | None:
    return dt.strftime("%H:%M") if dt else None


def round_time(dt: datetime, rounding: str) -> datetime:
    if rounding == "none":
        return dt.replace(second=0, microsecond=0)
    minute = dt.minute + dt.second / 60
    if rounding == "down5":
        m = math.floor(minute / 5) * 5
    elif rounding == "up5":
        m = math.ceil(minute / 5) * 5
    else:
        m = round(minute / 5) * 5
    return dt.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=m)
