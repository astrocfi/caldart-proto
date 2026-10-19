:signed-out: yes

=======
Sign in
=======

The **Sign in** screen lets you into the member portal, the part of the site where
you keep your own details, pay, and renew. You sign in with the email address CalDART
has for you and your password. The screen says the same under its title: *The member
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

Under the form are the **Sign in** button and the **Forgot your password?** link.
Under the card, *Not a member yet?* leads to **Join CalDART**. The top bar has only
**Help** on this screen.


A code from your phone
======================

If your account uses two-factor sign-in (see :doc:`two-factor`), the right password
takes you to a second screen, **Two-factor sign-in**: *Enter the code your
authenticator app shows for this account.* Open the app, type the six-digit code it
shows into the **Code** box, and press **Sign in**. Lost your phone? Type one of
your backup codes into the same box instead. Each one works once. **Start again**
goes back to the password.

If one of your roles requires two-factor sign-in and you haven't set it up, the
second screen is **Set up two-factor sign-in** instead: *This account needs a code
from an authenticator app each time it signs in. Set one up now to finish signing
in.* Scan the QR code with an authenticator app on your phone (or type the key
printed under it), type the code the app shows, and press **Confirm and continue**.
The next screen, **Save your backup codes**, shows ten codes. Each one signs you in
once without your phone. Press **Copy** or **Download as .txt**, keep them somewhere
safe, and press **I saved these** to go on. You won't see them again.


What happens next
=================

Press **Sign in**, and give the code if the screen asks for one. If you opened a
particular portal page first, such as a link a DART leader sent you, you go straight
back to it. Otherwise you land on your :doc:`dashboard`.

If you haven't finished joining, you land on the next step of :doc:`join` instead,
whatever page you asked for. That is **Check your email** until you confirm your
address (press **Resend verification message** there for a fresh link), then
**About you**, then, if you joined as a member, **Pay your dues**. The rest of the
portal opens once you finish.

Once you are signed in, the public site's top menu shows **Welcome, <first name>**
where **Sign in** was. It takes you back to the portal from any page.

The website's editing screens also send you here to sign in, and then back to the
page you wanted.

You also sign in to read most of this guide, because the guide is for members. Once
you are in, the guide page opens. A few pages open without signing in, so that
**Help** works on the screens you see before you sign in: this page, and the pages
for :doc:`forgot-password`, :doc:`reset-password`, :doc:`join`, :doc:`verify-email`,
:doc:`undo-email-change`, and :doc:`two-factor`.

You stay signed in on that browser until you sign out. **Sign out** is in the
portal's top bar, beside your name. It signs you out and clears everything the
portal kept about you. That matters on a shared or borrowed computer.


If the screen says something else
=================================

*Enter your email address.* or *Enter your password.*
  That box is empty. The screen checks both boxes at once. If both are empty, it
  shows both messages, moves the cursor to the first box, and says beside **Sign
  in** how many boxes to check.

*Use an email address like name@example.org.*
  The address is missing its @, or the part after the last dot. Spaces aren't
  allowed either, and a copied address often brings one along.

*Incorrect email address or password.*
  One of the two is wrong, and the cursor moves to this message. The message never
  says which one, so a stranger can't use the form to find out who has an account.
  Check the address first, then use **Forgot your password?** (see
  :doc:`forgot-password`).

*This account is deactivated. You can reactivate it.*
  Your account is switched off. You deactivated it yourself from :doc:`profile`, or
  an administrator did. You only see this message after you type the right
  password, so to a stranger a deactivated account looks like one that doesn't
  exist.

*This account has been closed. Contact CalDART to reopen it.*
  Your account is deactivated, and an administrator has also closed it. You can't
  reactivate it from here, with a password reset, or by joining again with the same
  address. The message shows your organization's name where this guide says
  CalDART. Write to them if you think it should be reopened. Like the deactivated
  message, you only see it after you type the right password.

*Too many tries. Try again in ... seconds.*
  There have been too many sign-in attempts from your network in a short time.
  Wait the number of seconds it gives and try again.

*Too many failed sign-in attempts for this email address. Try again in ... seconds.*
  Someone has tried ten wrong passwords or codes for this address in fifteen
  minutes, or thirty wrong codes in one day. The count includes tries from every
  computer. Until the pause is over, nobody can sign in to the account, even with
  the right password. The message ends with how many seconds are left, and CalDART
  emails the account about it, at most once a day. If those tries weren't yours,
  somebody is guessing at your account, and they can keep it paused by guessing
  more. Change your password once you are in. If you can't wait, ask CalDART: its
  system administrator can lift the pause at once.

*That code is not right. Enter the current code from your app, or a backup code.*
  The code is wrong or already used, or your phone's clock is off. Type the code
  the app shows now, or a backup code. After five wrong codes you start again with
  the password.

*Your sign-in has expired. Enter your email address and password again.*
  More than five minutes passed between the password and the code, or five wrong
  codes were tried. The screen goes back to the password. Sign in again.


Reactivating your account
=========================

Under the deactivated message is a card, **Reactivate my account**: *Reactivating
brings back your roles and any membership that has not yet run out.* Press its
**Reactivate my account** button. You are signed in with the address and password
you just typed.

* Your roles, and whether you are a member or a friend, are as they were.
* If your membership still had time left when you deactivated, it runs to its
  original end date. If that date has passed since, the membership shows as
  expired, and you can renew it as usual (see :doc:`renew`).
* Automatic renewal and any recurring donation stay off, because deactivating
  turned them off. Turn them on again from :doc:`payments` if you want them.
* If you never verified your email address, CalDART sends you a fresh verification
  message (see :doc:`verify-email`).

Resetting your password also reactivates a deactivated account. Follow the link,
choose a password, and the account is active again. None of this works on a closed
account: see *This account has been closed* above.


If something looks wrong
========================

If you are sure of your address and password and still can't get in, ask for a
reset link from :doc:`forgot-password`. If the code is the problem and you have
neither your phone nor a backup code, ask a user administrator to reset your
two-factor sign-in (see :doc:`two-factor`). A user administrator can also send you a
reset link. That helps when you aren't sure which address your account uses. If you
don't have an account yet, see :doc:`join`.
