===========
My aircraft
===========

**My aircraft** lists the airplanes you commonly fly. A DART leader reads this list,
and each airplane's insurance, before deciding whether to launch you on a mission,
so keep it current.

CalDART keeps one register of airplanes for everybody. Adding an airplane here
attaches a record from that register to your profile; you do not get a private
copy. Open the screen from **My aircraft** in the menu, from the button at the top
of :doc:`profile`, or from **Add the planes I fly** at the end of :doc:`join`.


What you see
============

When CalDART's coverage policy has a note to members, such as *Helicopters are not
covered*, it stands at the top of the **Attached aircraft** card. It says which
airplanes CalDART's insurance leaves out; a DART leader treats an airplane it leaves out
as a no-go.

The **Attached aircraft** card lists each airplane on your profile: its N-number,
make, and model, an insurance chip, and the liability limits and expiry date on
file, for example *$1,000,000 / $100,000 · exp 03/01/2027*. The chip reads:

* **Current**: a policy is on file and has not expired;
* **Expired**: the expiry date on file has passed;
* **Not on file**: the record has no insurance expiry date at all.

After the chip comes the insurance's mark: **Verified** once a DART leader or a
verifier has checked the policy against its documents, or **Not yet verified**. A DART
leader treats an airplane whose insurance is not verified as a no-go.

An airplane the coverage policy leaves out carries a red **Not covered** chip, and the
reason follows the limits, such as *Not covered: helicopters are excluded by CalDART's
policy*.

A record with no insurance reads *No insurance on file* in place of the limits.
With nothing attached, the card says **No aircraft attached yet**.

Beside each airplane are **Edit** and a trashcan, **Remove**.

Below it, the **Find an aircraft** card searches the register.


Adding an airplane you fly
==========================

#. Type in **Search the aircraft register**: the N-number, or the make, model, or
   owner if you do not have the number to hand.
#. The results say *Click on an aircraft to add it to your list.* Each shows its
   N-number, make and model, an insurance chip (**Insured**, **Expiring soon**,
   **Insurance expired**, or **No insurance on file**), and **Out of service** for
   an airplane taken out of use.
#. Click the airplane. It is attached straight away, *N12345 added.* appears, and
   it joins the list above.

You can type a registration however you like. CalDART writes every N-number one
way: upper case, no punctuation, and an N at the front. So 12345, n12345, and
N-12345 all find N12345, and one airplane can be in the register only once.

Airplanes already on your list are left out of the results and named under them,
such as *N12345 is already on your list.* or *N12345 and N9021K are already on your
list.* A search that finds nothing says **No aircraft matches that**. An airplane
taken out of service is left out of the results, unless you type its exact
registration, so you do not add it twice.


Adding an airplane that is not in the register
==============================================

**Add a new aircraft** sits at the foot of the card (*Not in the register? Add it
yourself.*), and you do not have to search first. It opens **Add an aircraft to the
register**, the whole record, with every box the record has when you edit it later:

* **N-number** (required). The box writes the N and takes digits first, then at
  most two letters, so 172sp becomes N172SP. Anything you typed in the search box is
  already in it. As you type, the FAA registry's airplanes whose N-number starts
  with what you typed are listed under the box: see :ref:`registry-list`.
* **Year**, four digits.
* **Aircraft type** (required): type the make, the model, or a designator, for example
  cessna 172, c172, or skyhawk, and pick the type from the list under the box. Each
  entry reads as its make and model, with its seats after it. Picking from the list
  is the only way to set the type, so one type always reads the same way, however it
  was typed. A search that finds nothing says *No aircraft type matches that.*
* **Seats**. Picking a type with **Seats** empty fills in its seats.
* **Category**, such as Airplane, Helicopter, Gyroplane, Glider, or Balloon, and
  **Airworthiness**, the category on the airworthiness certificate, such as Standard,
  Experimental, or Light sport. Either may stay **Not recorded**, but a DART leader's
  aircraft check then says *Category not recorded*. Picking a type the registry knows the
  category of fills in **Category**.
