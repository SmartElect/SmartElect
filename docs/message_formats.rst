Message formats
===============

10010
-----

Voter self-registration
~~~~~~~~~~~~~~~~~~~~~~~~

NID:  query registration
NID#CENTER_ID:  register

10030
-----

Polling day reports
~~~~~~~~~~~~~~~~~~~

CENTER_ID#CENTER_ID: phone activation

0#CENTER_ID: morning check-in (phone must be activated to CENTER_ID)

PERIOD_NUMBER#NUM_VOTERS: Polling report - for period "PERIOD_NUMBER",
 there were "NUM_VOTERS" voters.  (PERIOD_NUMBER must be 1-4.)

5#1#VOTES1#VOTES2: Quick preliminary count of votes for options 1 and 2
 (which might be a 2-candidate election, or Yes or No on a referendum).
 This assumes the whole country/election has the same 2 choices.
