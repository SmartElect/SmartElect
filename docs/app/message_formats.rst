Message formats
===============

15015
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

5#OPTION#NUMBER_OF_VOTES: Preliminary count of votes for an option
(e.g. yes/no) or candidate.
This assumes the whole country/election has the same choices.
