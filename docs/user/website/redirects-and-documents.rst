=======================
Redirects and documents
=======================

This page covers three libraries the editor keeps besides the pages: the redirects that
send an old address to a new one, the images pages show, and the documents people
download.

What you see
============

Redirects
~~~~~~~~~

**Settings**, then **Redirects**, lists every address the site forwards somewhere else.
Each row shows the old address under **From**, where it lands under **To**, and whether
the redirect is permanent or temporary. **Filter by** narrows the list by **Type**, and
**Search term** finds an address.

Most rows arrive on their own. When you publish a change to a page's **Slug**, or move a
page to a different parent, the editor adds a redirect from the page's old address, and
from the old address of every page beneath it, to where each one is now. That is why
renaming a page is safe: a printed flyer with the old address still works.

Images
~~~~~~

**Images** in the left-hand menu is the image library. Upload a picture once and use it
anywhere; the site makes the sizes each page needs. GIF, JPEG, PNG, WebP, and SVG files
are accepted, up to 10 MB each. The editor asks for a description of each image for
people who use screen readers.

Documents
~~~~~~~~~

**Documents** is the same idea for files people download: PDF, Word (DOCX), Excel (XLSX),
PowerPoint (PPTX), CSV, plain text (TXT), RTF, OpenDocument text (ODT), Keynote (KEY),
and ZIP files. On the live site a file can be up to 25 MB.

Every document belongs to a collection, chosen when you upload it and changeable later
on the document's own page. The site starts with two: **Root**, where a file lands unless
you choose otherwise, and **Members only**. The collection decides who may download the
file (see :doc:`members-only`).

What you can do
===============

Add a redirect
~~~~~~~~~~~~~~

Press **Add redirect** and fill in:

* **Redirect from**, the old address, such as /old-news.
* **From site**, which you leave as it is.
* **Permanent**, ticked to begin with. Untick it for a redirect you mean to remove later.
* **Redirect to a page**, a page chosen from the tree, or **Redirect to any URL**, a typed
  address. Fill in one of the two.

Press **Create**. You can change and delete redirects too. Deleting one the editor made
for you makes the old address stop working, so remove a redirect only when you want
that.

Upload images and documents
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Under **Images** or **Documents**, press the add button, drag files into the box or
choose them from your computer, and pick the collection under **Add to collection**.
Give every upload a title that says what it is: the title is what appears in the
chooser, in search, and, for a document, as the link's text unless you give it another.

Use them on a page
~~~~~~~~~~~~~~~~~~

Put an image on a page with the **Image** block, and a document with the **Document**
block or the document-link button in a paragraph (see :doc:`pages-and-blocks`). To
replace a document everyone links to, open it under **Documents** and upload the new
file there; the links keep working.

If something looks wrong
========================

If a page that used to work now says it cannot be found, its address changed. Check
**Redirects** first, since a slug change you published should have made one; if it is
missing, add a redirect from the old address to the page, or set the slug back. If an
image or a document will not upload, check that its type is one of those listed above
and that it is under the size limit. A photograph straight off a camera is usually far
larger than a web page needs, so resize it before uploading and the site will be quicker
too.
