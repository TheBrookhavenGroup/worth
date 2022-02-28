import datetime
import pytz
from django.conf import settings


def our_now():
    # This results in a time that can be compared values in our database
    # even if saved by a human entering wall clock time into an admin field.
    # This is in the time zone specified in settings, for us it is 'America/New_York'.
    return datetime.datetime.now(tz=pytz.timezone(settings.TIME_ZONE))


def set_tz(dt):
    tz = pytz.timezone(settings.TIME_ZONE)
    return tz.localize(dt)


def yyyymmdd2dt(d):
    dt = datetime.datetime.strptime(str(d), '%Y%m%d')
    return set_tz(dt)


def dt2dt(dt):
    tz = pytz.timezone(settings.TIME_ZONE)
    dt = datetime.datetime.fromisoformat(dt)
    return tz.localize(dt)


def y1_to_y4(y):
    y = 2020 + int(y)
    yr = our_now().year
    if y > yr:
        while y - yr > 10:
            y -= 1
    else:
        while yr - y > 10:
            y += 1
    return y
