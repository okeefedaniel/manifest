"""WSGI config for Manifest standalone deployment."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manifest_site.settings')
application = get_wsgi_application()
