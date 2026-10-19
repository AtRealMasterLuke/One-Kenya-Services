"""Print a session cookie for a demo account, so Lighthouse can audit signed-in pages
without scripting a login.   python manage.py shell < scripts/make_session.py"""

import os

from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore

from accounts.models import User

user = User.objects.get(phone=os.environ.get("SESSION_PHONE", "+254700000001"))
session = SessionStore()
session[SESSION_KEY] = str(user.pk)
session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
session[HASH_SESSION_KEY] = user.get_session_auth_hash()
session.create()
print(f"SESSION={session.session_key}")
