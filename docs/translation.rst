.. _translation:

Translation
===========

Translation in this project is set up pretty typically for a Django
project - see https://docs.djangoproject.com/en/1.7/topics/i18n/translation/.

The exception to that rule is that our SMS response messages are handled
differently.  See sms_responses.rst for documentation
of how that works.

This document refers to all other strings in the application.


Transifex
---------

The ``requirements/dev.txt`` will install the Transifex client.

Before using the command-line Transifex client, create a ``~/.transifexrc``
file with your credentials - see
http://support.transifex.com/customer/portal/articles/1000855-configuring-the-client

Adding features and fixing bugs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As a developer, when you work on a branch, please do `not` regenerate
the django.po file. Merging branches with different updates to django.po
is a pain, and not really necessary.

Updating messages on Transifex
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Instead, if there have been changes to the messages in the code or templates
that have been merged to develop, someone should update the messages on
Transifex as follows:

1. regenerate the English (only) .po file::

    python manage.py makemessages -l en

   (Never update the Arabic .po files using makemessages. We'll update the English file, upload it
   to Transifex, then later pull the .po files with translations down from Transifex.)

#. push the updated source file to Transifex (http://support.transifex.com/customer/portal/articles/996211-pushing-new-translations)::

     tx push -s

#. Commit and push the changes to github::

     git commit -m "Updated messages" locale/en/LC_MESSAGES/*
     git push


Updating translations from Transifex
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Anytime translations on Transifex have been updated, someone should update
our translation files on the develop branch as follows:

1. pull the updated Arabic files (http://support.transifex.com/customer/portal/articles/996157-getting-translations)::

    tx pull -af

2. Use ``git diff`` to see if any translations have actually changed. If not, you
   can just revert the Arabic .po file changes and stop here.

3. Compile the messages::

    python manage.py compilemessages -l ar

4. Run your test suite one more time::

    python manage.py test

5. Commit and push the changes to github::

    git commit -m "Updated translations" locale/ar/LC_MESSAGES/*
    git push
