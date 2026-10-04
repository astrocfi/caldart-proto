:roles: management

=============
Mail delivery
=============

**Mail delivery** tells you whether other mail systems, such as Gmail, Outlook, and
the providers your members use, will trust the email CalDART sends. If they do not,
a bulk email can land in people's spam folders or never arrive, and nothing on the
Compose screen would tell you. Open this page before your first bulk email, before a
large one, and after anyone changes the website's email settings.

CalDART management opens it, as **Mail delivery** under **Bulk Email** in the menu. A
system administrator can open it too. You only read it: the fixes are made by whoever
manages the CalDART domain name and the website's server.


How to read it
==============

The page opens with one sentence that sums everything up: either every check is good,
or it says how many found a problem and what that costs. Under it is one block for each
of four checks. Each block has:

- a colored dot and a word: **Good** (green), **Warning** (amber), or **Problem** (red),
  beside the check's name, or on a line of its own under the name on a phone;
- a line that says what the check is for, in plain words, and what it found;
- when the check is not good, **What to do**, a sentence you can pass on as it stands to
  the person who looks after the domain name or the server.

**Good** needs nothing. **Warning** means mail will probably still arrive, but the setup
is weaker than it should be, or the page could not judge it. **Problem** means some mail
is likely to be marked as spam or refused until it is fixed.

At the foot of the page, **Checked** gives the date and time of the last look and the
domain it was made for, for example *Checked 10/03/2026 at 8:00 AM for caldart.example.org.*
Press **Check again** after somebody says they have fixed something. The page looks the
records up again, which takes a few seconds. Without it, the page shows what it found
in the last five minutes.


The four checks
===============

**Approved senders (SPF).** A public list, kept with the CalDART domain name (or, when
bounces return to a different address, the domain of that address, which the block names),
of the
servers allowed to send email that claims to come from CalDART. Receiving systems read
it to catch forgeries. The check is good when the list exists, names the server the
website sends through, and tells receivers to be suspicious of anything else. It is a
problem when there is no list, the list is malformed, or the website's server is not on
it. It is a warning when the list is too lenient, or when the website hands its mail to
a server on the same machine, so the page cannot tell which public address the mail
leaves from.

**Message signature (DKIM).** A digital signature the mail server puts on every message,
which receiving systems check against a public key published with the domain name. It is
a problem when the key is not published. It is a warning, *No DKIM selector is
configured*, when the website has not been told which key to look for: the person who runs
the server needs to give it the key's name. The signature itself may be working; the page
just cannot check.

**Handling of forged mail (DMARC).** A short public instruction that tells receiving
systems what to do with a message that claims to come from CalDART but fails the other
checks, and where to send reports about such messages. It is a problem when none is
published, or when more than one is, because receiving systems then follow none of them.
It is a warning while the instruction only says to watch (``p=none``) and
asks receivers to do nothing about forgeries. It is good when it says to send forgeries
to spam (``quarantine``) or refuse them (``reject``). When the instruction names an address for
reports, the page lists it.

**Bounce address.** When a receiving server cannot deliver a message, it sends it back to
the bounce address, and CalDART reads those returns to find out which addresses are no
good. Some systems trust a message more when the
bounce address is on the same domain as the From address. It is a warning when it is on
an unrelated domain.


When something is not good
==========================

Copy the **What to do** sentence into an email to the person who manages the CalDART
domain name (often whoever registered it) or who runs the website's server. They will know
the records by name. Changes to a domain name can take a few hours to reach everyone, so
**Check again** may still show the old answer for a while.

If a block says that a lookup *did not get an answer in time*, or that the check *took too
long*, the page could not reach the domain name system at that moment. That says nothing
about your records: press **Check again** in a minute or two. If it says that *no name
server could answer*, the domain's own name servers are not working, and whoever manages
the domain name needs to look at them.
