import os
from pathlib import Path
from dotenv import load_dotenv # Ensure this is imported

# Load environment variables from .env file
load_dotenv() # This line ensures .env is loaded for all management commands

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# WARNING: Change this in production! Use environment variables or a secret management system.
# Example for development:
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-your-secret-key-here')

DEBUG = True

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages', # Essential for Django's messaging framework
    'django.contrib.staticfiles', # Essential for serving static files like DRF's CSS
    'rest_framework',           # Django REST Framework
    'corsheaders',              # Django CORS Headers
    'api',                      # Your API app (assuming this is where your views/models are)
    'background_task',          # Background task processing
    'channels',                 # Django Channels
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # ✅ ADD THIS LINE
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware', # CORS middleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'betting_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # ADDED: This tells Django to look for templates in a 'templates' folder
        # at the root of your project (next to manage.py and betting_project folder)
        'DIRS': [BASE_DIR / 'templates'], 
        'APP_DIRS': True, # This allows Django to look for templates inside each app's 'templates' folder
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages', # Corrected path for messages context processor
            ],
        },
    },
]

# ASGI application for Django Channels
ASGI_APPLICATION = 'betting_project.asgi.application' # <--- New setting

# Channel Layer configuration (using Redis)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [os.environ.get('REDIS_URL', 'redis://localhost:6379/0')], # <--- New setting
        },
    },
}

WSGI_APPLICATION = 'betting_project.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
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

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'

# This tells Django to look for static files in a 'static' folder
# at the root of your project (next to manage.py and betting_project folder)
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# The directory where `collectstatic` will gather all static files for deployment.
# It's good practice to define this even in development.
STATIC_ROOT = BASE_DIR / 'staticfiles' # <--- NEW LINE

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS Headers Configuration
CORS_ALLOW_ALL_ORIGINS = True # For development, allows all origins.
# In production, change to CORS_ALLOWED_ORIGINS = ['http://localhost:3000', 'https://your-react-app-domain.com']
# Or use CORS_ALLOW_ALL_ORIGINS = False and define CORS_ALLOWED_ORIGIN_REGEXES

# BCH Wallet Configuration (for Testnet) - No longer directly used in this generic setup
# WARNING: NEVER hardcode private keys in production! Use environment variables.
# This is a TESTNET private key. Get one from a testnet faucet.
# Example: "cNfsAACYiXk1c1h4qXj2P2pM5rGq9j8h7g6f5e4d3c2b1a0" (replace with your actual testnet WIF)
# BCH_WALLET_WIF = os.environ.get('BCH_WALLET_WIF', 'L5Y6pTRnLYn7bKec11Xu7MgqT5XmjQMFDvgn6WmCHHcEhZaoQ2Kq')


# LOGGING configuration for detailed console output
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG', # Set to DEBUG to see all messages
            'class': 'logging.StreamHandler',
            'formatter': 'simple', # Use simple formatter for cleaner console output
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO', # Django's general logs
            'propagate': False,
        },
        'background_task': { # Logger for django-background-tasks
            'handlers': ['console'],
            'level': 'DEBUG', # Set to DEBUG to see detailed task execution logs and errors
            'propagate': False,
        },
        'api': { # Logger for your api app
            'handlers': ['console'],
            'level': 'DEBUG', # Set to DEBUG to see your custom logger messages
            'propagate': False,
        },
        'channels': { # <--- Add Channels logger
            'handlers': ['console'],
            'level': 'INFO', # Can set to DEBUG for more verbosity
            'propagate': False,
        },
        # Add other loggers if needed
    },
    'root': { # Catch-all logger
        'handlers': ['console'],
        'level': 'WARNING', # Default level for anything not explicitly configured
    }
}
