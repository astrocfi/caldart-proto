===
FAQ
===

Short answers to the questions the office actually gets.  Each one points at
the page that covers it properly.

Membership
==========

When does my membership expire?
-------------------------------

Sign in and look at the dashboard at ``/portal/``.  The status card at the top
says **Current**, **Expired**, or **No membership**, and a current one shows the
date it runs out.  ``/portal/profile`` and the **Renew** screen show the same
date.

An **Annual** term runs 365 days including the day it starts, so a term bought
on 1 March ends on 28 February the following year — not 1 March.  A **Life**
membership has no expiry date at all and the card says *Lifetime*.

See :doc:`member-guide`.

I renewed early — why does it still say my old date?
----------------------------------------------------

It should not.  A renewal bought while you are still current starts the day
after your present term ends, and the dashboard adds the two together and shows
you the *end of your unbroken cover* — next year's date, straight away.

If you are seeing the old date, reload the page.  If it persists, your renewal
payment may not have completed; check ``/portal/`` for the payment in your
recent history, and see :doc:`payments`.

What happens if I let my membership lapse?
------------------------------------------

Your account stays exactly as it is.  You keep your sign-in, your profile, your
aircraft and your history; nothing is deleted.  What you lose is access to
members-only pages, and a DART leader checking you before a flight sees
**NO-GO** on membership.

Renew at ``/portal/renew`` and you are current again the moment the payment
clears.  A new term after a lapse starts **today**, not on the day the old one
ended — you do not pay for the gap, and you do not get it back either.

See :doc:`member-guide`.

Will you remind me?
-------------------

Yes, by email: 60 days before expiry, 30 days before, 7 days before, on the day
it expires, and 30 days after.  Each one links straight to the renewal screen.
Life members are never reminded, because there is nothing to renew.

Reminders go to the email address on your account, which is also the address
you sign in with.  If they are not arriving, check your spam folder first, then
that the address is right at ``/portal/profile``.

See :doc:`member-guide`.

Can I have more than one membership at once?
--------------------------------------------

You can buy a term while another is running — that is what renewing early is —
and they chain end to end rather than overlapping.  Buying a Life membership
while an Annual term is running simply makes you a life member; the Annual term
becomes irrelevant.

See :doc:`payments`.

Paying
======

Which payment methods are accepted?
-----------------------------------

That depends on what the organization has configured, and the checkout only
shows what is actually available.  In full it offers:

- **Card**, through Stripe.
- **Apple Pay** and **Google Pay**, which appear automatically in the Stripe
  panel when your device and browser support them.
- **Link**, Stripe's saved-details service, if you use it.
- **PayPal**.

On a demonstration or test deployment with no payment keys you will instead see
a single **Test payment** panel with *Succeed* and *Fail* buttons.  Nothing is
charged and no card details are collected.  See :doc:`payments`.

Can my membership renew itself?
-------------------------------

Yes.  Tick **Renew automatically each year** at the checkout, or turn it on from
**Payments** in the portal menu.  The day before your membership runs out,
CalDART charges the saved card or PayPal account for that year's dues plus
whatever contribution you asked to renew alongside them, and your coverage
carries straight on.  You are never charged while a whole year of coverage still
remains.

You get an email fourteen days before every charge saying the amount, the date
and which method will be used, and you can turn it off at any time from the same
screen.

See :doc:`payments`.

I am a life member — can I still give every year?
--------------------------------------------------

Yes.  A life membership never expires, so there is nothing to renew, but you can
ask CalDART to take a contribution for you once a year.  The card on the
Payments screen is headed **Automatic contribution** rather than **Automatic
renewal**, you choose the amount and nothing else, and the charge falls on the
anniversary of the day you turned it on.  Every email about it says
"contribution"; none of them says your membership is being renewed, because it
is not.

The renew screen offers a life member the same thing: a contribution, with no
plan to buy.

See :doc:`payments`.

How do I change the card on file?
---------------------------------

If your membership renews itself, **Payments** in the portal menu shows the card
or PayPal account on file; turn automatic renewal off and on again to save a
different one.  Otherwise there is no card on file at all: CalDART stores a
payment method only when you ask it to renew your membership for you, and
otherwise you enter your details afresh each time you pay.

See :doc:`payments`.

How do I stop being charged automatically?
------------------------------------------

**Payments** in the portal menu, then **Turn off** on the **Automatic renewal**
card -- **Automatic contribution**, if you are a life member.  It takes effect immediately: nothing further is charged and the saved
payment method is dropped.  Your membership is untouched and runs to the end of
the term you have already paid for, and the ordinary renewal reminders resume.
If you would rather someone did it for you, ask the office.

See :doc:`payments`.

Can I add a donation?
---------------------

