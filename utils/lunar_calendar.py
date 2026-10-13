from datetime import date, datetime


def _normalise_lunar_result(result):
    """Normalise various possible return shapes from vietlunar."""
    if isinstance(result, dict):
        return (
            result.get("year"),
            result.get("month"),
            result.get("day"),
            bool(result.get("is_leap") or result.get("leap_month") or result.get("isLeap")),
        )
    if isinstance(result, (list, tuple)) and len(result) >= 3:
        leap = False
        if len(result) >= 4:
            leap = bool(result[3])
        return (result[0], result[1], result[2], leap)
    if hasattr(result, "year"):
        leap = getattr(result, "is_leap", None)
        if leap is None:
            leap = getattr(result, "leap_month", False)
        return (
            getattr(result, "year", None),
            getattr(result, "month", None),
            getattr(result, "day", None),
            bool(leap),
        )
    return None


try:
    from vietlunar import VietLunar
except Exception:  # pragma: no cover
    VietLunar = None


def gregorian_to_lunar_day(gdate):
    """Return (year, month, day, leap) for a Gregorian date. If no library is available,
    fall back to the Gregorian date itself so the app still behaves sensibly.
    """
    if VietLunar is None:
        return (gdate.year, gdate.month, gdate.day, False)
    try:
        lunar = VietLunar().solar_to_lunar(gdate.year, gdate.month, gdate.day)
        return _normalise_lunar_result(lunar)
    except Exception:
        return (gdate.year, gdate.month, gdate.day, False)


def same_lunar_day(one_date, another_date):
    try:
        a = gregorian_to_lunar_day(one_date)
        b = gregorian_to_lunar_day(another_date)
        return a[1] == b[1] and a[2] == b[2]
    except Exception:
        return one_date.month == another_date.month and one_date.day == another_date.day
