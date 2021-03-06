#!/usr/bin/env python
import os
import site
import sys


ROOT = os.path.dirname(os.path.abspath(__file__))

path = lambda *a: os.path.join(ROOT, *a)

prev_sys_path = list(sys.path)

site.addsitedir(path('libs'))
site.addsitedir(path('vendor'))

# Move the new items to the front of sys.path. (via virtualenv)
new_sys_path = []
for item in list(sys.path):
    if item not in prev_sys_path:
        new_sys_path.append(item)
        sys.path.remove(item)
sys.path[:0] = new_sys_path

# No third-party imports until we've added all our sitedirs!
from django.core.management import execute_from_command_line

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    execute_from_command_line(sys.argv)
