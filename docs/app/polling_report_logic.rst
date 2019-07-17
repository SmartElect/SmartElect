.. _polling_report_logic:

Libyan Voter Registration - Polling report Logic
==================================================

Last update: Thursday, December 11, 2014

The polling report tool processes messages sent to 10030

Notes:

1) See message_formats.rst for the message formats that are
   processed on 10030.

2) The phone activation period is from midnight, two days before polling starts,
   to the end of polling.

3) The center opening period is from midnight, two days before polling starts,
   to the end of polling.

4) The polling reporting period is from the time polling starts until 16 hours
   after polling ends.

5) The preliminary vote count submitting period is the same as the polling
   reporting period.

Logic:

    If phone number is not whitelisted:
        respond NOT_WHITELISTED_NUMBER
    else if phone number is not activated:
        if phone activation period is not active:
            respond POLLING_NOT_OPEN
        else if message format is not two numbers:
            respond PHONE_NOT_ACTIVATED
        else if the two center numbers in the message don't match:
            respond POLLING_REPORT_CENTER_MISMATCH
        else if there's no center with that number:
            respond INVALID_CENTER_ID
        else if the center with that number is not active:
            respond INVALID_CENTER_ID
        else:
            Activate the calling phone for the specified center
            Mark the center open at the current time
            respond PHONE_ACTIVATED
    else (phone number has been activated already):
        if message has two numbers:
            if the first number is 0:
                (this is a center opening message)
                if center opening period is not active:
                    respond POLLING_NOT_OPEN
                else if there's no center with that number:
                    respond INVALID_CENTER_ID
                else if second number != the center the phone's registered at:
                    respond CENTER_OPENING_NOT_AUTHORIZED
                else:
                    Mark the center open at the current time
                    respond CENTER_OPENED
            else if the polling report period is not open:
                respond POLLING_NOT_OPEN
            else if the first number is NOT between 1 and 4:
                respond POLLING_REPORT_INVALID
            else:
                Save the polling report data
                if turnout exceeds 90%:
                    respond POLLING_REPORT_RECEIVED_VERY_HIGH_TURNOUT
                else if the center has no registrants:
                    respond POLLING_REPORT_RECEIVED_NO_REGISTRANTS
                else:
                    respond POLLING_REPORT_RECEIVED
        else if the message has three numbers and the first number is 5:
            if polling report period is not open:
                respond POLLING_NOT_OPEN
            else if there's no election in progress:
                respond POLLING_NOT_OPEN
            else:
                Save the preliminary vote counts
                respond PRELIMINARY_VOTES_REPORT
        else:
            respond POLLING_REPORT_INVALID
