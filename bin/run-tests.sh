#!/bin/bash

urlwait
bin/run-common.sh
py.test --junitxml=test-results/test-results.xml
