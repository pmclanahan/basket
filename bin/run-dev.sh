#!/bin/sh

./bin/wait-for-db.sh || exit 1
./bin/run-common.sh
./manage.py runserver 0.0.0.0:8000

