:signed-out: yes

==================
Two-factor sign-in
==================

Two-factor sign-in asks for a second thing each time you sign in, after your
password: a six-digit code from an authenticator app on your phone. Somebody who
learns your password still cannot get in without your phone. You set it up, make new
backup codes, and turn it off on the **Two-factor sign-in** card of :doc:`profile`.


Who has to use it
=================

Anyone may turn two-factor sign-in on. It is required for every account that can see
or change other people's accounts, money, or the public website: a user
administrator, the treasurer, an account administrator, CalDART management, a
website administrator, and a system administrator. If you hold one of those roles
and have not set it up, the next time you sign in the portal takes you through
setting it up before it lets you in (see :doc:`sign-in`). Those roles cannot turn it
off.


What you need
=============

An authenticator app on your phone. Any app that reads a QR code and shows six-digit
codes that change every 30 seconds works, such as Google Authenticator, Microsoft
Authenticator, 1Password, or Authy. The app works without a phone signal.


Setting it up
=============

On :doc:`profile`, the **Two-factor sign-in** card reads *Two-factor sign-in is off.*
Press **Turn on**, type your **Current password**, and press **Show the QR code**.

1. The card shows a QR code. In your authenticator app, add an account and scan it.
   If you cannot scan it, type the key printed under it, *Cannot scan it? Type this
   key into the app instead*, into the app by hand.
2. The app shows a six-digit code for CalDART. Type it into the **Code** box and press
   **Turn on two-factor sign-in**. The message *Two-factor sign-in is on.* appears.
3. The card shows ten **backup codes**, such as ``abcde-fghjk``. Press **Copy** or
   **Download as .txt** and keep them somewhere safe, away from your phone: in a
   password manager, or printed in a drawer. They are not shown again. Press **I
   saved these** when you have them, and the card reads *Two-factor sign-in is on.
   You have 10 unused backup codes.*

CalDART emails you to say so, with the subject *CalDART: two-factor sign-in is on*.
The email log lists it as *Two-factor sign-in turned on*. If you get that email
without having turned it on, reset your password and ask a user administrator to
reset your two-factor sign-in, since somebody else's phone may be the one it asks
for.

If the code is refused, check that the phone's clock is set automatically, and type
the code the app shows now. A code that has just changed may be refused; wait for the
next one.


Signing in with it
==================

After your password, the sign-in screen asks for a code: open the app and type the
six-digit code it shows for CalDART. Each code works once. See :doc:`sign-in` for the
whole screen and what it says when something is wrong.

A wrong code after the right password makes CalDART email you, once for each time
somebody signs in, with the subject
*CalDART: a wrong two-factor code was entered*; the email log lists it as *Wrong
two-factor code*. Only somebody who knows your password gets that far, so if it was
not you, change your password. Ten wrong passwords or codes in fifteen minutes, or
thirty wrong codes in a day, pause signing in to your account for a while, whoever
tries; CalDART emails you then too, with the subject *CalDART: sign-in paused after
failed attempts*, at most once a day, listed as *Sign-in paused*.


Backup codes
============

A backup code is for the day your phone is lost, broken, or flat. Type one into the
**Code** box in place of the app's code, wherever a code is asked for: when you sign
in, when you make new backup codes, and when you turn two-factor sign-in off.

* Each backup code works **once**. Cross it off when you use it.
* Capital letters, the hyphen, and spaces don't make a difference.
* Each time one is used, CalDART emails you, with the subject *CalDART: a backup code
  was used*, saying how many you have left. The email log lists it as *Backup code
  used*. If you did not use it, somebody knows your password: change it at once (see
  :doc:`change-password`) and tell CalDART.

**New backup codes** on the card makes a fresh set of ten. Type a code from the app,
or one of your old backup codes, and press **Make new backup codes**. Every earlier
backup code stops working, used or not, and the new ones are shown once, as when you
set it up. CalDART emails you with the subject *CalDART: new backup codes*; the email
log lists it as *New backup codes*.


Turning it off
==============

If no role you hold requires it, the card offers **Turn off**. Type your current
password and a code from the app or a backup code, and press **Turn off two-factor
sign-in**. The message *Two-factor sign-in is off.* appears, your backup codes stop
working, and you sign in with your password alone from then on. CalDART emails you
with the subject *CalDART: two-factor sign-in is off*; the email log lists it as
*Two-factor sign-in turned off*.

If a role you hold requires it, the card doesn't offer **Turn off** and says *Your role
requires two-factor sign-in, so it cannot be turned off. If you lose your phone, sign
in with a backup code, or ask a user administrator to reset it.*


A new phone, or a lost one
==========================

With a new phone and the old one still in hand, turn two-factor sign-in off and on
again, or, if your role requires it, sign in on the new phone with a backup code and
ask a user administrator to reset it so you can set it up again.

With the phone and the backup codes both gone, ask a user administrator to reset your
two-factor sign-in. They do it from your user record, pressing **Reset two-factor**
and then **Yes, reset two-factor**; only a system administrator can reset a system
administrator's, and nobody can reset their own. Your app's entry and your backup
codes stop working, you are signed out everywhere, and CalDART emails you with the
subject *CalDART: two-factor sign-in was reset*; the email log lists it as
*Two-factor sign-in reset*. The next time you sign in, set it up again as above: a
role that requires it asks you to do so before you continue.


If something looks wrong
========================

*That code is not right. Enter the current code from your app, or a backup code.*
means the code is wrong, already used, or from a phone whose clock is off; type the
code the app shows now, or a backup code. *Two-factor sign-in is already on for this
account.* means it is on already: reload the page. If you get an email about
two-factor sign-in that you did not cause, change your password at once and tell
CalDART.
