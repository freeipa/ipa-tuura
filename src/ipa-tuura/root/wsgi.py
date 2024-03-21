#
# Copyright (C) 2024  FreeIPA Contributors see COPYING for license
#

"""
WSGI config for root project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/wsgi/
"""

import os
import sys

from django.core.wsgi import get_wsgi_application

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../root")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "root.settings")

application = get_wsgi_application()
