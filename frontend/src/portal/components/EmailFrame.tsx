/**
 * An email drawn in a sandboxed frame, as a reader sees it in a mail program.
 *
 * Nothing in the email can run or reach the portal: the frame allows no scripts, no
 * forms, and no same-origin access.  It allows only popups that leave the sandbox, and
 * every link in the email opens in a new tab (a `<base target="_blank">` put at the
 * head of the email), so a reader can follow a newsletter's links without the page
 * they are reading being replaced. A small style at the head keeps every picture
 * within the frame's width, so a narrow screen shows the whole email; the frame is
 * as tall as most of the window and scrolls.
 */
import type { JSX } from 'react';

/** The sandbox: popups only, which may leave it, and nothing else. */
export const EMAIL_FRAME_SANDBOX = 'allow-popups allow-popups-to-escape-sandbox';

/** What is put at the head of every email, so its links open in a new tab. */
const NEW_TAB_BASE = '<base target="_blank" rel="noopener">';

/** What is put at the head of every email, so no picture is wider than the frame. */
const FITTED_IMAGES = '<style>img{max-width:100%;height:auto}</style>';

/** `html` with `markup` just inside `<head>` when the email has one, and first otherwise. */
function atHead(html: string, markup: string): string {
  const head = /<head(\s[^>]*)?>/i.exec(html);
  if (head === null) return `${markup}${html}`;
  const at = head.index + head[0].length;
  return `${html.slice(0, at)}${markup}${html.slice(at)}`;
}

/** `html` with its links set to open in a new tab. */
export function withNewTabLinks(html: string): string {
  return atHead(html, NEW_TAB_BASE);
}

/** `html` with every picture kept within the width it is shown at, its height in step. */
export function withFittedImages(html: string): string {
  return atHead(html, FITTED_IMAGES);
}

export interface EmailFrameProps {
  /** The frame's accessible name, such as "The email as Ann Able received it". */
  title: string;
  /** The whole HTML email. */
  html: string;
}

/** The document the frame shows: `html` with links to a new tab and pictures fitted. */
export function emailDocument(html: string): string {
  return withFittedImages(withNewTabLinks(html));
}

/** The email `html` in a sandboxed frame whose links open in a new tab. */
export function EmailFrame({ title, html }: EmailFrameProps): JSX.Element {
  return (
    <iframe
      className="email-frame"
      title={title}
      sandbox={EMAIL_FRAME_SANDBOX}
      srcDoc={emailDocument(html)}
    />
  );
}
