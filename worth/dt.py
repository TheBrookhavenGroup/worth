import datetime
import pytz
from django.conf import settings


def our_now():
    # This results in a time that can be compared values in our database
    # even if saved by a human entering wall clock time into an admin field.
    # This is in the time zone specified in settings, for us it is 'America/New_York'.
    return datetime.datetime.now(tz=pytz.timezone(settings.TIME_ZONE))


def our_localize(t):
    # Given datetime(2021, 10, 21, 0, 0, 0, 0) this will return the
    # datetime when it is 0, 0, 0, 0 in the local time, say NY.
    utc = pytz.timezone('UTC')
    tz = pytz.timezone(settings.TIME_ZONE)
    return tz.localize(t).astimezone(utc)


def to_date(d):
    if type(d) == str:
        if '-' in d:
            d = datetime.date.fromisoformat(d)
        else:
            d = datetime.datetime.strptime(d, '%Y%m%d').date()
    elif d is None:
        d = datetime.date.today()

    return d


def day_start(d):
    # Return start of day in local time zone
    t = datetime.datetime(d.year, d.month, d.day)
    return our_localize(t)


def day_start_next_day(d):
    # Return start of next day in local time zone
    # Good for finding all trades where dt is less than this for a given date.
    t = datetime.datetime(d.year, d.month, d.day)
    t += datetime.timedelta(days=1)
    return our_localize(t)


def set_tz(dt):
    # useful for output
    tz = pytz.timezone(settings.TIME_ZONE)
    if dt.tzinfo is not None:
        return dt.astimezone(tz)
    return tz.localize(dt)


def yyyymmdd2dt(d):
    if (type(d) == datetime.datetime) or (type(d) == datetime.date):
        return d
    d = datetime.datetime.strptime(str(d), '%Y%m%d')
    d = set_tz(d)
    return d


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


def is_week_end(d):
    return d.weekday() > 4


