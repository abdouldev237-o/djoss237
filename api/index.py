import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.core.management import call_command
try:
    call_command('migrate', '--noinput')
except:
    pass

from config.wsgi import application as app