/*
 * A toolbar under every diagram and image figure in the CalDART docs.
 *
 * After the page loads, every <figure> holding a Graphviz <object> or an <img>
 * gains two controls: "Open full size", a link that opens the SVG or image on
 * its own in a new tab, and "Zoom", which opens a full-window overlay showing
 * it at its natural size in a scrollable panel.  "Close" or the Escape key
 * closes the overlay and returns focus to the Zoom button.
 *
 * Loaded by docs/conf.py through html_js_files, for both builds.  It uses no
 * inline handlers, so it runs under a script-src of 'self', and it needs no
 * library.
 */
(() => {
  'use strict';

  /** The URL of the figure's drawing, or null when it holds neither kind. */
  function sourceOf(figure) {
    const diagram = figure.querySelector('object.graphviz');
    if (diagram !== null && diagram.data !== '') {
      return diagram.data;
    }
    const image = figure.querySelector('img');
    if (image !== null) {
      return image.currentSrc || image.src;
    }
    return null;
  }

  /** The text that names the figure for a screen reader: its alt text or caption. */
  function nameOf(figure) {
    const image = figure.querySelector('img');
    if (image !== null && image.alt !== '') {
      return image.alt;
    }
    const caption = figure.querySelector('figcaption');
    return caption === null ? 'Figure' : caption.textContent.trim();
  }

  /** Build the overlay once; every Zoom button reuses it. */
  function buildOverlay() {
    const overlay = document.createElement('div');
    overlay.className = 'figure-zoom-overlay';
    overlay.hidden = true;
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Figure at full size');

    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'figure-zoom-close';
    close.textContent = 'Close';

    const panel = document.createElement('div');
    panel.className = 'figure-zoom-panel';
    panel.tabIndex = 0;

    const image = document.createElement('img');
    image.className = 'figure-zoom-image';
    panel.append(image);
    overlay.append(close, panel);
    document.body.append(overlay);

    let opener = null;

    function hide() {
      overlay.hidden = true;
      image.removeAttribute('src');
      document.documentElement.classList.remove('figure-zoom-open');
      if (opener !== null) {
        opener.focus();
        opener = null;
      }
    }

    close.addEventListener('click', hide);
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !overlay.hidden) {
        event.preventDefault();
        hide();
      }
    });

    return {
      show(url, name, button) {
        opener = button;
        image.src = url;
        image.alt = name;
        overlay.hidden = false;
        document.documentElement.classList.add('figure-zoom-open');
        panel.scrollTo(0, 0);
        close.focus();
      },
    };
  }

  /** Append the toolbar to one figure. */
  function addToolbar(figure, url, overlay) {
    const toolbar = document.createElement('div');
    toolbar.className = 'figure-zoom-toolbar';

    const open = document.createElement('a');
    open.href = url;
    open.target = '_blank';
    open.rel = 'noopener';
    open.textContent = 'Open full size';

    const zoom = document.createElement('button');
    zoom.type = 'button';
    zoom.textContent = 'Zoom';
    zoom.addEventListener('click', () => overlay.show(url, nameOf(figure), zoom));

    toolbar.append(open, zoom);
    figure.append(toolbar);
  }

  function start() {
    const figures = [...document.querySelectorAll('figure')]
      .map((figure) => ({ figure, url: sourceOf(figure) }))
      .filter(({ url }) => url !== null);
    if (figures.length === 0) {
      return;
    }
    const overlay = buildOverlay();
    figures.forEach(({ figure, url }) => addToolbar(figure, url, overlay));
  }

  if (document.readyState === 'complete') {
    start();
  } else {
    window.addEventListener('load', start);
  }
})();
