#!/bin/sh
set -ex

flake8 .

coverage erase
python manage.py makemigrations --dry-run --check --settings=libya_elections.settings.dev
coverage run manage.py test --keepdb --noinput --settings=libya_elections.settings.dev "$@"
coverage report -m --skip-covered --fail-under 85
