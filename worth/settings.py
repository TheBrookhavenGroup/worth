import os
from pathlib import Path
import configparser
from tbgutils import dt as mc_dt

config_file = '/Users/ms/.worth'
if os.path.exists(config_file):
    config = configparser.ConfigParser(interpolation=None)
    config.read('/Users/ms/.worth')
    IB_FTP_USER = config['IB']['IB_FTP_USER']
    IB_FTP_PW = config['IB']['IB_FTP_PW']
    IB_FTP_SERVER = config['IB']['IB_FTP_SERVER']
    IB_FLEX_TOKEN = config['IB']['IB_FLEX_TOKEN']
    IB_DEFAULT_ACCOUNT = config['IB']['IB_DEFAULT_ACCOUNT']

    PPM_FACTOR = float(config['GENERAL']['PPM_FACTOR'])
    USE_PRICE_FEED = config['GENERAL']['USE_PRICE_FEED'].lower() == 'true'

    GPG_EMAIL = config['GPG']['GPG_EMAIL']
    GPG_HOME = config['GPG']['GPG_HOME']
    GPG_PASS = config['GPG']['GPG_PASS']

    SECRET_KEY = config['DJANGO']['SECRET_KEY']

    POSTGRES_USER = config['POSTGRES']['USER']
    POSTGRES_PASSWORD = config['POSTGRES']['PASS']
    POSTGRES_DB = config['POSTGRES']['DB']

    # SECURITY WARNING: don't run with debug turned on in production!
    DEBUG = config['DJANGO']['DEBUG'].lower() == 'true'
else:
    # This should only be used in github action ci_testing.yml.
    POSTGRES_USER = os.environ['POSTGRES_USER']
    POSTGRES_PASSWORD = os.environ['POSTGRES_PASSWORD']
    POSTGRES_DB = 'worth_test'
    GPG_HOME = None
    GPG_PASS = None
    GPG_EMAIL = 'you@example.com'
    PPM_FACTOR = 1

# Build paths inside the worth like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

ALLOWED_HOSTS = ['127.0.0.1']

INSTALLED_APPS = [
    'worth.apps.AdminConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'crispy_forms',
    'crispy_bootstrap4',
    'easyaudit',
    'accounts',
    'markets',
    'trades',
    'analytics',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'easyaudit.middleware.easyaudit.EasyAuditMiddleware',
]

ROOT_URLCONF = 'worth.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'worth/templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

CRISPY_TEMPLATE_PACK = 'bootstrap4'

DJANGO_EASY_AUDIT_WATCH_REQUEST_EVENTS = False
DJANGO_EASY_AUDIT_WATCH_AUTH_EVENTS = False
DJANGO_EASY_AUDIT_UNREGISTERED_CLASSES_EXTRA = [
    'auth.User',
    'auth.Group',
    'auth.Permission',
    'sessions.Session',
    'accounts.Account',
    'accounts.Receivable',
    'accounts.Vendor',
    'markets.Market',
    'markets.Ticker',
    'markets.DailyPrice',
    'markets.DailyPrice',
    'markets.TBGDailyBar',
    'analytics.PPMResult',
]

WSGI_APPLICATION = 'worth.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'worth',
        'HOST': '127.0.0.1',
        'PORT': 5432,
        'USER': POSTGRES_USER,
        'PASSWORD': POSTGRES_PASSWORD,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation'
                '.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation'
                '.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation'
                '.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation'
                '.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True
mc_dt.time_zone = TIME_ZONE

STATIC_URL = 'static/'
STATIC_ROOT = 'static/'
#STATICFILES_DIRS = ['static/']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DATA_UPLOAD_MAX_NUMBER_FIELDS = None
