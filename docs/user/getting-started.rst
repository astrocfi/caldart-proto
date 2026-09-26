===============
Getting started
===============

|org| runs two things from one website: the public pages anybody can read, and
the **member portal** at ``/portal/``, where you keep your own details up to
date, renew your membership, and — depending on the roles you hold — look after
other people's accounts.

This page covers the part everybody needs: getting an account, signing in, and
getting back in when you have forgotten your password.  What to do once you are
inside is in :doc:`member-guide`.


Your account
============

One account, one email address
------------------------------

Your **email address is your username**.  There is no separate login name, and
capitalization does not matter: ``Marta.Reyes@example.org`` and
``marta.reyes@example.org`` are the same account.  Only one account may use an
address, so if the site tells you the address is already taken, you already have
an account — reset the password rather than making a second one.

.. _kinds-of-account:

Members, friends, and donors
----------------------------

Every account belongs to one of three kinds of person:

**Member**
  Pays annual dues when joining and is expected to keep paying, or buys a Life
  plan.  A member's membership is current, expiring, or expired, and the site
  sends renewal reminders as the end of a term approaches.  A member can add a
  contribution to any payment.

**Friend**
  A friend of |org| has the same portal as a member — the profile, the
  payments, the dashboard — but pays no dues.  A friend is never current, never
  expired, and never reminded to renew, and members-only pages stay closed.  A
  friend can give whenever they like, and becomes a member by paying for a plan.
  A member who becomes a friend while a term is still running stays a current
  member until that term ends, and is a friend from the next day.

**Donor**
  Somebody who gave to |org| without joining.  A donor's account holds the
  gifts and the receipts, but no password and no role: a donor cannot sign in,
  cannot ask for a password reset, and appears in no member list.  A donor who
  later joins, as a member or a friend, registers with the same email address
  and then follows the link |org| emails there: the account is kept, gifts and
  all, and signs in with the password chosen at registration.  Until the link
  is followed nobody is signed in, so only the owner of the address can see
  the gifts.

Members and friends both hold the ``member`` role, which is what opens the
portal to them.

Creating one
------------

#. Follow **Join** in the public site's top navigation, or go straight to
   ``/portal/join``.
#. Fill in the first step of the wizard: whether you join as a member or as a
   friend, your first and last name, your email address, and a password.
#. Submit.  You are signed in immediately, an empty member profile is waiting
   for you, and you hold the ``member`` role.  If the address already belongs
   to a donor's account, because you once gave from it, you are not signed in
   yet: the step says **Check your email**, and you sign in, with the password
   you just chose, once you have opened the link in the message.  The address
   of a deactivated account is refused, with a **Sign in to reactivate** link.
#. Check your email.  |org| sends a **verification message** to the address you
   gave, with a link that proves the address is yours.  The wizard waits on its
   **Check your email** step until you open that link.

The link opens a page that says **Email verified**; its **Continue** button
takes you back to the wizard, which moves on to your profile and to payment.  On
the **Check your email** step you can also:

* press **Resend verification message** if the first one has not arrived;
* press **I've clicked the link** if you opened the link in another browser or
  on another device, so the wizard checks again;
* follow **Use a different email address** if you mistyped it.  You change the
  address there (see `Changing your email address`_) and a fresh message goes to
  the corrected one.

The link is good for three days.  If it has expired, sign in and use **Resend
verification message** on the step, or on your dashboard, to get a new one.

Paying for a membership term is a later step in the same wizard.  You can stop
after creating the account and come back to pay: you will have a portal login,
but no current membership and therefore no access to members-only content.  A
friend has no dues to pay: the same step offers a contribution, and **Not now**
skips it.

Choosing a password
-------------------

Passwords are checked against Django's standard rules, so the site will turn
down a password that is:

* shorter than 8 characters;
* one of the few thousand most common passwords (``password``, ``letmein``);
* entirely numeric;
* too similar to your own name or email address.

Pick something you do not use anywhere else.  |org| never sees your password —
it is stored only as a hash, and no administrator can read it or tell it to you.

What you can do is set by your roles
------------------------------------

Every account holds one or more **roles**, and the portal's menu shows only the
sections your roles open.  Every member and friend starts with ``member``; a
user administrator grants the rest.  A donor holds no role at all.

===================  ==================================================
Role                 What it adds
===================  ==================================================
``member``           A member or a friend with a portal account: your own
                     profile, payments, and membership; renew;
                     members-only content while your membership is
                     current.
``dart_leader``      A Disaster Airlift Response Team (DART) member: look
                     up any member and check membership, medical,
                     certificate, and aircraft insurance currency; list
                     and filter the whole membership and download its
                     report.
``user_admin``       List accounts, assign roles, activate and
                     deactivate, and trigger password resets.
``treasurer``        The money: every payment, fee, refund, and automatic
                     renewal; issue refunds, record payments taken by
                     check or cash, reconcile a period against the bank
                     statement, run the financial reports, and
                     email them on a schedule.
``account_admin``    Create, edit, and delete members, grant membership
                     terms by hand, maintain aircraft and payments, read
                     the renewal reminder log, run reports and email
                     them on a schedule, send each DART its roster, and
                     check members like a DART leader.
``website_admin``    Edit the public site in the Wagtail admin.
``system_admin``     Everything above, plus backups, health, and the
                     reminder and scheduled-report runs.
===================  ==================================================