Yes.  The checkout offers contribution tiers — Participating $20, Bronze $100,
Silver $300, Gold $1,000, Diamond $3,000, Platinum $10,000 — plus an *Other
amount* box and a *No thank you*.  The contribution is added to the membership
fee in one payment and is recorded separately, so the organization can tell
dues from donations.

See :doc:`payments`.

Do I get a receipt?
-------------------

Yes.  CalDART emails one the moment the payment clears, with a PDF attached,
whichever way you paid — card, PayPal, or a check somebody entered for you.
The PDF carries the organization's address and EIN, a receipt number, the date
and what you bought, and a contribution on it carries the 501(c)(3) wording.
Every receipt can be downloaded again from **Payments** in the portal.

See :doc:`payments`.

Can I get a statement of my contributions for my taxes?
--------------------------------------------------------

Yes.  **Payments** in the portal offers one button per calendar year you
contributed in, and the statement lists every contribution that year, anything
refunded, and the total, with the wording a tax return needs.  A year you paid
dues and gave nothing has no statement: dues are not a gift.

See :doc:`payments`.

My payment failed. Was I charged?
---------------------------------

No.  A membership term is only created when the payment provider confirms the
money moved, and a failed attempt leaves a record with the status *failed* and
nothing else.  Try again, or try a different method; if a charge appears on
your statement without a matching membership, contact the office and quote the
date.

See :doc:`payments`.

Can I get a refund?
-------------------

Ask the office.  There is no self-service refund, but a treasurer or an
account administrator can issue one from CalDART, in part or in full: a
contribution on its own, say, while your membership stands.  You are emailed
when it goes through, with the amount and whether your membership ended with
it, and the money goes back to the card or account you paid with — your bank
decides how quickly it appears, usually a few working days.

See :doc:`payments`.

Profile and aircraft
====================

Why is my medical showing as expired?
-------------------------------------

Because the **expiration date** on your profile has passed, or because you set
a medical class without entering a date.  CalDART does not calculate your
medical's expiry from anything; it reads the date you typed.  BasicMed and
class medicals are treated identically in this respect.

Update it at ``/portal/profile``, in the *Aviation* section.  A medical class
requires an expiry date — the form will not save one without the other.

See :doc:`member-guide`.

Why is an aircraft's insurance showing as expired?
--------------------------------------------------

For the same reason: the ``insurance expiration`` on the aircraft record has
passed, or there is no policy on file at all.  Those are different states — the
card distinguishes them — but both fail the currency check.

Anyone may add an airplane to the register, and the member who added a record
may keep it up to date.  If somebody else added the one you fly, ask an account
administrator to correct it.  See :doc:`aircraft`.

Somebody else already added the airplane I fly. Should I add another?
---------------------------------------------------------------------

No.  There is one register, shared by everybody, and one record per airframe.
Attach the existing record to your profile — that is what "planes commonly
flown" means — and an insurance renewal entered once is then right for all of
you.  The register normalizes registrations, so ``N12345``, ``n-12345``, and
``12345`` all find the same airplane and a duplicate cannot be created by
typing it differently.

See :doc:`aircraft`.

Access and sign-in
==================

Why can I not see a members-only page?
--------------------------------------

Most often because your membership has lapsed.  The wall you hit says which it
is and offers the right way out — sign in, renew (naming the date you ran out),
or join.

You get through if your membership is current, **or** if you hold any role
beyond plain ``member`` — a DART leader or an administrator reads members-only
pages whatever their own membership is doing.

See :doc:`member-guide`.

I have forgotten my password
----------------------------

Use **Forgot your password?** on the sign-in screen.  You will get an email
with a link that lets you set a new one; the link is single-use and expires.
The message is the same whether or not the address is registered, so it
cannot be used to find out who is a member.

If nothing arrives, check spam, then confirm you are using the address the
account was created with.  A user administrator can send the reset for you.

See :doc:`member-guide`.

A menu entry I expect is missing, or I get "403 — you do not have access"
-------------------------------------------------------------------------

You are missing the role, not doing something wrong.  The portal only shows
what your roles open.  Ask a user administrator to grant it; see
:doc:`user-administrator`.

Can I change my email address?
------------------------------

Not from your own profile — the address is your sign-in, so changing it is an
administrator action.  Ask a user administrator or an account administrator.
Capitalization never matters: ``Marta@example.org`` and ``marta@example.org``
are the same account.

See :doc:`user-administrator`.

Who do I contact about a data correction?
-----------------------------------------

Anything you can see on ``/portal/profile`` you can fix yourself.  For
everything else — your name, your email address, a membership term with the
wrong dates, a payment recorded against the wrong person, an aircraft record
somebody else created — contact the office; an account administrator can
correct all of it.  The contact address is in the footer of every public page.

For the record, an administrator can see your profile including the internal
notes field, your membership history and your payment history.  They cannot see
your password: it is stored only as a hash, and nobody can read it or tell it
to you.

See :doc:`account-administrator-guide`.
