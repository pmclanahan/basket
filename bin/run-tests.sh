#!/bin/sh

./bin/wait-for-db.sh || exit 1
./bin/run-common.sh
py.test news

