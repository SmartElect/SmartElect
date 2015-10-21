.. _code_overview:

Code Overview
=============

There are a lot of directories in this repository. Here's a map to what they're for.

Translation
-----------

.tx
    Configuration files for Transifex. Used for translating the user interface.
locale
    The gettext files containing messages and their translations.

Also see the `text_messages` Django application and :ref:`translation`.

Deploying
---------

conf
    Files used for deploying to servers.  See also :ref:`deployment`.

Documentation
-------------

docs
    Where files like this one live


Project directory
-----------------

libya_elections
   Has settings, core utilities, the main URL files, and other things that are used by
   multiple of the Django applications that make up the system.

Django applications
-------------------

audit
    Verify that SMS messages aren't getting lost between points inside the system
bulk_sms
    Send bulk SMS messages
changesets
    Make batch changes to registrations, with approval and tracking.
civil_registry
    The citizen database. See also :ref:`civil_registry`.
help_desk
    Support telephone-based help for citizens.
    See also :ref:`help_desk_design`.
httptester
    Internal tool to send test messages and see what response is returned
libya_site
    The public face of the site
load_test
    Internal tool used for load testing
polling_reports
    Gather data and report on polling during elections.
    See also :ref:`polling_report_logic`.
register
    Voter registration.  See also :ref:`registration_logic`
    and :ref:`registration_locations`.
reporting_api
    Provide a "REST" API that returns some election data
rollgen
    Print voter rolls for use in polling places
sms_status
    Report on the status of SMS-based voting
staff
    Staff-specific pages, like managing who can access internal areas
    of the site
subscriptions
    Manage subscriptions to email notices about things like auditing issues.
text_messages
    Change the text and translations of the text messages that the system sends.
    See :ref:`sms_responses`.
voting
    SMS voting. See also :ref:`sms_voting_logic`.
vr_dashboard
    Voter registration dashboard - public reports and graphs tracking the progress
    of voter registration
