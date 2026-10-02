:roles: management

==========
Bulk Email
==========

**Bulk Email** writes one email to everybody a filter selects: every friend of CalDART, the
members of one DART, the pilots in two counties, or the whole membership. Each person is
sent a copy of their own. You see the list of recipients before anything is sent, and every
send is kept with what became of each copy.

The CalDART management role opens it, as **Bulk Email** under **Administration** in the
menu. A system administrator can open it too. A user administrator grants the role.


Choosing who it goes to
=======================

The filters at the top are the ones the member list uses, and they choose the same people:

- **Kind**: **Members only** or **Friends only**. A friend is somebody who supports CalDART
  without a paid membership; leave **Kind** on **All** to write to both.
- **Search**: a name, an email address, a phone number, or a certificate number.
- **Membership**: **Current**, **Expired**, or **Friend**.
- **Certificate**, **Medical**, and **DART**.
- **County**: tick as many counties as you like.
- **Role**: the holders of one role.
- **Expiring within (days)**: members whose membership ends within that many days.

Each filter applies itself as you choose it. **Reset to Defaults** clears them all, which
selects every member and friend. Donors are never on the list.


Writing the message
===================

**Subject** is one line, and every recipient sees it exactly as you type it. **Message** is
plain text: leave a blank line between paragraphs and each becomes a paragraph of the
email. Both are required.

Each copy comes from the site's own address. Under the message it carries a short footer
with your organization's name, the contact address when one is set, and the line *You
receive this email as a member or a friend of* your organization.


Previewing the recipients
=========================

Press **Preview recipients**. Nothing is sent. Under the form a line counts the list, such
as *42 people will be sent this email; 3 are skipped.*, and the table **Who this email would
reach** names each person: **To send** for everyone who will be sent a copy, then
**Skipped** for everyone the filters chose who will not be, with the reason:

- *Account deactivated*: the account has been deactivated.
- *No email address*: there is no address on the account.
- *Invalid email address*: the address on file could never be delivered.
- *Duplicate address*: somebody earlier on the list has the same address, so it gets one
  copy.

**Download list** saves the same list as a spreadsheet file (CSV), with each person's name,
address, result (*To send* or *Skipped*), and reason.

Changing a filter puts the preview away, because it no longer says who the email would
reach; press **Preview recipients** again. Changing the subject or the message keeps it.


Sending
=======

Under the preview, **Send to 42 people** (with the count from the preview) asks first: *This
sends* the subject *to 42 people now. A sent email cannot be called back.* Press **Send
now** to send, or **Cancel** to go back.

The list is built again at the moment you send, so somebody who started matching the
filters after the preview is sent a copy too. A send that would reach nobody is refused
with *Nobody matches these filters.*

When it finishes, **What became of each copy** replaces the preview: the subject and the
date, a line such as *Sent 41, failed 1, skipped 3.*, a **Download the list** link, and a
row per person reading **Sent**, **Failed**, or **Skipped**. A copy the mail server refused
reads **Failed** with *Refused by the mail server*; every other copy still goes. Each copy
also appears in the log of sent emails as *Bulk email*.


Past sends
==========

**Sent bulk emails**, below, lists every send, the most recent first, one line each:

- **Date**: the day it was sent.
- **Subject** and **From**: what it said, and who sent it.
- **Sent**, **Failed**, and **Skipped**: how many copies went, were refused, and were
  skipped.
- **Results** opens the send's rows under the table, as they read just after it went.
  **CSV** downloads them, with each person's name, address, result, and reason.

Before the first send the table reads *No bulk email has been sent*.


If something looks wrong
========================

If the preview lists fewer people than you expected, look at the skips first, then at the
filters: a forgotten **County** or **Kind** narrows the list quietly, and **Reset to
Defaults** starts again from everybody. If somebody says the email never arrived, open the
send under **Results** and find their row. **Sent** means CalDART handed the copy to the
mail server, so ask them to check their spam folder; **Failed** or **Skipped** gives the
reason. An address that needs correcting is corrected on the person's account by a user
administrator or an account administrator.
