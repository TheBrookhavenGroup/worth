import re
import datetime
import pytz
from django.conf import settings


def our_now():
    # This results in a time that can be compared values in our database
    # even if saved by a human entering wall clock time into an admin field.
    # This is in the time zone specified in settings, for us it is 'America/New_York'.
    return datetime.datetime.now(tz=pytz.timezone(settings.TIME_ZONE))


def yyyymmdd2dt(d):
    tz = pytz.timezone(settings.TIME_ZONE)
    dt = datetime.datetime.strptime(str(d), '%Y%m%d')
    return tz.localize(dt)


def dt2dt(dt):
    tz = pytz.timezone(settings.TIME_ZONE)
    dt = datetime.datetime.fromisoformat(dt)
    return tz.localize(dt)


# Taken from http://pleac.sourceforge.net/pleac_python/numbers.html
commify_re = re.compile(r"(\d\d\d)(?=\d)(?!\d*\.)")


def commify(x, sci_f=False):
    if sci_f:
        return f"{float(x):.3e}"
    x = str(x)
    x = x[::-1]  # Reverse the string
    x = commify_re.sub(r"\1,", x)
    return x[::-1]


# symbol could be None, $, or %
x_inf = float('inf')
x_nan = float('nan')


def cround(x, p=2, w=0, symbol=None, nsig=None):
    if str == type(x):
        return x

    if x is None:
        return 'N/A'
    if list == type(x) or tuple == type(x):
        return [cround(i, p, w, symbol, nsig) for i in x]

    if x == x_inf:
        return 'inf'
    if x == x_nan:
        return 'nan'

    if '%' == symbol:
        x *= 100.0

    magnitude = None
    sci_f = False
    if symbol != '#':
        trillion = 1.0e12
        billion = 1.0e9
        million = 1.0e6
        if x >= trillion:
            sci_f = True
        elif x >= billion:
            x /= billion
            magnitude = 'B'
        elif x >= million:
            x /= million
            magnitude = 'M'

    if nsig is not None:
        p = nsig
    y = round(x, p)
    y = str(y)
    if ('inf' == y) or ('nan' == y):
        return y
    whole_part, frac_part = y.split('.')
    if 0 == p:
        y = whole_part
    else:
        pp = p
        if nsig is not None:
            if x < 0.0:
                nsig += 1
            z = nsig - len(whole_part)
            if z <= 0:
                pp = 0
            else:
                pp = z
        frac_part = frac_part.ljust(pp, '0')[:pp]
        y = whole_part + '.' + frac_part if len(frac_part) else whole_part
    if magnitude is not None:
        y += magnitude
    y = commify(y, sci_f=sci_f)
    if '%' == symbol:
        y = y + '%'
    if '$' == symbol:
        if x < 0:
            y = y.replace('-', '-$', 1)
        else:
            y = '$' + y
    y = y.rjust(w, ' ')

    return y


def is_near_zero(x, epsilon=1E-10):
    y = abs(x)
    return y < epsilon


def is_not_near_zero(x, epsilon=1E-10):
    return not is_near_zero(x, epsilon=epsilon)