# Butcher's algorithm http://code.activestate.com/recipes/576517-calculate-easter-western-given-a-year/
def easter(year):
    #  Returns Easter as a date object.
    a = year % 19
    b = year // 100
    c = year % 100
    d = (19 * a + b - b // 4 - ((b - (b + 8) // 25 + 1) // 3) + 15) % 30
    e = (32 + 2 * (b % 4) + 2 * (c // 4) - d - (c % 4)) % 7
    f = d + e - 7 * ((a + 11 * d + 22 * e) // 451) + 114
    month = f // 31
    day = f % 31 + 1
    return datetime.date(year, month, day)


def good_friday(year):
    d = easter(year)
    return d - datetime.timedelta(days=2)


def which_holiday(dte, weekend_f=True):
    if weekend_f and is_week_end(dte):
        return 'Weekend'

    y, m, d, wd = dte.year, dte.month, dte.day, dte.weekday()

    if 1 == m:
        if 1 == d:
            return 'New Years Day'
        elif (2 == d) and (0 == wd):
            # It is Monday the 2nd so the first was a Sunday.
            return 'New Years Day observed'
        elif (0 == wd) and (d > 14) and (d < 22) and (y > 1985):
            return 'MLK Day'
    elif 2 == m:
        # Presidents day - third Monday of February
        if (0 == wd) and (d > 14) and (d < 22):
            return 'Presidents Day'
    elif 5 == m:
        # Memorial day is the last Monday in May
        if (0 == wd) and (d > 24):
            return 'Memorial Day'
    elif 7 == m:
        # Independence day
        if 4 == d:
            return 'Independence Day'
        elif (3 == d) and (4 == wd):
            # It is the 3rd of the month and a Friday so the 4th is Saturday
            # This happens in 2020.
            return 'Independence Day Observed'
        elif (5 == d) and (0 == wd):
            # It is the 5th of the month and a Monday so the 4th is Sunday.
            return 'Independence Day Observed'
    elif 9 == m:
        # Labor day
        if (0 == wd) and (d < 8):
            return 'Labor Day'
    elif 11 == m:
        # Thanksgiving - fourth Thursday of November
        if (3 == wd) and (d > 21) and (d < 29):
            return 'Thanksgiving Day'
    elif 12 == m:
        if 25 == d:
            # Christmas
            return 'Christmas'
        elif (24 == d) and (4 == wd):
            # It is Friday the 24th so Christmas is on Saturday
            return 'Christmas observed'
        elif (26 == d) and (0 == wd):
            # It is Monday the 26th so Christmas is on Sunday
            return 'Christmas observed'
        elif (31 == d) and (4 == wd):
            # It is Friday the 31st so Saturday is New Years.
            return 'New Years Day observed'

    gf = good_friday(y)
    if dte == good_friday(y):
        return 'Good Friday'

    return None


def is_holiday_observed(dte, weekend_f=True):
    return which_holiday(dte, weekend_f=weekend_f) is not None


def test_is_holiday_observed():
    expected = [[20140101, 'Wednesday New Years Day'],
                [20140120, 'Monday MLK Day'],
                [20140217, 'Monday Presidents Day'],
                [20140418, 'Friday Easter Friday'],
                [20140526, 'Monday Memorial Day'],
                [20140704, 'Friday Independence Day'],
                [20140901, 'Monday Labor Day'],
                [20141127, 'Thursday Thanksgiving Day'],
                [20141225, 'Thursday Christmas Day'],
                [20150101, 'Thursday New Years Day'],
                [20150119, 'Monday MLK Day'],
                [20150216, 'Monday Presidents Day'],
                [20150403, 'Friday Easter Friday'],
                [20150525, 'Monday Memorial Day'],
                [20150703, 'Friday Independence Day'],
                [20150704, 'Saturday Independence Day'],
                [20150907, 'Monday Labor Day'],
                [20151126, 'Thursday Thanksgiving Day'],
                [20151225, 'Friday Christmas Day'],
                [20160101, 'Friday New Years Day'],
                [20160118, 'Monday MLK Day'],
                [20160215, 'Monday Presidents Day'],
                [20160325, 'Friday Easter Friday'],
                [20160530, 'Monday Memorial Day'],
                [20160704, 'Monday Independence Day'],
                [20160905, 'Monday Labor Day'],
                [20161124, 'Thursday Thanksgiving Day'],
                [20161225, 'Sunday Christmas Day'],
                [20161226, 'Monday Christmas Day'],
                [20170101, 'Sunday New Years Day'],
                [20170102, 'Monday New Years Day'],
                [20170116, 'Monday MLK Day'],
                [20170220, 'Monday Presidents Day'],
                [20170414, 'Friday Easter Friday'],
                [20170529, 'Monday Memorial Day'],
                [20170704, 'Tuesday Independence Day'],
                [20170904, 'Monday Labor Day'],
                [20171123, 'Thursday Thanksgiving Day'],
                [20171225, 'Monday Christmas Day'],
                [20180101, 'Monday New Years Day'],
                [20180115, 'Monday MLK Day'],
                [20180219, 'Monday Presidents Day'],
                [20180330, 'Friday Easter Friday'],
                [20180528, 'Monday Memorial Day'],
                [20180704, 'Wednesday Independence Day'],
                [20180903, 'Monday Labor Day'],
                [20181122, 'Thursday Thanksgiving Day'],
                [20181225, 'Tuesday Christmas Day'],
                [20190101, 'Tuesday New Years Day'],
                [20190121, 'Monday MLK Day'],
                [20190218, 'Monday Presidents Day'],
                [20190419, 'Friday Easter Friday'],
                [20190527, 'Monday Memorial Day'],
                [20190704, 'Thursday Independence Day'],
                [20190902, 'Monday Labor Day'],
                [20191128, 'Thursday Thanksgiving Day'],
                [20191225, 'Wednesday Christmas Day'],
                [20200101, 'Wednesday New Years Day'],
                [20200120, 'Monday MLK Day'],
                [20200217, 'Monday Presidents Day'],
                [20200410, 'Friday Easter Friday'],
                [20200525, 'Monday Memorial Day'],
                [20200703, 'Friday Independence Day'],
                [20200704, 'Saturday Independence Day'],
                [20200907, 'Monday Labor Day'],
                [20201126, 'Thursday Thanksgiving Day'],
                [20201225, 'Friday Christmas Day'],
                [20210101, 'Friday New Years Day'],
                [20210118, 'Monday MLK Day'],
                [20210215, 'Monday Presidents Day'],
                [20210402, 'Friday Easter Friday'],
                [20210531, 'Monday Memorial Day'],
                [20210704, 'Sunday Independence Day'],
                [20210705, 'Monday Independence Day'],
                [20210906, 'Monday Labor Day'],
                [20211125, 'Thursday Thanksgiving Day'],
                [20211224, 'Friday Christmas Day'],
                [20211225, 'Saturday Christmas Day'],
                [20211231, 'Friday New Years Day'],
                [20220101, 'Saturday New Years Day'],
                [20220117, 'Monday MLK Day'],
                [20220221, 'Monday Presidents Day'],
                [20220415, 'Friday Easter Friday'],
                [20220530, 'Monday Memorial Day'],
                [20220704, 'Monday Independence Day'],
                [20220905, 'Monday Labor Day'],
                [20221124, 'Thursday Thanksgiving Day'],
                [20221225, 'Sunday Christmas Day'],
                [20221226, 'Monday Christmas Day'],
                [20230101, 'Sunday New Years Day'],
                [20230102, 'Monday New Years Day'],
                [20230116, 'Monday MLK Day'],
                [20230220, 'Monday Presidents Day'],
                [20230407, 'Friday Easter Friday'],
                [20230529, 'Monday Memorial Day'],
                [20230704, 'Tuesday Independence Day'],
                [20230904, 'Monday Labor Day'],
                [20231123, 'Thursday Thanksgiving Day'],
                [20231225, 'Monday Christmas Day'],
                [20240101, 'Monday New Years Day']]

    expected = [yyyymmdd2dt(i).date() for i, j in expected]
    d = yyyymmdd2dt(20140101).date()
    flag = True
    for i in range(3657):
        if is_holiday_observed(d, weekend_f=False):
            if d not in expected:
                flag = False

        d = d + datetime.timedelta(days=1)

    return flag


def most_recent_business_day(d):
    d = to_date(d)
    while is_holiday_observed(d):
        d -= datetime.timedelta(days=1)
    return d


def prior_business_day(d):
    d -= datetime.timedelta(days=1)
    return most_recent_business_day(d)


def lbd_of_month(d):
    y = d.year
    m = d.month
    if m == 12:
        d = datetime.date(y + 1, 1, 1)
    else:
        d = datetime.date(y, m + 1, 1)

    return prior_business_day(d)


def is_lbd_of_month(d):
    return d == lbd_of_month(d)


def lbd_prior_month(d):
    d = datetime.date(d.year, d.month, 1)
    d -= datetime.timedelta(days=1)
    return lbd_of_month(d)
