#!/bin/sh
set -ex

flake8 .

rm -f .coverage
coverage run manage.py test --noinput --settings=libya_elections.settings.dev "$@"
coverage report
