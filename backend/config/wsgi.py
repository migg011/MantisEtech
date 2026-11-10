"""Expõe a aplicação WSGI para servidores como Waitress; não inicia o Angular."""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_wsgi_application()
