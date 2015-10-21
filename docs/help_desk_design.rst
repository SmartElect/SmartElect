.. _help_desk_design:

Design/Users Guide for the Help Desk
====================================

User Interface
--------------

When the operator answers a call, they'll start a new case (probably
clicking a big obvious button or link). A case will be created and the
operator and start time recorded in it.

As the operator works on the call, they'll see (at least) two areas on
their screen. One will show the data accumulated so far on the call -
e.g. the caller's phone number, name, voter name, are they field staff,
etc. To keep things simple, data not gathered yet will not show up as
a field that's empty; only fields we have data for will be displayed.

This area might also display other information associated with the
caller or staffer, like where the voter is currently registered, or
their mother's name, that are not necessarily stored in the case.

There may also be some indication of what phase the call is in. This
might be something like "gathering initial data", "validating caller",
"asking if caller wants to change their registration".  Or maybe this
should be the heading in the second area?

The second major area of the screen will be the area the operator
interacts with during the call. It will always include instructions to
the operator as to what to do next (usually, "ask the caller ....").
It will then accept input based on what happened - maybe entering the
caller's response, or the operator indicating that the user gave a
valid response, whatever is appropriate. There will also always be a
way to indicate things like "the caller just hung up", which will close
the interface on that case (as far as the operator is concerned).

Detailed flow chart
-------------------

TBD

Cases
-----

Each time an operator receives a call and starts processing it
in the help desk site, a new "case" will be created to capture
all the information about that call and its eventual resolution.

Some information that cases can contain:

* operator who took the call
* start time, end time
* current status of the case
* voter
* field staffer, if they were the caller
* answers given to operator questions
* whether marked for review by senior staff, with classification and comments
* final outcome

User types
----------

These are the kinds of users we're concerned with. Really there's only
one kind of user, but they could have different sets of permissions.
We'll implement individual permissions for each kind of thing that
a user might or might not be allowed to do, then have groups that
grant the desired set of permissions, e.g. a "Help desk operators"
group and a "Field staff" group.

* Help desk operator

    * Can access the help desk pages of the site ('help_desk.add_case')
    * Can create cases and update them per the flow chart
      ('help_desk.add_case', 'help_desk_change_case', 'help_desk.read_case')

Question: who can create/change help desk operator accounts?

* Field staff

    * Not a web site user. Just a record in the help desk app.
    * Have a Staff ID number.
    * Are linked to a particular phone number.

* Supervisor

    * Can cancel the window in which a voter is being allowed to
      change their registration, iffi they haven't already changed it
      ('help_desk.cancel_registration_change')
    * Can mark a case for "attention by senior staff review" with
      drop-down classification and comments.
      ('help_desk.mark_case')

* Senior staff

    * view reporting tools ('help_desk.read_report')
    * view cases ('help_desk.read_case')
    * set a recommended action on cases marked for senior staff review
      ('help_desk.recommend_case')

* View-only

    * view reports ('help_desk.read_report')
    * view cases ('help_desk.read_case')
    * (cannot make any changes to any information)

* Help desk manager

    * Create Field staff IDs ('help_desk.add_fieldstaff')
    * Mark field staff IDs as suspended ('help_desk.suspend_fieldstaff')
    * Ability to create/delete/reset passwords for help desk staff
      (help_desk.change_staff_password)
    * Ability to create supervisor accounts. ('help_desk.add_supervisor')
    * Ability to create senior staff review accounts.
      ('help_desk.add_senior_staff')
    * Ability to create view-only accounts ('help_desk.add_viewonly')

Reports
-------

Requirements for reports:

* Display the number of calls for different time periods.
* Screen to display cases with the stage they are in, call centre staff user, outcome. Screen to be filterable by time – currently active, up to last hour, up to today.
* Ability to select a case to see further details on actions and outcomes to questions.
* Ability to view number of cases by call centre staff user, for different timeframes, sub-classified by type of outcome.
* Ability to view average length of case completion by call centre staff user, for different timeframes, sub-classified by type of outcome.
* Screens should differentiate between citizen calls and staff calls.

For cases of staff calling:

* Screen to display number of call per field staff member, and types of calls/outcomes.

Reports
=======

The report page has two links at the top to switch between a view
of individual cases and a view presenting statistics.

Individual cases page
---------------------

Screen::

       *Select cases to include*

         Time:  o Started today   o Started within the last hour  o Currently active
             o This week   o This month  o ALL
             o Dec 2013 o Jan 2014  o Feb 2014  o Mar 2014 ... (months in the last year that have any data)
             o 2014   o 2013 ... (years that have any data)
             From:  __YYYY-MM-DD_HH:SS__ - __YYYY-MM-DD_HH:SS__   (updated by radio buttons, or user can edit directly)
         Call made by:   o Any  o Citizen  o Field staff
         Call outcome:   _ Outcome A  _ Outcome B  _ Outcome C ... | Select all | Select None

       Click on case number for case details

       Case # | State    |  Operator  | Field Staff | Outcome
       _1_      Get NID    John Smith        n/a         n/a
       _2_      Complete   Fred Dobbs     Jane Doe     Registration unlocked
       ...


Statistics page
---------------

Screen::

       *Select cases to include*

         Time:  o Started today   o Started within the last hour  o Currently active
             o This week   o This month  o ALL
             o Dec 2013 o Jan 2014  o Feb 2014  o Mar 2014 ... (months in the last year that have any data)
             o 2014   o 2013 ... (years that have any data)
             From:  __YYYY-MM-DD_HH:SS__ - __YYYY-MM-DD_HH:SS__   (updated by radio buttons, or user can edit directly)
         Call made by:   o Any  o Citizen  o Field staff
         Call outcome:   _ Outcome A  _ Outcome B  _ Outcome C ... | Select all | Select None

       *Group by*

            o Days of the week (Monday, Tuesday, Wednesday, ...)
            o Hours (0:00-0:59, 1:00-1:59, ...)
            o Day (Jan 1, Jan 2, ...)
            o Week (Jan 1-7, Jan 8-14, ...)
            o Month (Jan, Feb, Mar, ...)
            o Operator
            * Field staff

       *Select data to show in table*

         o Number of cases
         o Average length of calls

      Report example if grouping by day:

          Day    | Outcome A | Outcome B | ... | Any
          Sunday      2           3              25
          Monday      0           4              37
          ...
          Saturday    0           1              18
          Total      18          15             537

          The first row aggregates data from all the Sundays in the reporting period,
          the second row from Mondays, and so forth.

          The report can also be grouped by hour, showing how many calls happened from 0:00-0:59,
          how many from 1:00-1:59, and so on.

      Report example if grouping by week:

          Week     | Outcome A | Outcome B | ... | Any
          Jan 1-7
          Jan 8-14
          ...
          Total

          When grouping by day, week or month, clicking a time period will go to a report
          listing the individual cases within that time period that satisfy the other
          criteria currently selected.  E.g. if viewing a report of cases from all year,
          made by field staff, with any outcome, grouped by week, then clicking on "Jan 1-7"
          might go to an individual case report listing cases from Jan 1 to Jan 7,
          made by field staff, with any outcome.


Managing staff
--------------

* Create new account
* Grant privileges to existing user accounts that aren't currently help desk staff
* Manage privileges, password of current help desk staff
