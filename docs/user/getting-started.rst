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

Creating one
------------

#. Follow **Join** in the public site's top navigation, or go straight to
   ``/portal/join``.
#. Fill in the first step of the wizard: your first and last name, your email
   address, and a password.
#. Submit.  You are signed in immediately, an empty member profile is waiting
   for you, and you hold the ``member`` role.

The wizard then moves on to your profile and to payment.

Paying for a membership term is a later step in the same wizard.  You can stop
after creating the account and come back to pay: you will have a portal login,
but no current membership and therefore no access to members-only content.

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
sections your roles open.  Everyone starts with ``member``; a user administrator
grants the rest.

===================  ==================================================
Role                 What it adds
===================  ==================================================
``member``           Your own profile, payments, and membership; renew;
                     members-only content while your membership is
                     current.
``dart_leader``      A Disaster Airlift Response Team (DART) member: look
                     up any member and check membership, medical
                     , certificate, and aircraft insurance currency.
``user_admin``       List accounts, assign roles, activate and
                     deactivate, and trigger password resets.
``treasurer``        The money: every payment, fee, refund, and automatic
                     renewal; issue refunds, record payments taken by
                     check or cash, reconcile a period against the bank
                     statement, and run the financial reports.
``account_admin``    Create, edit, and delete members, grant membership
                     terms by hand, maintain aircraft and payments, read
                     the renewal reminder log, run reports, and check
                     members like a DART leader.
``website_admin``    Edit the public site in the Wagtail admin.
``system_admin``     Everything above, plus backups, health, and
                     reminder runs.
===================  ==================================================

If a menu entry you expect is missing, or you open a page and are told **"You
do not have access to this page"** under a **403**, you are missing the role
rather than doing something wrong.  The page names the role it wanted.  Ask a
user administrator (see :doc:`user-administrator`).


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
* **This account has been deactivated** means an administrator has switched the
  account off.  It appears only once you have typed the right password, so a
  deactivated account looks no different from an unregistered one to a stranger
  guessing.  Nothing you can type will get you in; ask a user administrator to
  reactivate it.

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
#. Your account is deactivated — no email is sent for a deactivated account.
#. Your account does not exist yet, in which case you want **Join CalDART**
   rather than a password reset.

A user administrator can send you a reset link directly, which is the quickest
way through if you are not sure which address your account uses.

Changing a password you still know
----------------------------------

Go to ``/portal/change-password``.  You need your current password, then the new
one twice.  You stay signed in on the device you changed it from.

Too many attempts
-----------------

Signing in, registering, and asking for reset links are all rate limited per
network address.  If you have been hammering the form you may see **Request was
throttled**; wait a minute (an hour, for registration and reset requests) and
try again.


Finding your way around
=======================

The portal's left-hand menu is grouped, and each entry appears only if your
roles allow it:

**Membership**
   Your dashboard, your profile, the aircraft you fly, renewal, and
   changing your password.

**Operations**
   The DART leader's member and aircraft checks.

**Administration**
   Members, aircraft, payments, reminders, and users and roles.

**System**
   Health, backups, and reminder runs.

On a phone the menu collapses behind the **Menu** button in the top bar.  Every
screen is keyboard-navigable, and *Skip to content* is the first stop when you
start tabbing.

This guide is on the site too.  **User guide** at the foot of the portal's menu
opens the page for your role — a member lands on :doc:`member-guide`, a DART
leader on :doc:`dart-leader-guide`, an administrator on their own guide — and
every page links to the rest.  The public site's footer links to the guide's
front page.  Either way you are asked to sign in first if you have not
already: the guide is for members.

Where to go next:

* :doc:`member-guide` — your profile, membership, and renewals.
* :doc:`dart-leader-guide` — checking another member before a flight.
* :doc:`user-administrator` — running accounts and roles.
* :doc:`faq` — the short answers.
