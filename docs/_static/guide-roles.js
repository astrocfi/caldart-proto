/*
 * The user guide's sidebar and tables of contents, trimmed to the reader's roles.
 *
 * Every page the site serves at /docs/ carries this script (docs/conf.py lists it
 * under the guide build alone).  Once the page has loaded it reads two things from
 * the site: roles.json, which the guide build writes beside its index and which
 * names each role-restricted page and the roles that may read it, and the reader's
 * own roles from the portal's /api/v1/auth/me.  It then removes every sidebar
 * entry, table-of-contents entry, and next or previous link that leads to a page
 * the reader's roles do not reach, and any caption or table whose entries are all
 * gone.  On the search page it does the same to every result, as Sphinx adds them,
 * and makes the closing count say how many are left.  A system administrator sees
 * everything.
 *
 * An inline script in the page head marks <html> "guide-roles-pending", and
 * guide-roles.css keeps the trees hidden while it is there; this script clears the
 * mark once both reads have settled, whether they succeeded or not.  When either
 * fails, nothing is removed: the server still refuses a restricted page, and a
 * reader who follows its link lands on the guide's front page.
 *
 * The guide's root is read from the data-content_root attribute Sphinx writes on
 * <html>, so the script works at any depth and under any URL prefix: the portal's
 * API sits beside /docs/.  It uses no inline handlers and needs no library.
 */
(() => {
  'use strict';

  const PENDING = 'guide-roles-pending';
  const SYSTEM_ADMIN = 'system_admin';
  const ROLES_FILE = 'roles.json';
  const ME_PATH = '../api/v1/auth/me';
  const INDEX = 'index';
  /** The lists this script trims, and the next and previous links under each page. */
  const TREES = '.sidebar-tree, .toctree-wrapper';
  const RELATED = '.related-pages a';
  /** Sphinx's search page: the results it lists, and the sentence that counts them. */
  const SEARCH_RESULTS = 'search-results';
  const SEARCH_ITEMS = 'ul.search > li > a:first-child';
  const SEARCH_SUMMARY = 'p.search-summary';
  const SEARCH_FINISHED = 'Search finished';

  const guideRoot = new URL(
    document.documentElement.dataset.content_root ?? './',
    window.location.href,
  );

  /** The body of a same-origin JSON response, or an error for any other answer. */
  async function readJson(url) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) {
      throw new Error(`${url} answered ${response.status}`);
    }
    return response.json();
  }

  /**
   * The docname a link inside the guide leads to, or null for a link that leaves it.
   *
   * The dirhtml build writes the page "admin/members" at admin/members/, and a
   * group's index "admin/index" at admin/, so a directory path is returned without
   * its slash and looked up both ways by rolesOf().
   */
  function pathOf(href) {
    const url = new URL(href, window.location.href);
    if (url.origin !== guideRoot.origin || !url.pathname.startsWith(guideRoot.pathname)) {
      return null;
    }
    return decodeURIComponent(url.pathname.slice(guideRoot.pathname.length))
      .replace(/index\.html$/, '')
      .replace(/\/$/, '');
  }

  /** The roles that may read the page at ``path``; an empty list for an open page. */
  function rolesOf(pageRoles, path) {
    if (path === '') {
      return pageRoles[INDEX] ?? [];
    }
    return pageRoles[path] ?? pageRoles[`${path}/${INDEX}`] ?? [];
  }

  /** True when a reader holding ``held`` may read a page restricted to ``needed``. */
  function mayRead(held, needed) {
    if (needed.length === 0 || held.includes(SYSTEM_ADMIN)) {
      return true;
    }
    return needed.some((slug) => held.includes(slug));
  }

  /** True when ``anchor`` leads to a page inside the guide the reader may not read. */
  function isHidden(anchor, pageRoles, held) {
    const path = pathOf(anchor.href);
    return path !== null && !mayRead(held, rolesOf(pageRoles, path));
  }

  /** Remove every list that has no entries left, with its caption and empty wrapper. */
  function removeEmptyLists() {
    for (const list of document.querySelectorAll(`:is(${TREES}) ul`)) {
      if (list.querySelector('li') !== null) {
        continue;
      }
      const caption = list.previousElementSibling;
      if (caption !== null && caption.classList.contains('caption')) {
        caption.remove();
      }
      const wrapper = list.closest('.toctree-wrapper');
      list.remove();
      if (wrapper !== null && wrapper.querySelector('ul') === null) {
        wrapper.remove();
      }
    }
  }

  /** Take out of the page every link to a page the reader's roles do not reach. */
  function prune(pageRoles, held) {
    for (const anchor of document.querySelectorAll(`:is(${TREES}) li > a`)) {
      if (isHidden(anchor, pageRoles, held)) {
        anchor.parentElement.remove();
      }
    }
    for (const anchor of document.querySelectorAll(RELATED)) {
      if (isHidden(anchor, pageRoles, held)) {
        anchor.remove();
      }
    }
    removeEmptyLists();
  }

  /** The sentence Sphinx closes a search with, for ``count`` results. */
  function searchSummary(count) {
    if (count === 0) {
      return 'Your search did not match any page you can open.';
    }
    const pages = count === 1 ? 'one page' : `${count} pages`;
    return `${SEARCH_FINISHED}, found ${pages} matching the search query.`;
  }

  /**
   * Take out of the search results, now and as Sphinx adds more, every page the
   * reader's roles do not reach, and recount them once Sphinx has said it is done.
   */
  function trimSearchResults(pageRoles, held) {
    const results = document.getElementById(SEARCH_RESULTS);
    if (results === null) {
      return;
    }
    let removed = 0;
    const trim = () => {
      for (const anchor of results.querySelectorAll(SEARCH_ITEMS)) {
        if (isHidden(anchor, pageRoles, held)) {
          anchor.parentElement.remove();
          removed += 1;
        }
      }
      const summary = results.querySelector(SEARCH_SUMMARY);
      if (removed === 0 || summary === null || !summary.textContent.startsWith(SEARCH_FINISHED)) {
        return;
      }
      const recount = searchSummary(results.querySelectorAll(SEARCH_ITEMS).length);
      if (summary.textContent !== recount) {
        summary.textContent = recount;
      }
    };
    trim();
    new MutationObserver(trim).observe(results, { childList: true, subtree: true });
  }

  /** Read the page roles and the reader's roles, trim the page, and show the trees. */
  async function run() {
    try {
      const [pageRoles, me] = await Promise.all([
        readJson(new URL(ROLES_FILE, guideRoot)),
        readJson(new URL(ME_PATH, guideRoot)),
      ]);
      prune(pageRoles, me.roles ?? []);
      trimSearchResults(pageRoles, me.roles ?? []);
    } catch (error) {
      console.warn("The guide could not read the reader's roles; every entry stays.", error);
    } finally {
      document.documentElement.classList.remove(PENDING);
    }
  }

  void run();
})();
