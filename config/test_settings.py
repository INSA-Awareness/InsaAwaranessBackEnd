import os
import sys

os.environ["DATABASE_URL"] = ""

for mod in list(sys.modules.keys()):
    if "config" in mod and mod != "config.test_settings":
        del sys.modules[mod]

from config.settings import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "test_db.sqlite3"),
    }
}
