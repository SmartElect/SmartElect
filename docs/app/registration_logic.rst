.. _registration_logic:

Libyan Voter Registration - Tool 1 Logic
========================================

Last update: Friday, September 12, 2014

Tool 1 processes messages sent to 15015 (or 10020 on the test servers).

The handlers look at the incoming message in this order.

The first handler whose conditions are satisfied will handle the message, and no further handlers will be involved.

As soon as a handler responds to the message, the processing ends.

Any change request should explain the new logic at the same level of detail.

ANYTIME
-------

1. Before ANY of the following Handlers begin evaluating

   * Checks if message is sent to 15015 or 21815015

      * If not, allows message to pass to other Tools

   * Checks if number is on Blacklist

      * If yes, respond with BLACKLISTED_NUMBER

   * If all above checks succeed then proceed to following Handlers

1.  VoterQueryCitizenLookupHandler

   * Conditions

      * Message format “NID” where NID is the right length

   * Processing

      * if national ID not in our Citizen table

          * respond VOTER_QUERY_NOT_FOUND

      * if Citizen has confirmed registrations

         * if exactly 1 confirmed registration

            * respond VOTER_QUERY_REGISTERED_AT with registration data

         * else (more than 1 confirmed registration!  this should never happen, but...)

            * respond VOTER_QUERY_PROBLEM_ENCOUNTERED

      * respond VOTER_QUERY_NOT_REGISTERED

1. WrongLengthNIDHandler

   * Conditions

      * Message format “digits”

   * Processing

      * respond VOTER_QUERY_NID_WRONG_LENGTH

(Note: if none of these handlers match, then it doesn't look much like a voter
query, and the message will pass on to the registration handler, below.)


BEFORE AND DURING REGISTRATION
------------------------------

Common code: every handler, if a message matches its conditions, starts with this code and if this code generates a response, that ends handling:


1. Before ANY Handler begins evaluating

   * Checks if message is sent to 15015 or 21815015

      * If not, lets message pass to other Tools (Tool 1.5, etc)

   * Checks if number is on Blacklist

      * If yes, respond with BLACKLISTED_NUMBER

   * Checks if registration is allowed:

      * A registration period is open, or
      * Message has the ``registration_allowed`` flag (set by the ``voting`` app)
      * If none of the above, respond with REGISTRATION_NOT_OPEN

   * If all above checks succeed then proceed to following Handlers

1. RegistrationMessageHandler

   * Conditions

      * Message format “NID*CENTERID” with the right field lengths

   * Processing

      * If no center with CENTERID:

         * respond RESPONSE_CENTER_ID_INVALID

      * if no Citizen in our Citizen table with NID:

         * respond RESPONSE_NID_INVALID

      * if Citizen not eligible (not 18, blocked, etc):

         * respond RESPONSE_NID_INVALID

      * if Citizen already has a registration:

         * if it’s from the same phone they’re sending from now, or the registration is ``unlocked``:

            * if they have no changes remaining:

               * respond MESSAGE_6 ({person}, we have registered you at {centre} with Election Center Number {code}.  If this is incorrect or you need to change your Election Center, you must go to the Election Center you wish to vote at in person during the Addition and Amendments Period.)

            * if CENTERID matches their existing registration

               * increment their “done this already” counter
               * if they’ve already done this 3 or more times

                  1. respond MESSAGE_1_5

               * respond MESSAGE_1

            * They are changing their center. Increment their change count
            * reset their “done this already” count
            * update their registration to the new center
            * if registration was ``unlocked``, lock it now.
            * if no remaining changes now:

               * respond MESSAGE_5 ({person}, you have changed your Election Center to {centre}. If you want to change your Election Center again, you must go to the Election Center you wish to vote at in person during the Addition and Amendments Period.)

            * else if 1 remaining change:

               * respond MESSAGE_4 ({person}, you have changed your polling center to {centre}. You may change your polling center only one more time by SMS.)

            * else:

               * respond MESSAGE_1 ({person}, we have registered you at {centre}. The Election Center Number is {code}. If this is incorrect or you wish to change your registration, please resubmit using this phone number.)

         * else (it’s from a different phone)

            * if CENTERID matches their existing registration

               * respond MESSAGE_7 (Sorry, this NID is already registered at {centre} with a phone ending in {number}. You must use this phone to re-register. If you do not have access to this phone or need help, call 1441.)

            * respond MESSAGE_2   # can’t change reg from a different phone  (Sorry, this NID is already registered at {centre} with a phone ending in {number}. You must use this phone to re-register. If you do not have access to this phone or need help, call 1441.)

      * else: (no existing registration)

         * create new registration
         * respond RESPONSE_VALID_REGISTRATION

1. WrongNIDLengthHandler

   * Conditions

      * Message format “digits*CENTERID” where CENTERID is the right length

   * Processing

      * Respond RESPONSE_NID_WRONG_LENGTH

1. WrongCenterIDLengthHandler

   * Conditions

      * Message format “NID*digits” where NID is the right length

   * Processing

      * respond RESPONSE_CENTER_ID_WRONG_LENGTH

1. DefaultHandler

   * Conditions

      * Message doesn't match any of the above patterns

   * Processing

      * Respond MESSAGE_INCORRECT
