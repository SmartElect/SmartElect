.. _introduction:

Introduction
============

This code implements voter registration using telephone text messages.

This system was developed to meet the specific needs of the High National
Election Commission of the state of Libya between 2013 and 2015. It is
not intended to serve as a drop-in solution for any other case, but it
can provide example code, or a starting point that could be modified
to use in other cases.

What registration consists of
-----------------------------

In this case, registration means allowing citizens who are eligible
to vote to indicate at which polling place they intend to cast their
vote in an upcoming election.

Citizens are identified by a 12-digit National IDentification number,
or NID.

Polling places, also called Registration Centers, are identified by
a 5-digit number.

To register, a Libyan citizen would text their NID, and the code for
their desired polling place, to 15015.  E.g. a citizen with NID
123456789012 who wants to vote at polling place 12345 would send the
message "123456789012 12345" to 15015.

The system verifies that there is a Libyan citizen with that NID
who is eligible to vote and has not previously registered, and that
the requested polling place is valid. If so, it records the citizen's
choice, along with the phone number that they sent their text from,
and sends a response saying they are registered.

Changes to registrations
------------------------

The system allows citizens to change their registration by sending
in a new registration message, subject to some restrictions:

* They have to make the change from the same phone number
  they previously registered from
* They can only make a limited number of changes

If a citizen needs to register from a different phone,
or has used up their changes, they can call a help desk
and get their maximum changes limit increased, or their
registration unlocked so they can change it from a new phone
(for a limited time).

The citizen must identify themselves to the help desk
by providing additional information that must match
the information in the citizen database.

Voter rolls
-----------

Once registration is closed before an election, the system
provides voter rolls for each polling place, as PDF files.
These identify the voters who will be voting at that polling
center and which voting station each is assigned to inside
the polling center.

Public Reports
---------------

A public web site provides reports and graphs showing the progress
of registration - e.g., 10,000 people registered yesterday and the
total is now 1.5 million and here's a graph showing the number of
registrations growing over the last two months.

Private reports
---------------

There are private reports for staff that allow tracking attendance at each polling
center on election day, with poll workers texting in short status messages.

The reports allow administrators to see which polling centers have and
have not sent in each scheduled status message, and what the numbers of votes are
at individual polling stations and in summary.

Staff phones must be pre-registered with the system. They can be managed
at ``/sms/staffphones/``. The registered phones are "white-listed" and only
they can send in reports on election day of how many votes have been cast so
far in a polling station. There's also a black list that can be used to
block specific phone numbers completely.

Internal features
-----------------

These are other features that aren't directly visible to the public.

* Batch changes: Registrations can be changed or voters blocked by staff, but
  only through a batch-oriented system that requires approvals, keeps a record of
  every change, and allows reversing any change later. This is important if
  a polling center needs to be closed and voters moved to a nearby center, for
  example. Those whose registrations are changed are optionally sent a text
  message about it.

* Bulk messaging: Send a text message in bulk to a list of uploaded phone numbers,
  or to the voters registered at particular centers or larger
  administrative areas.

* Audit: Track messages through the system and report problems if e.g.
  an incoming text message received from a mobile network operator
  never shows up at the registration server, or no response to it
  is sent out.

.. _registration_locations:

One-time setup
--------------

Some of the system's data represents things that don't change very
often. Here are some of those items that have to be set up in the system
at the beginning, and then changed occasionally thereafter.

(These are obviously specific to Libya, and are some of the things that
will need to be changed to re-use this system.)

* Registration Centers - another name for a place where people vote in person.
  Probably the most volatile of these items.

* Subconstituency - a geographical region. Most registration centers are in
  one subconstituency. A subconstituency is relatively small; every registration
  center in a subconstituency will have the same ballot choices in an election,
  i.e. they're all voting for the same races. (There are a few exceptional
  cases that can violate these rules.)

* Constituency - a larger geographical region. Every registration center is
  in one constituency. Constituencies and subconstituencies are political
  boundaries.

* Office - an even larger geographical region, representing the election
  commission branch offices that manage elections for parts of the country.
  Every registration center is in an office. The areas covered by offices don't
  necessarily line up with the political boundaries represented by
  constituencies and subconstituencies.

It's important to note that we cannot assume these items form a strict hierarchy.
Two registration centers could be in the same office but different subconstituencies,
for example. It means we have to keep track for every registration center of what
subconstituency, constituency, and office it belongs to. It also means when adding
up statistics for the country from smaller areas, we have to be very careful not
to include some numbers twice.

These can all be managed with a staff login on the site at
``/registration/centers/``. At the bottom of each page there are links
to allow uploading and downloading the data as .CSV files, for bulk
data creation.

Source
------

Developed for the Libya High National Elections Commission by `Caktus Consulting Group
<https://www.caktusgroup.com/>`_.
