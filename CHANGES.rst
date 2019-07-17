Summary of Changes for SmartElect
=================================

2019-07-17 (v2.0)
-----------------

* Reorganize documentation

2019-05-03
----------

* Upgrade to Django 2.2
* Upgrade to Celery 4
* Upgrade to Python 3 (specifically 3.6)
* Disable server side cursors
* Search for registrations by phone number
* Add column to allow ordering users by date
* Add form fields to allow limiting some reports by date
* Allow for date-based expiration of staff users
* Add registrations by center report
* Add registrations by phone number report
* Fix total row in call reports
* Use Python locale settings to format dates
* Allow characters in FBR number field
* Add registration date to help desk screen
* Show staff link to all groups
* Limit registrations to 2 NIDs per phone
* Add daiily totals by subconstituency to CSV report
* Help desk: close open calls when starting a new call
* Show today instead of yesterday in dashboard tables
* Make sorting more stable so pagination works properly

2017-12-05
----------

* Send logging errors to Sentry
* Fix error due to unsaved SMS
* Help desk: Add field to record caller's phone number
* Handle missing citizens in changesets
* Include missing records when mirroring DBs
* Allow public dashboard to be turned off.
* Use the whitelist on testing to prevent accidental outgoing SMS
* Fix --keepdb
* Fix audit trail to deal with new format
* Upgrade to Django 1.8 LTS
* Gracefully handle upload of non-CSV file for registration centers
* Make registration period and staff phone delete pages show registration period dates
* Validate phone numbers to make sure they don't start with '2180'
* Support locale-based date formats
* Switch to Libyan date format on Message Tester page
* Ensure the help desk call time is no longer than 1 hour
* Ensure errors in django_bread properties propagate, and fix them in the citizen read view and election read view
* Correct conditional logic in showing fields on changeset edit page
* Add changesets to main navigation
* Speed up loading of the registration browse page
* Ensure uniqueness of non-deleted blacklist and whitelist numbers

2016-08-29
----------

* Change from TravisCI to CircleCI
* Add tools for limiting registration to subcons and freezing registrations
* Upgrade kombu

2015-10-21 (v1.0)
-----------------

* Initial open source release of SmartElect
