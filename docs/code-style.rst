.. _code_style:

Code style
==========

We try to keep a consistent style for our code. Here
are some guidelines.

PEP-8
-----

We follow `PEP-8 <https://www.python.org/dev/peps/pep-0008/>`_,
as amended on 01-Aug-2013.

Please go read it. It has a lot of useful advice that won't
be repeated here.

We use flake8 to enforce this, with this configuration in setup.cfg::

    [flake8]
    exclude = migrations,libya_elections/constants.py,env/*,docs/conf.py
    max-line-length = 100

Indentation
-----------

For Python, "Use 4 spaces per indentation level."
-- `https://www.python.org/dev/peps/pep-0008/#indentation <https://www.python.org/dev/peps/pep-0008/#indentation>`_.

For templates and JavaScript, we use 2 spaces, since those
tend to get nested much more deeply than Python.

Wrapping long lines
-------------------

We choose to use the option that was added in the 01-Aug-2013
version of PEP-8::

    "it is okay to increase the nominal line length from 80 to 100 characters
    (effectively increasing the maximum length to 99 characters), provided that
    comments and docstrings are still wrapped at 72 characters."

Even allowed 100 char lines, we sometimes have to wrap long lines.
There are many ways to approach this and still pass flake8's checks.

For imports, we always add a `\\` after a comma and indent
lines after the first by one level.  E.g.::

    from mypackage import long_name_1, long_name_2,\
        long_name_3, long_name_4,\
        long_name_5

The alternative is putting the imported names inside parentheses,
but we choose not to use that method in our code.

PEP-8 says "The 4-space rule is optional for continuation lines", but
flake8 enforces it and so do we.

Aside from import statements, we try to avoid using backslashes when
wrapping lines whenever possible.

Otherwise, this guide doesn't express a preference among the
acceptable approaches listed in PEP-8, except that it has to pass
flake8.

Organizing imports
------------------

We organize imports into the following groups, in the following order.
(This is an extension of https://www.python.org/dev/peps/pep-0008/#imports).

* Imports from `__future__`
* Imports from the Python standard library
* Anything not in the other categories goes here - possibly subdivided.
* Imports from code in the same project/repository.

Within a group, lines are alphabetized, ignoring the first word ("from" or "import").
E.g.::

    from datetime import timedelta
    import os
    from os.path import abspath
    from sys import exit

Per PEP-8, "You should put a blank line between each group of imports.".

Naming
------

* Factory classes are named "ModelNameFactory".  E.g. "WidgetCatalogFactory".

* Factory classes should be in a `factories.py` file in the `tests` directory
  in the same app where the models being created are defined. E.g. the factory
  for the Widget model defined in `acme/models.py` should be defined in
  `acme/tests/factories.py`.

* Special case: if we need to define a factory for a model that's not part
  of our project, do it in any `factories.py` file that seems related,
  e.g. one for any app whose tests need to use the factory.

* Modules containing utility functions should be named `utils.py` (not
  `util.py`).
