import os
from os import environ as env
from pathlib import Path
from moneycounter import dt as mc_dt


IB_FTP_USER = env.get('IB_FTP_USER')
IB_FTP_PW = env.get('IB_FTP_PW')
IB_FTP_SERVER = env.get('IB_FTP_SERVER')
IB_FLEX_TOKEN = env.get('IB_FLEX_TOKEN')

PPM_FACTOR = eval(env.get('PPM_FACTOR', 'False'))
USE_PRICE_FEED = eval(env.get('USE_PRICE_FEED', 'True'))

# Build paths inside the worth like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = \
    'django-insecure-dt@hl9)ewrj!wdwrja6$#%&yx(g-*yp*ke*kcpdf8+x&*or1^='
SECRET_KEY = env.get("DJANGO_SECRET_KEY", SECRET_KEY)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1']

INSTALLED_APPS = [
    'worth.apps.AdminConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
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


WSGI_APPLICATION = 'worth.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'worth',
        'HOST': '127.0.0.1',
        'PORT': 5432,
        'USER': 'postgres',
        'PASSWORD': 'postgres',
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
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
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'worth/static')
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
