========
Aircraft
========

CalDART keeps one register of airplanes.  Members add the aircraft they
commonly fly and attach them to their profile; account administrators keep the
insurance details straight; DART leaders read the result before a mission.
This page covers both halves.


N-numbers
=========

A registration is stored in one canonical form: upper case, no punctuation,
with the leading ``N`` supplied if you leave it off.  All of these are the same
airplane, and any of them can be typed into any search box in the portal:

.. code-block:: text

   12345      n12345      N-12345      N12345   ->  N12345
   172sp      n-172-sp    N172SP                ->  N172SP

Because of that, an airplane can only be in the register once, however the
person adding it happened to type the number.


For members: adding an airplane you fly
=======================================

#. Open **My aircraft** in the portal menu.
#. Search the register in the panel underneath: type the registration, or the
   make, model, or owner if you do not have the number to hand.
#. Pick the airplane from the results, which say *Click on an aircraft to add
   it to your list*.  It is attached to your profile straight away and appears
   in the list above with its insurance chip.

Airplanes already on your list are filtered out of the results and named
underneath — *N12345 is already on your list.* for one, *N12345 and N9021K are
already on your list.* for two, and three or more joined with commas and a
final *and* — so you can tell the difference between "not in the register" and
"already attached".  A search that
finds nothing says so, and points at the button below it.

One **Add a new aircraft** button sits at the foot of the panel, under the
results or the empty state, and opens the same short form whenever you want it
— you do not have to search first.  The form needs:

=====================  ==========================================================
Field                  Notes
=====================  ==========================================================
N-number               Required.  The box writes the ``N`` and takes digits
                       first, then at most two letters, so ``172sp`` becomes
                       ``N172SP`` and nothing else can be typed
Make                   Required, e.g. ``Cessna``
Model                  Required, e.g. ``172S Skyhawk``
Year                   Optional, four digits
Owner                  Optional: the person, club, or FBO that owns it
Insurance carrier      Optional, but a DART leader will look for it
Insurance expires      Optional, and the single most useful field on the form
=====================  ==========================================================

Saving adds the airplane to the register *and* attaches it to your profile.

You can correct an aircraft you added: on **My aircraft**, press **Edit**
beside it.  Only an account administrator can delete an aircraft, since
another member may be flying it.  Opening **Edit** on a record somebody else
added says so and asks you to have an account administrator correct it.

.. tip::

   Keep the insurance expiry current on the airplanes you fly.  It is what a
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
Search               N-number, make, model, or owner name.  A registration is
                     normalized first, so ``172sp`` finds ``N172SP``
Make                 Any part of the make, case-insensitively
Owner type           Individual, FBO, or flying club
Insurance            ``Current`` (a policy on file, not yet expired),
                     ``Expired``, or ``Not on file``
Expiring within      30, 60, or 90 days — cover that is still valid but is about
                     to lapse.  Already-expired policies are *not* included
===================  ============================================================

Each filter applies as soon as you set it; a typed one applies once you pause.
**Reset to Defaults** empties them all.  The filters, the sort order, and the page you are
on are kept in the page's address, so a filtered register can be bookmarked or
sent to another administrator, and the browser's back button steps back through
the filters you applied.

The insurance column is a colored dot beside the expiry date: green while the
cover runs, amber in its last 30 days, red once it has lapsed, and gray when
no policy is on file.  The column heading already says "Insurance", so the
rows do not repeat the word; the state is still read out to a screen reader.

The register lists in-service and out-of-service airframes alike, so nothing
disappears from an administrator's view.  Each row stays on one line, and
anything too long for its column is cut with an ellipsis, with the whole value
shown on hover.

Every column sorts, and sorting happens on the server, so it sorts the whole
register rather than the page you are looking at.  Airplanes with no
insurance on file always sort to the bottom, whichever direction you sort the
expiry column, so they never crowd out the ones that are about to lapse.

Exports
-------

**Export CSV** and **Export PDF** download exactly the rows the filters have
selected — set the filters first, then export.  Both carry the same nine
columns unless you ask for others:

.. code-block:: text

   N-number, Make, Model, Owner, Carrier, Liability / occurrence,
   Hull, Expires, Current

The CSV gives money as plain decimal dollars for a spreadsheet; the PDF is a
landscape-letter table with the filters printed under the title, sized so no
column has to wrap.

A useful monthly routine: filter to **Expiring within 30 days**, export the
PDF, and work down it.

Choosing the columns
--------------------

**Columns**, beside the filters, opens a chooser that drives both downloads.
Three columns beyond the nine above are on offer — *Owner type*,
*Liability / person*, and *Pilots*, the members who list the airplane on their
profile.  They are there for an insurance review or a roster, so they are off
until you tick them; the pilot list is as long as the number of members who fly
the airplane, which is why it is asked for rather than assumed.  **Reset to the
default columns**, under the boxes, ticks the nine again.

The chooser feeds the downloads, not the table: the register on screen keeps its
five columns however many you tick.  The last column cannot be unticked, since a
report of nothing helps nobody.