If a menu entry you expect is missing, or you open a page and are told **"You
do not have access to this page"** under a **403**, you are missing the role
rather than doing something wrong.  The page names the role it wanted.  Ask a
user administrator (see :doc:`admin/users`).


Signing in
==========

Go to ``/portal/`` and you land on the sign-in page, or use **Sign in** in the
public site's top navigation — the button changes to **Members** once you are
signed in.  Enter your email address and password.

* If you were following a link into a particular page — say a leader sent you
  ``/portal/profile`` — signing in takes you straight back there.
* **Incorrect email address or password** means exactly that, and does not say
  which of the two was wrong.  This is deliberate: it stops a stranger using the
  sign-in form to find out who has an account.
* **This account is deactivated. You can reactivate it.** means the account is
  switched off: you deactivated it yourself (see :doc:`member-guide`), or an
  administrator did.  It appears only once you have typed the right password, so
  a deactivated account looks no different from an unregistered one to a stranger
  guessing.

.. _reactivating-your-account:

Reactivating your account
-------------------------

Under that message the sign-in page shows a panel, **Reactivate my account**:
"Reactivating brings back your roles and any membership that has not yet run
out."  Press its **Reactivate my account** button and you are signed in, exactly
as a normal sign-in would take you, with the same email address and password you
just typed.

* Your roles and your kind of account (member or friend) are as they were.
* A membership that still had time to run when the account was deactivated
  resumes through its original date.  One whose date passed in the meantime reads
  as expired, and you can renew it as usual.
* Automatic renewal and any recurring donation stay off: deactivating canceled
  them.  Turn them on again from **Payments** if you want them.
* If your email address was never verified, a fresh verification message is sent.

A password reset reactivates a deactivated account too: request one, follow the
link, and choose a new password; the account is active again and you sign in
with the new password.

You stay signed in on that browser until you sign out or the session expires.
**Sign out** is in the top bar of the portal, next to your email address; it
ends the session and clears everything the portal had cached about you, which
matters on a shared or borrowed computer.


Forgotten passwords
===================

#. From the sign-in page, follow **Forgot your password?**.
#. Type the email address your account uses, and submit.
#. Open the email and follow its link.
#. Choose a new password, type it twice, and submit.
#. Sign in with the new password.

The site always answers the same way — *if an account uses that address, a reset
link is on its way* — whether or not it recognizes the address.  That is on
purpose, for the same reason the sign-in error is vague: the form must not be
usable as a way of discovering who is a member.

The email contains a single link back to ``/portal/reset-password``.  Two things
to know about it:

* **It works once.**  Following it a second time, or after you have already set
  a new password, gives you *that password reset link is invalid or has
  expired*.  Ask for a fresh one.
* **It expires.**  Links are good for three days by default.

Nothing arrived?
----------------

In order of likelihood:

#. It went to the spam folder.
#. You typed a different address from the one on your account.  Try the other
   addresses you use.
#. Your account does not exist yet, in which case you want **Join CalDART**
   rather than a password reset.

A user administrator can send you a reset link directly, which is the quickest
way through if you are not sure which address your account uses.

Changing a password you still know
----------------------------------

Go to ``/portal/change-password``.  You need your current password, then the new
one twice.  You stay signed in on the device you changed it from.

Changing your email address
---------------------------

Choose **Change email** in the portal's menu, or go to ``/portal/change-email``.
Type the new address and your current password, then press **Change email**.
From then on you sign in with the new address, and you stay signed in on the
device you changed it from.

The new address is **unverified** until you open the link in the verification
message |org| sends to it; your dashboard says so, and offers **Resend
verification message**, until you do.  An unverified address does not lock you
out of anything.  The site refuses an address another account already uses, and
the address you already have.

Too many attempts
-----------------

Signing in, registering, asking for reset links, following verification links,
and resending verification messages are all rate limited per network address.
If you have been hammering the form you may see **Request was throttled**; wait
a minute (an hour, for everything but signing in) and try again.


Finding your way around
=======================

The portal's left-hand menu is grouped, and each entry appears only if your
roles allow it:

**Membership**
   Your dashboard, your profile, the aircraft you fly, renewal, and
   changing your password or your email address.

**Operations**
   The DART leader's member and aircraft checks.

**Administration**
   Members, aircraft, payments, reminders, reports by email, and users and
   roles.  DART leaders see **Members** here too, and treasurers see **Reports**
   beside **Payments**.

**System**
   Health, backups, and the reminder and scheduled-report runs.

On a phone the menu collapses behind the **Menu** button in the top bar.  Every
screen is keyboard-navigable, and *Skip to content* is the first stop when you
start tabbing.

This guide is on the site too.  **User guide** at the foot of the portal's menu
opens the page for your role — a member lands on :doc:`member-guide`, a DART
leader on :doc:`admin/member-check`, a treasurer on :doc:`finance/index`, an
administrator on their own guide — and
every page links to the rest.  The public site's footer links to the guide's
front page.  Either link opens the guide in a new tab, so the screen you were on
stays where you left it, and either way you are asked to sign in first if you
have not already: the guide is for members.

Where to go next:

* :doc:`member-guide` — your profile, membership, and renewals.
* :doc:`admin/member-check` — checking another member before a flight.
* :doc:`admin/users` — running accounts and roles.
* :doc:`finance/index` — the money.
* :doc:`faq` — the short answers.
