:signed-out: yes

=======
Sign in
=======

The **Sign in** screen lets you into the member portal, the part of the site where
you keep your own details, pay, and renew. Use the email address CalDART has on
file and your password. The screen says the same under its title: *The member
portal is where CalDART members and friends keep their details, pay, and renew.*


What you see
============

You reach the screen from **Sign in** at the right of the public site's top menu,
from the **Sign-in** button in the **Member sign-in** box on the home page, or from
any portal page you open while signed out. The screen asks for two things:

**Email address**
  Your email address is your username. There isn't a separate login name, and
  capital letters don't make a difference: Marta.Reyes@example.org and
  marta.reyes@example.org are the same account.

**Password**
  The password you chose when you joined, or the one you set from a reset link.

Under the form sit the **Sign in** button and the **Forgot your password?** link.
Under the card, *Not a member yet?* leads to **Join CalDART**. The top bar holds
only **Help** here, since you are already on the way in.


A code from your phone
======================

If your account uses two-factor sign-in (see :doc:`two-factor`), a right password
leads to a second screen, **Two-factor sign-in**: *Enter the code your
authenticator app shows for this account.* Open the app, type the six-digit code it
shows into the **Code** box, and press **Sign in**. Lost your phone? Type one of
your backup codes into the same box instead; each works once. **Start again** goes
back to the password.

If a role you hold requires two-factor sign-in and you have not set it up, the second
screen is **Set up two-factor sign-in** instead: *This account needs a code from an
authenticator app each time it signs in. Set one up now to finish signing in.* Scan
the QR code with an authenticator app on your phone (or type the key printed under
it), type the code the app shows, and press **Confirm and continue**. The next
screen, **Save your backup codes**, shows ten codes, each good for one sign-in
without your phone. Press **Copy** or **Download as .txt**, keep them somewhere safe,
and press **I saved these** to go on. They are not shown again.


What happens next
=================

Press **Sign in**, and give the code if the screen asks for one. If you opened a particular portal page first, such as a link a
DART leader sent you, you go straight back to it. Otherwise you land on your
:doc:`dashboard`.

If you have not finished joining, you land on the step of :doc:`join` you still
have to finish instead, whatever page you asked for: **Check your email** while
your address is unverified (press **Resend verification message** there for a
fresh link), then **About you**, then, if you joined as a member, **Pay your
dues**. The rest of the portal opens once that is done.

Once you are signed in, the public site's top menu reads **Welcome, <first name>**
in place of **Sign in**, and takes you back to the portal from any page.

The website's editing screens send you here to sign in too, and back to the
page you were opening once you are in.

Most pages of this guide also ask you to sign in first, because the guide is for
members. Once you are in, the guide page opens. This page and the pages for
:doc:`forgot-password`, :doc:`reset-password`, :doc:`join`, :doc:`verify-email`, and
:doc:`undo-email-change`, and :doc:`two-factor` open without signing in, so **Help** works
on the screens you see before you can sign in.

You stay signed in on that browser until you sign out. **Sign out** is in the
portal's top bar, beside your name. It ends the session and clears
everything the portal had kept about you, which matters on a shared or borrowed
computer.


If the screen says something else
=================================

*Enter your email address.* or *Enter your password.*
  That box is empty. Both boxes are checked together, so an empty form names both,
  the cursor moves to the first of them, and a line beside **Sign in** says how many
  to check.

*Use an email address like name@example.org.*
  The box doesn't have an @ in it, or doesn't have anything after the last dot. The box
  doesn't take spaces,
  and a copied address often brings one with it.

*Incorrect email address or password.*
  One of the two is wrong, and the cursor moves to this message. The message never says which, so a stranger cannot use
  the form to find out who has an account. Check the address first, then use
  **Forgot your password?** (see :doc:`forgot-password`).

*This account is deactivated. You can reactivate it.*
  Your account is switched off. You deactivated it yourself from
  :doc:`profile`, or an administrator did. The message appears only once you have
  typed the right password, so to a stranger a deactivated account looks the same
  as one that does not exist.

*This account has been closed. Contact CalDART to reopen it.*
  Your account is deactivated, and an administrator has closed it so that it
  cannot be reactivated from here, by a password reset, or by joining again with
  the same address. The sentence names your organization in place of CalDART.
  Write to them if you think it should be reopened. Like the deactivated message,
  it appears only once you have typed the right password.

*Request was throttled. Expected available in ... seconds.*
  There have been too many sign-in attempts from your network in a short time.
  Wait the number of seconds it gives and try again.

*Too many failed sign-in attempts for this email address. Try again later.*
  Ten wrong passwords or codes have been tried for this address in fifteen minutes,
  or thirty wrong codes in a day, from anywhere. Nobody can sign in to it until the
  time is up, even with the right password; the sentence ends with how many seconds
  are left, and CalDART emails the account, at most once a day. If none of the
  attempts were yours, somebody is guessing at your account, and can keep it paused by
  going on guessing: change your password once you are in, and if you cannot wait, ask
  CalDART, whose system administrator can lift the pause at once.

*That code is not right. Enter the current code from your app, or a backup code.*
  The code is wrong, has already been used, or comes from a phone whose clock is
  off. Type the code the app shows now, or a backup code. After five wrong codes you
  start again with the password.

*Your sign-in has expired. Enter your email address and password again.*
  The code was not given within five minutes of the password, or five wrong codes
  were tried. The screen goes back to the password; sign in again.


Reactivating your account
=========================

Under the deactivated message the screen shows a card, **Reactivate my account**:
*Reactivating brings back your roles and any membership that has not yet run
out.* Press its **Reactivate my account** button and you are signed in with the
address and password you just typed.

* Your roles, and whether you are a member or a friend, are as they were.
* A membership that still had time to run when you deactivated resumes through
  its original date. One whose date passed in the meantime reads as expired, and
  you can renew it as usual (see :doc:`renew`).
* Automatic renewal and any recurring donation stay off, because deactivating
  turned them off. Turn them on again from :doc:`payments` if you want them.
* If your email address was never verified, a fresh verification message is sent
  (see :doc:`verify-email`).

Resetting your password reactivates a deactivated account too: follow the link,
choose a password, and the account is active again. None of this works on an
account that has been closed: see *This account has been closed* above.


If something looks wrong
========================

If you are sure of your address and password and still cannot get in, ask for a
reset link from :doc:`forgot-password`. If the code is the trouble and you have
neither your phone nor a backup code, ask a user administrator to reset your
two-factor sign-in (see :doc:`two-factor`). A user administrator can also send you a
reset link, which helps when you are not sure which address your account uses. If
you don't have an account yet, you want :doc:`join`.