Beside **Columns**, **Load columns** lists the sets of columns you have saved
for the aircraft report.  Pick a name and its columns are applied; the list
closes.  The trashcan beside a name deletes that set.  **Save columns** keeps
the boxes as they stand: type a name of up to 60 characters and press **Save**,
or press Enter.  Saving under a name you already use replaces that set, and
loading a set puts its name in the box, so a set you load and change is saved
again under the same name.  Each of the three buttons opens its own panel under
itself, which a click outside it or Escape puts away.  Your saved sets are
yours alone, and each report keeps its own.

Editing a record
----------------

Click a registration to open the record.  Over the details is the line **Last
updated 2026/09/01 by Dana Fiske**, the date of the last write and the account
behind it; a record nobody has touched since the demo data was loaded gives the
date alone.  The details themselves are in four sections:

- **Aircraft** — registration, year, make, model, seats.  The registration is
  a US N-number: ``N`` and then up to five characters, digits first and at most
  two letters after them, never I or O.  The model box suggests types as you
  type — three letters of "Malibu" offers *PA-46 Malibu* — and picking one
  fills the make in.
- **Owner** — individual, FBO, or club, with a name and a contact.
- **Insurance** — carrier, policy number, liability per occurrence and per
  person, hull value, and the expiry date.  Amounts are entered in dollars and
  stored as integer cents; nothing may be negative.  A figure is grouped for
  reading as soon as you leave the box, so ``1000000`` becomes ``1,000,000``.
- **Administration** — free-text notes and an "in service" flag.  Clearing
  it marks the airframe **Out of service**: it is labeled that way in the
  register, on the record, and on a DART leader's aircraft check, and it stops
  being offered to members searching for a plane to add to their profile.  A
  member who types its exact registration still sees it, labeled, so they do
  not try to add a second record for the same airplane.

**History** lists every write to the record, newest first, one line each: the
date and time, the account that made it, and what it did — ``2026/09/01 12:00 ·
Dana Fiske · updated carrier, insurance expiry``, or ``· created`` for the write
that added the aircraft.  A write with no account behind it, such as the demo
seed, reads "the seed".  A record that predates its history says no change is
recorded for it; the next save starts the list.  If the history itself cannot be
fetched the card says so, rather than passing the failure off as an empty
record.  The columns are named as the
form names them, so "insurance expiry" is the **Insurance expires** box.

Underneath, **Pilots who fly this aircraft** lists every member who has
attached it, with their membership and medical currency — the same facts a
DART leader would see.

**Delete this aircraft** — a trashcan and those words, as every delete in the
portal is — removes it from the register permanently, and from every profile
that had it attached.  It asks once for confirmation.  Prefer
clearing the "in service" flag if the airplane may come back — the history
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

"Creator" means the member who added that particular airplane.
``system_admin`` may do everything in the table.

Every aircraft on **My aircraft** (``/portal/profile/aircraft``) has an
**Edit** action.  For an aircraft the member added, it opens the same form the
register uses, without the administrator-only controls.  For anyone else's, it
shows a card headed *Someone else added this aircraft*.  The API enforces the
same rule (:doc:`/developer/api-aircraft`), so a member who did not add the
record gets a 403 however they reach it.

That card is keyed on who added the record, not on roles, so an account
administrator sees it too on their own **My aircraft**.  They edit those
records from **Aircraft** under Administration instead.


When something goes wrong
=========================

**"An aircraft with this N-number is already on file."**
   The register already has it, under whatever spelling somebody first used.
   Search for it and attach the existing record instead of adding a second —
   that is the whole point of one shared register.  Registrations are
   normalized, so ``N12345``, ``n-12345``, and ``12345`` cannot be entered as
   three separate airplanes.

**"Enter a registration, for example N12345."**
   The lookup box got something it could not read as a tail number.  Letters
   and digits are all it needs; punctuation, spaces, and case are ignored.

**The picker finds nothing, but you know the airplane is on file.**
   The fuzzy search leaves out airplanes marked *out of service*.  Type the
   exact registration and it will still be found, labeled as out of service,
   so you do not add a duplicate.

**You are told only the member who added it, or an administrator, may change it.**
   You are not the record's creator.  Ask an account administrator to make the
   change — including for a record with no creator recorded, which is
   administrator-only by default.

**"Only an account administrator can delete an aircraft."**
   Deleting is never granted to the creator alone, because the record may be
   attached to other people's profiles.  If the airplane is simply out of
   use, clear the **in service** flag rather than asking for a deletion.

**An insurance chip says "No insurance on file" and you think it is insured.**
   That state means the record has no expiration date, which is different from
   an expired policy.  Somebody has to enter the carrier, the limits and the
   expiry before a DART leader can rely on it.

**"Enter an amount of $0 or more."**
   One of the three money boxes holds something that is not a positive amount
   — a negative number, or text the form cannot read as one.  Enter dollars;
   commas and a leading ``$`` are accepted and stripped for you.

**You removed an airplane and worry you deleted it.**
   The trashcan on your own profile only detaches the airplane from you.  The
   record, and everybody else's link to it, is untouched.
