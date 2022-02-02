import datetime
import pytz
from django.conf import settings


def our_now():
    # This results in a time that can be compared values in our database
    # even if saved by a human entering wall clock time into an admin field.
    # This is in the time zone specified in settings, for us it is 'America/New_York'.
    return datetime.datetime.now(tz=pytz.timezone(settings.TIME_ZONE))


def yyyymmdd2dt(d):
    return datetime.strptime(str(d), '%Y%m%d')