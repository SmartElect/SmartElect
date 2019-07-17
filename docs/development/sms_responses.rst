.. _sms_responses:

SMS Responses
=============

The text and translations of our SMS response messages are handled
differently from the rest of the text in this project. (See
translation.rst for more on the other text.)

Instead of having the English text in the code, and the translations
managed via gettext and Transifex, we have all the text and translations
of the SMS messages we send stored in the database, in the Django
text_messages application.


How to add a new message
------------------------

1. Define a new message code in ``libya_elections/constants.py``.

   Never re-use a code that's been used before; choose a new one
   higher than the highest one currently in use.

2. Create a migration that adds the new message to the database,
   leaving the Arabic text blank unless you know what it should be.

   See ``text_messages/migration_template.py`` for a template that
   should be used when creating these migrations.

   So, do something like::

       python manage.py makemigrations text_messages --empty

   Then suppose it creates ``text_messages/migrations/0007_xyz.py``::

       cp text_messages/migration_template.py text_messages/migrations/0007_xyz.py

   and edit ``text_messages/migrations/0007_xyz.py`` as needed.

3. Do the usual process to review and merge the code and deploy it to testing.

4. After the code is merged and deployed to testing, ask to have
   the new message translated on the testing server.  (Note that the
   message has to already have been added to the database by the
   migration; the messages tool doesn't provide an "add message"
   function.)

5. Pull the latest messages from testing into a local file,
   messages.json.gz, with the latest messages from the server.

6. Update the messages on production
   Note that we're doing this before deploying the new code to production.
   This way, when the code is deployed, there's already a translated message
   for it to use.

How to change existing messages (English or Arabic)
---------------------------------------------------

1. Edit the text on the testing server by going to https://test.example.com/messages/.
2. Pull the latest messages from testing
3. Update the messages on production

How to remove an obsolete message
---------------------------------

Only do this if you're *absolutely sure* the message is not being
used anymore.

1. Comment out the definition of its code in constants.py. (Keep the
   deleted line so we can see that this code was once used and should
   not be re-used.)

Now, we want to set the deleted field to True on this message
in the databases on the servers, so it won't show up in the
translation interface anymore.  We don't have a real interface
for this because it's going to happen so rarely.

2. Start a manage.py shell to one of the testing servers

3. Import the MessageText class::

    >>> from text_messages.models import MessageText

4. Get the relevant message using its message code::

    >>> msg = MessageText.objects.get(number=27)

5. Set deleted to True and save the record::

    >>> msg.deleted = True
    >>> msg.save()

6. Exit by typing Control-D or quit()<return>

7. Repeat the above steps on production.
