#!/bin/bash

# This utility runs the standard rollgen tests, but with two special environment variables
# set (ROLLGEN_TEST_SUBCONSTITUENCY_NAME and ROLLGEN_TEST_CENTER_NAME). They're set to
# the longest subcon and center names (respectively) in the database.
# The rollgen test code is aware of these environment variables and will set the names of the
# subcon and center used in almost all of its tests to the names in these environment variables.
#
# The practical benefit is that one can run this test at any time to ensure that the current data
# (presumably in the production database, but any one will do) does not break rollgen formatting.

set +x

echo "This might take a minute, especially if you're connected to a remote database."

python manage.py rollgen_find_longest_name subconstituencies --filename=_rollgen_test_subconstituency.txt

if [ $? -ne 0 ]; then
	echo "manage.py failed."
	exit
fi

export ROLLGEN_TEST_SUBCONSTITUENCY_NAME=$(<_rollgen_test_subconstituency.txt)

python manage.py rollgen_find_longest_name centers --filename=_rollgen_test_center.txt

if [ $? -ne 0 ]; then
	echo "manage.py failed."
	exit
fi

export ROLLGEN_TEST_CENTER_NAME=$(<_rollgen_test_center.txt)

python manage.py test rollgen


