.. _development:

Information for developers
==========================

For developing (working on the code), the README.rst file in the top directory
is the place to start.

Once you have that much set up, see the :ref:`code_overview` which
explains what all the directories are for.

Create a superuser if you haven't already and run the server locally
using ``runserver``.  At `http://localhost:8000/ <http://localhost:8000/>`_
you can see the public view.  Then go to
`http://localhost:8000/staff/ <http://localhost:8000/staff/>`_ to
see what election staff tools are available.  As a superuser, you can
see them all; most staff will only have access to a subset depending
on their permissions.

Then start looking at the code in ``libya_elections/urls.py`` and you'll start to get an
idea of how the code provides for the various pages.

Before you start making changes, review :ref:`code_style` about
how the code should be formatted.

.. toctree::
   :maxdepth: 2

   code_overview
   contributing_code
   code_style
   load_testing
   sms_responses
   testing_messages
   translation
