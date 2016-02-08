#!/bin/sh

# wait 10s for mysql to start
if ! nc -zw 10 db 3306; then
  echo "Can't connect to db on 3306"
  exit 1
fi