* **Owner type** (Individual, FBO, or Flying club), **Owner name**, and **Owner
  contact**, an email address or a phone number.
* **Carrier**, **Policy number**, **Liability per occurrence**, **Liability per
  person**, **Hull**, and **Insurance expires**. Money is in whole dollars, and the
  commas write themselves. **Insurance expires** is the most useful box on the form,
  since it is what a DART leader looks at.

Press **Add aircraft**. The airplane joins the register and your list at once.
**Cancel** closes the form.

.. _registry-list:

Picking an airplane from the FAA registry
-----------------------------------------

Every US airplane is in the FAA's aircraft registry, and CalDART keeps a copy of it,
refreshed every night. Type the start of the N-number, such as N17, and up to eight
airplanes whose N-number starts with it are listed under the box, each with its
N-number, aircraft type, year, and registrant. Keep typing to narrow the list. Click
one, or move to it with the arrow keys and press Enter; Escape closes the list.

Picking an airplane writes its N-number into the box and fills in its aircraft type,
year, seats, category, and airworthiness; **Owner name** takes the registrant's name, and **Owner type**
takes a guess from the kind of registrant it is: a person or co-owners become
**Individual**, a partnership becomes **Flying club**, and a company becomes
**FBO**. A government registrant, or one the registry does not sort into any of
those, leaves **Owner type** as it was. The line under the N-number box then reads,
for example, *From the FAA registry as of 09/20/2026*, the day of the copy, until
you change the N-number again. Check what it filled and correct anything that is
out of date.

An airplane the registry does not have simply does not appear in the list. Finish
typing its N-number and fill the rest of the form in by hand.


Editing an airplane
===================

Press **Edit** beside an airplane. For one you added yourself, the form opens with
every detail, as it was added: **N-number**, **Year**, **Aircraft type**, **Seats**,
**Category**, and **Airworthiness**; **Owner type** (Individual, FBO, or Flying club), **Owner name**, and
**Owner contact**; and **Carrier**, **Policy number**, **Liability per occurrence**,
**Liability per person**, **Hull**, and **Insurance expires**. Money is in whole
dollars, and the commas write themselves. To change the type, type in **Aircraft
type** and pick the new one from the list. Picking a type with **Seats** empty fills
in its seats. Typing in **N-number** lists the registry's airplanes again, and
picking one fills the form from it (:ref:`registry-list`). Press **Save aircraft**;
*N12345 updated.* appears. Saving a change to any insurance detail clears the
insurance's verification, and the mark reads **Not yet verified** until a DART
leader or a verifier checks the new policy.

For an airplane somebody else added, **Edit** shows **Someone else added this
aircraft**: *Ask a CalDART account administrator to correct it.* The register is
shared, so flying an airplane does not make its record yours to change. An account
administrator is the exception: for them **Edit** opens any airplane on the list.


Removing an airplane
====================

The trashcan asks first: press it and it turns into **Remove** and **Keep**. Press
**Remove** and the airplane comes off your list, and *N12345 removed.* appears;
press **Keep**, press Escape, or click away and nothing changes. Removing only
detaches the airplane from you. The record stays in the register, and anyone else
who flies it keeps it on their list. Only an account administrator can delete an
airplane from the register.


If something looks wrong
========================

*Pick the aircraft type from the list.* means the **Aircraft type** box holds typing
that was never picked from the list. If the list has no entry for your airplane, ask
an account administrator to add its type. *An aircraft with this N-number is already
on file.* means the register has it already. Search for it and attach that record.
*Use a US registration like N172SP: N, then digits, then at most two letters.* means
the N-number cannot be a US registration. *Enter an amount of $0 or more.* means a
money box holds something that is not an amount. If the insurance chip says **Not on
file** and the airplane is insured, the record has no expiry date: add it if you
added the airplane, or ask an account administrator.
