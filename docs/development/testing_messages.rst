.. _testing_messages:

Testing Messages
================

There are 3 ways in which we can manually test that our system provides the correct response to
incoming messages.

1. Web Message Tester:

   This is only available to superusers on testing, and not on production. Staff users can send arbitrary messages
   to any of the short codes assigned to that instance. For testing, the available shortcodes are
   currently 10020, 10040 and occasionally 10050 (depending on how 10050 is configured). The user
   can also vary their ``from_number`` as desired. The Web Message Tester will send the specified
   message to the specified shortcode, pretending to be originating from the specified phone number.
   The system's response will be shown in the application and will also be present in the SMS model.
   In the SMS logs, they will be associated with a carrier of ``message_tester``.

2. Android Message Tester:

   Note: As of May 2019, these phones are no longer available.

   HNEC has installed 2 android phones, one with a Libyana SIM and one with an Al-Madar SIM.
   `MightyText <http://mightytext.net>`_ is installed on each phone. Each phone is associated with a
   Gmail account, and the credentials are in LastPass.

   a. Login to Gmail, using the credentials of one of the accounts.
   b. Go to mightytext.net and click the Login button. It should show you a list of all the Gmail
      accounts that you're currently logged into. Choose one of the HNEC accounts.
   c. Click the big red 'New Message' button and send a message to the shortcode of your choice.

   The limitation of this approach is that the ``from_number`` is fixed, so it's not possible to
   test scenarios requiring different incoming phone numbers. On the other hand, this does test the
   entire network stack, from the phone to the MNO to Vumi to our application, and back.

   .. WARNING::

      This allows messages to be sent to the production servers, so if you send registration
      messages with valid NIDs and center codes, you will create valid registrations. This tool is
      meant ONLY to test the network stack and make sure that a proper default response is sent.
      Manual testing of application logic should be done using the Web Message Tester above.

3. HNEC staff phones:

   Staff in Libya can send messages from their phones to shortcodes and test responses. This should
   also only be done with the testing shortcodes.
