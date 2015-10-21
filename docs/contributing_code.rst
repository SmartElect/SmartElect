.. _contributing_code:

Contributing Code
=================

If you'd like to contribute code to this project, we recommend that you discuss the topic, either on
the mailing list, or via a Github issue. This document describes the mechanical process for creating
a pull request.


Get the Source
--------------

You can clone the repository from Github::

    git clone git://github.com/FIXME/FIXME.git

However this checkout will be read-only. If you want to contribute code you should
create a fork and clone your fork. You can then add the main repository as a remote::

    git clone git@github.com:<your-username>/FIXME.git
    git remote add upstream git://github.com/FIXME/FIXME.git
    git fetch upstream


Running the Tests
-----------------

When making changes to the code, either fixing bugs or adding features, you'll want to
run the tests to ensure that you have not broken any of the existing functionality.
With the code checked out and Django installed you can run the tests via::

    ./run_tests.sh


Building the Documentation
--------------------------

The docs are written in `ReST <http://docutils.sourceforge.net/rst.html>`_
and built using `Sphinx <http://sphinx.pocoo.org/>`_. As noted above you can use
tox to build the documentation or you can build them on their own via::

    make html

from inside the ``docs/`` directory.


Coding Standards
----------------

See :ref:`code_style` for details regarding the conventions that this project follow.


Submitting a Pull Request
-------------------------

The easiest way to contribute code or documentation changes is through a pull request.
For information on submitting a pull request you can read the Github help page
https://help.github.com/articles/using-pull-requests.

Pull requests are a place for the code to be reviewed before it is merged. Reviewers should review
style, clarity, correctness, in addition to making sure that it solves the intended problem and
belongs in this project. It may be a long discussion or it might just be a simple thank you.

Not every request will be merged but you should not take it personally if your change is not
accepted. At some level, the code review process is subjective. Here are some tips to increase the chances of your change being incorporated.

- Address a known issue. Preference is given to a request that fixes a currently open issue.
- Include documentation and tests when appropriate. New features should be tested and documented.
  Bugfixes should include tests which demostrate the problem.
- Keep it simple. It's difficult to review a large block of code so try to keep the scope of the
  change small.

You should also feel free to ask for help writing tests or writing documentation if you aren't sure
how to go about it.
