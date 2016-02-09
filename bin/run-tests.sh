#!/bin/sh
set -ex

urlwait
./bin/run-common.sh
py.test news

