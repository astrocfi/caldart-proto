========
Aircraft
========

CalDART keeps one register of aeroplanes.  Members add the aircraft they
commonly fly and attach them to their profile; account administrators keep the
insurance details straight; DART leaders read the result before a mission.
This page covers both halves.

.. contents:: On this page
   :local:
   :depth: 1


N-numbers
=========

A registration is stored in one canonical form: upper case, no punctuation,
with the leading ``N`` supplied if you leave it off.  All of these are the same
aeroplane, and any of them can be typed into any search box in the portal:

.. code-block:: text

   12345      n12345      N-12345      N12345   ->  N12345
   172sp      n-172-sp    N172SP                ->  N172SP

Because of that, an aeroplane can only be in the register once, however the
person adding it happened to type the number.


For members: adding an aeroplane you fly
========================================

Open **My aircraft** in the portal menu and search the register.  Type the
registration, or the make, model or owner if you do not have the number to
hand.  Pick the aeroplane from the results and it is attached to your profile.

Aeroplanes already on your list are filtered out of the results and named
underneath, so you can tell the difference between "not in the register" and
"already attached".

If nothing matches, choose **Add a new aircraft**.  The short form needs:

=====================  ==========================================================
Field                  Notes
=====================  ==========================================================
N-number               Required.  Typed however you like; stored canonically
Make                   Required, e.g. ``Cessna``
Model                  Required, e.g. ``172S Skyhawk``
Year                   Optional, four digits
Owner                  Optional: the person, club or FBO that owns it
Insurance carrier      Optional, but a DART leader will look for it
Insurance expires      Optional, and the single most useful field on the form
=====================  ==========================================================

Saving adds the aeroplane to the register *and* attaches it to your profile.

You may edit any aircraft you added yourself — carrier, expiry, owner details
— from the same screens.  You may not edit an aeroplane somebody else added,
and you may not delete one at all: another member may be flying it.  Ask an
account administrator.

.. tip::

   Keep the insurance expiry current on the aeroplanes you fly.  It is what a
   DART leader sees at the moment they decide whether to launch you.


For account administrators: maintaining the register
====================================================

**Aircraft** under Administration (``/portal/admin/aircraft``) lists the whole
register.

Filtering
---------

===================  ============================================================
Filter               Matches
===================  ============================================================
Search               N-number, make, model or owner name.  A registration is
                     normalised first, so ``172sp`` finds ``N172SP``
Make                 Any part of the make, case-insensitively
Owner type           Individual, FBO or flying club
Insurance            ``Insured`` (a policy on file, not yet expired),
                     ``Expired``, or ``Not on file``
Expiring within      30, 60 or 90 days — cover that is still valid but is about
                     to lapse.  Already-expired policies are *not* included
===================  ============================================================

The register lists in-service and out-of-service airframes alike, so nothing
disappears from an administrator's view.

Every column sorts, and sorting happens on the server, so it sorts the whole
register rather than the page you are looking at.  Aeroplanes with no
insurance on file always sort to the bottom, whichever direction you sort the
expiry column, so they never crowd out the ones that are about to lapse.

Exports
-------

**Export CSV** and **Export PDF** download exactly the rows the filters have
selected — set the filters first, then export.  Both carry the same columns:

.. code-block:: text

   n_number, make, model, owner, owner_type, insurance_carrier,
   liability_per_occurrence, liability_per_person, hull,
   insurance_expiration, insurance_current, pilots

``pilots`` is the members who list the aeroplane on their profile.  The CSV
gives money as plain decimal dollars for a spreadsheet; the PDF is a
landscape-letter table with the filters printed under the title.

A useful monthly routine: filter to **Expiring within 30 days**, export the
PDF, and work down it.

Editing a record
----------------

Click a registration to open the record.  It is in four sections:

- **Aircraft** — registration, year, make, model, seats.
- **Owner** — individual, FBO or club, with a name and a contact.
- **Insurance** — carrier, policy number, liability per occurrence and per
  person, hull value, and the expiry date.  Amounts are entered in dollars and
  stored as integer cents; nothing may be negative.
- **Administration** — free-text notes and an "in service" flag.  Clearing
  it marks the airframe **Out of service**: it is labelled that way in the
  register, on the record, and on a DART leader's aircraft check, and it stops
  being offered to members searching for a plane to add to their profile.  A
  member who types its exact registration still sees it, labelled, so they do
  not try to add a second record for the same aeroplane.

Underneath, **Pilots who fly this aircraft** lists every member who has
attached it, with their membership and medical currency — the same facts a
DART leader would see.

**Delete this aircraft** removes it from the register permanently, and from
every profile that had it attached.  It asks once for confirmation.  Prefer
clearing the "in service" flag if the aeroplane may come back — the history
stays, and a leader checking the tail number can still see what was on file.


Who may do what
===============

=========================  ==========  ==========  ==========  ==========
Action                     Member      Creator     DART        Account
                                                   leader      admin
=========================  ==========  ==========  ==========  ==========
Search the register        yes         yes         yes         yes
Add an aircraft            yes         yes         yes         yes
Attach one to own profile  yes         yes         yes         yes
Edit a record              no          yes         no          yes
Delete a record            no          no          no          yes
Export CSV / PDF           no          no          no          yes
=========================  ==========  ==========  ==========  ==========

"Creator" means the member who added that particular aeroplane.
``system_admin`` may do everything in the table.
