:signed-out: yes

==================
Two-factor sign-in
==================

Two-factor sign-in asks for a second thing each time you sign in, after your
password: a six-digit code from an authenticator app on your phone. Somebody who
learns your password still can't get in without your phone. You set it up, make new
backup codes, and turn it off on the **Two-factor sign-in** card of your
:doc:`profile`.


Who has to use it
=================

Anyone can turn two-factor sign-in on. You must use it if you can see or change
other people's accounts, money, or the public website. That means a user
administrator, the treasurer, an account administrator, CalDART management, a
website administrator, and a system administrator. If you hold one of those roles
and haven't set it up, the portal walks you through it the next time you sign in,
before it lets you in (see :doc:`sign-in`). With one of those roles, you can't turn
it off.


What you need
=============

You need an authenticator app on your phone. Any app works if it reads a QR code and
shows six-digit codes that change every 30 seconds, such as Google Authenticator,
Microsoft Authenticator, 1Password, or Authy. The app works without a phone signal.


Setting it up
=============

On :doc:`profile`, the **Two-factor sign-in** card says *Two-factor sign-in is off.*
Press **Turn on**, type your **Current password**, and press **Show the QR code**.

1. The card shows a QR code. In your authenticator app, add an account and scan it.
   If you can't scan it, find the key under *Can't scan it? Type this key into the
   app instead*, and type it into the app by hand.
2. The app shows a six-digit code for CalDART. Type it into the **Code** box and press
   **Turn on two-factor sign-in**. The message *Two-factor sign-in is on.* appears.
3. The card shows ten **backup codes**, such as ``abcde-fghjk``. Press **Copy** or
   **Download as .txt** and keep them somewhere safe, away from your phone: in a
   password manager, or printed in a drawer. You won't see them again. When you have
   them, press **I saved these**. The card then says *Two-factor sign-in is on. You
   have 10 unused backup codes.*

CalDART emails you to say so, with the subject *CalDART: two-factor sign-in is on*.
The email log lists it as *Two-factor sign-in turned on*. If you get that email and
didn't turn it on, reset your password and ask a user administrator to reset your
two-factor sign-in. Somebody else's phone may be the one it asks for.

If the code doesn't work, check that your phone sets its clock automatically, and
type the code the app shows now. A code that has just changed may not work. Wait for
the next one.


Signing in with it
==================

After your password, the sign-in screen asks for a code: open the app and type the
six-digit code it shows for CalDART. Each code works once. See :doc:`sign-in` for the
whole screen and what it says when something is wrong.

If somebody types the right password and then a wrong code, CalDART emails you with
the subject *CalDART: a wrong two-factor code was entered*. You get one email for
each sign-in, however many wrong codes are typed. The email log lists it as *Wrong
two-factor code*. Only somebody who knows your password gets that far, so if it
wasn't you, change your password.

Ten wrong passwords or codes in fifteen minutes, or thirty wrong codes in one day,
pause signing in to your account for a while, whoever is trying. CalDART emails you
then too, at most once a day, with the subject *CalDART: sign-in paused after failed
attempts*. The email log lists it as *Sign-in paused*.


Backup codes
============

A backup code is for the day your phone is lost, broken, or dead. Wherever the
screen asks for a code, you can type a backup code into the **Code** box instead of
the app's code: when you sign in, when you make new backup codes, and when you turn
two-factor sign-in off.

* Each backup code works **once**. Cross it off when you use it.
* Capital letters, the hyphen, and spaces don't make a difference.
* Each time somebody uses one, CalDART emails you with the subject *CalDART: a backup
  code was used*, saying how many you have left. The email log lists it as *Backup
  code used*. If you didn't use it, somebody knows your password. Change it at once
  (see :doc:`change-password`) and tell CalDART.

**New backup codes** on the card makes a fresh set of ten. Type a code from the app,
or one of your old backup codes, and press **Make new backup codes**. Every earlier
backup code stops working, used or not. You see the new ones once, as when you set it
up. CalDART emails you with the subject *CalDART: new backup codes*; the email log
lists it as *New backup codes*.


Turning it off
==============

If none of your roles requires it, the card has a **Turn off** button. Type your
current password and a code from the app or a backup code, and press **Turn off
two-factor sign-in**. The message *Two-factor sign-in is off.* appears, your backup codes stop
working, and you sign in with your password alone from then on. CalDART emails you
with the subject *CalDART: two-factor sign-in is off*; the email log lists it as
*Two-factor sign-in turned off*.

If one of your roles requires it, the card doesn't have a **Turn off** button. It
says *Your role
requires two-factor sign-in, so it cannot be turned off. If you lose your phone, sign
in with a backup code, or ask a user administrator to reset it.*


A new phone, or a lost one
==========================

If you have a new phone and still have the old one, turn two-factor sign-in off and
then on again. If your role requires two-factor sign-in, you can't turn it off.
Instead, sign in with a backup code and ask a user administrator to reset it, so
that you can set it up again on the new phone.

If you have lost both the phone and the backup codes, ask a user administrator to
reset your two-factor sign-in. They do it from your user record, with **Reset
two-factor** and then **Yes, reset two-factor**. Only a system administrator can
reset a system administrator's, and nobody can reset their own. After the reset,
your app's entry and your backup codes stop working, and you are signed out
everywhere. CalDART emails you with the subject *CalDART: two-factor sign-in was
reset*; the email log lists it as *Two-factor sign-in reset*. The next time you sign
in, set it up again as above. If your role requires it, the portal asks you to set it
up before you go on.


If something looks wrong
========================

*That code is not right. Enter the current code from your app, or a backup code.*
means the code is wrong or already used, or your phone's clock is off. Type the code
the app shows now, or a backup code. *Two-factor sign-in is already on for this
account.* means it is already on. Reload the page. If you get an email about
two-factor sign-in and you didn't do what it says, change your password at once and
tell CalDART.
